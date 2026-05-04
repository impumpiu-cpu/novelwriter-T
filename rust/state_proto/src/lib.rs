mod core;

use aho_corasick::AhoCorasick;
use jieba_rs::Jieba;
use pyo3::pybacked::PyBackedStr;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyTuple};
use regex::{Match, Matches, Regex};
use rustc_hash::{FxHashMap, FxHashSet};
use std::borrow::Cow;
use std::sync::{Mutex, OnceLock};
use unicode_casefold::UnicodeCaseFold;
use unicode_normalization::UnicodeNormalization;

use crate::core::{
    assemble_payload_bytes, build_full as build_full_request, build_full_bytes,
    normalize_chapter_text,
    plan_update_result,
    segment_chapter_text_without_index,
    update_incremental as update_incremental_request, update_incremental_bytes,
    BuildRequest, BuildResult, PayloadError, RequestChapter, RequestTarget,
    STATE_PROTO_PAYLOAD_FORMAT_VERSION, UpdatePlanResult,
};

impl From<PayloadError> for PyErr {
    fn from(value: PayloadError) -> Self {
        PyValueError::new_err(value.to_string())
    }
}

static ZH_TOKENIZER: OnceLock<Mutex<Option<Jieba>>> = OnceLock::new();
type CandidateCount = u32;
const ZH_SPLIT_NAME_MIN_COUNT: CandidateCount = 2;
const ZH_FRAGMENT_EXTENSION_MIN_COUNT: CandidateCount = 3;
const ZH_FRAGMENT_DOMINANCE_THRESHOLD: f32 = 0.85;
const ZH_FRAGMENT_MAX_TOKEN_CHARS: usize = 3;
const ZH_BLOCK_MIN_OCCURRENCES: usize = 3;
const ZH_BLOCK_MIN_BLOCKS: usize = 1;
const ZH_BLOCK_DISCOVERY_MULTIPLIER: usize = 8;
const ZH_BLOCK_DISCOVERY_HARD_CAP: usize = 2048;
const ZH_BLOCK_RETURN_MULTIPLIER: usize = 6;
const ZH_BLOCK_RETURN_HARD_CAP: usize = 768;
const ZH_BLOCK_MIN_BOUNDARY_ENTROPY: f64 = 0.55;
const ZH_BLOCK_MIN_EXTENSION_CONTAINMENT: f64 = 0.90;
const ZH_BLOCK_MIN_EXTENSION_SCORE_MARGIN: f64 = 0.75;
const ZH_BLOCK_FRAGMENT_DIRECTIONAL_ENTROPY_MAX: f64 = 1.6;
const ZH_BLOCK_FRAGMENT_EXTENSION_MIN_CONTAINMENT: f64 = 0.82;
const ZH_BLOCK_FRAGMENT_EXTENSION_MAX_SECONDARY_RATIO: f64 = 0.5;
const ZH_BLOCK_LOCAL_EXTENSION_MAX_EXTRA_CHARS: usize = 2;
const ZH_BLOCK_GENERIC_MODIFIER_PREFIX_CHARS: &str = "大小老新旧高低前后左右上下内外";
const ZH_BLOCK_LOW_VALUE_PREFIX_CHARS: &str =
    "一都这那没了着出个自给将把向从对跟比于其各每该本此";
const ZH_BLOCK_LOW_VALUE_SUFFIX_CHARS: &str = "了着过啊呀吧呢吗么的";
const ZH_BLOCK_LOW_VALUE_INTERIOR_CHARS: &str = "的";
const ZH_BLOCK_EXTRA_SINGLE_SURNAMES: &str = "林花贺兰佟柯";
const ZH_BLOCK_TWO_CHAR_FUNCTION_CHARS: &str =
    "了不的来去都也就在上里看说没是有把将和与着出个给这那好太很再更向从对跟比于到等让";
const ZH_BLOCK_TWO_CHAR_HINT_SUFFIXES: &str =
    "星际焰兽师士器盘镯石药炉体子司营府院门宗派盟帮城港谷湖河山殿宫阁楼坊铺";
const ZH_BLOCK_GENERIC_ROLE_SUFFIX_CHARS: &str = "后帝王君皇妃司师使神主尊圣";
const ZH_SINGLE_SURNAMES: &str =
    include_str!("../../../app/core/indexing/data/zh_single_surnames.txt");
const ZH_COMPOUND_SURNAMES: &str =
    include_str!("../../../app/core/indexing/data/zh_compound_surnames.txt");
const ZH_NAME_TRAILING_NOISE_CHARS: &str =
    include_str!("../../../app/core/indexing/data/zh_name_trailing_noise_chars.txt");
const ZH_TRANSLIT_CHARS: &str =
    include_str!("../../../app/core/indexing/data/zh_translit_chars.txt");
const ZH_NAME_SUFFIX_TITLES: &str =
    include_str!("../../../app/core/indexing/data/zh_name_suffix_titles.txt");
const ZH_VARIANT_CHAR_LINES: &str =
    include_str!("../../../app/core/indexing/data/zh_variant_chars.tsv");

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum MatchNormalization {
    None,
    AsciiLower,
    UnicodeCaseFold,
}

#[derive(Debug, Clone)]
struct NarrativeBlock {
    text: String,
}

#[derive(Debug, Clone, Default)]
struct BlockSurfaceAccumulator {
    raw_occurrences: usize,
    block_count: usize,
    left_contexts: FxHashMap<BoundarySymbol, CandidateCount>,
    right_contexts: FxHashMap<BoundarySymbol, CandidateCount>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum BoundarySymbol {
    Start,
    End,
    Whitespace,
    Punctuation,
    Other,
    Char(char),
}

#[derive(Debug, Clone)]
struct RepeatedSpanSurfaceStat {
    surface_id: usize,
    char_len: usize,
    raw_occurrences: usize,
    block_count: usize,
    left_entropy: f64,
    right_entropy: f64,
    discovery_score: f64,
}

#[derive(Debug, Clone)]
struct CanonicalCandidate {
    canonical_id: usize,
    importance: usize,
    block_count: usize,
    discovery_score: f64,
    surface_ids: Vec<usize>,
}

thread_local! {
    static COUNT_RE_HAN_DEFAULT: Regex = Regex::new(
        r"([\u{3400}-\u{4DBF}\u{4E00}-\u{9FFF}\u{F900}-\u{FAFF}\u{20000}-\u{2A6DF}\u{2A700}-\u{2B73F}\u{2B740}-\u{2B81F}\u{2B820}-\u{2CEAF}\u{2CEB0}-\u{2EBEF}\u{2F800}-\u{2FA1F}a-zA-Z0-9+#&\._%\-]+)"
    ).unwrap();
    static COUNT_RE_SKIP_DEFAULT: Regex = Regex::new(r"(\r\n|\s)").unwrap();
}

struct SplitMatches<'r, 't> {
    finder: Matches<'r, 't>,
    text: &'t str,
    last: usize,
    matched: Option<Match<'t>>,
}

impl<'r, 't> SplitMatches<'r, 't> {
    #[inline]
    fn new(re: &'r Regex, text: &'t str) -> SplitMatches<'r, 't> {
        SplitMatches {
            finder: re.find_iter(text),
            text,
            last: 0,
            matched: None,
        }
    }
}

enum SplitState<'t> {
    Unmatched(&'t str),
    Matched(Match<'t>),
}

impl<'t> SplitState<'t> {
    #[inline]
    fn as_str(&self) -> &'t str {
        match self {
            SplitState::Unmatched(text) => text,
            SplitState::Matched(matched) => matched.as_str(),
        }
    }

    #[inline]
    fn is_matched(&self) -> bool {
        matches!(self, SplitState::Matched(_))
    }
}

impl<'r, 't> Iterator for SplitMatches<'r, 't> {
    type Item = SplitState<'t>;

    #[inline]
    fn next(&mut self) -> Option<Self::Item> {
        if let Some(matched) = self.matched.take() {
            self.last = matched.end();
            return Some(SplitState::Matched(matched));
        }

        if let Some(matched) = self.finder.next() {
            if matched.start() != self.last {
                let unmatched = &self.text[self.last..matched.start()];
                self.matched = Some(matched);
                self.last = matched.start();
                return Some(SplitState::Unmatched(unmatched));
            }
            self.last = matched.end();
            return Some(SplitState::Matched(matched));
        }

        if self.last != self.text.len() {
            let unmatched = &self.text[self.last..];
            self.last = self.text.len();
            return Some(SplitState::Unmatched(unmatched));
        }

        None
    }
}

fn zh_tokenizer_state() -> &'static Mutex<Option<Jieba>> {
    ZH_TOKENIZER.get_or_init(|| Mutex::new(None))
}

fn with_zh_tokenizer<R>(f: impl FnOnce(&Jieba) -> R) -> R {
    let mut tokenizer = zh_tokenizer_state()
        .lock()
        .expect("zh tokenizer mutex poisoned");
    let tokenizer = tokenizer.get_or_insert_with(Jieba::new);
    f(tokenizer)
}

fn release_zh_tokenizer() {
    let mut tokenizer = zh_tokenizer_state()
        .lock()
        .expect("zh tokenizer mutex poisoned");
    tokenizer.take();
}

#[pyfunction]
fn payload_format_version() -> u32 {
    STATE_PROTO_PAYLOAD_FORMAT_VERSION
}

#[pyfunction]
fn tokenize_zh_text(py: Python<'_>, text: &str) -> PyResult<Vec<String>> {
    let source = text.to_owned();
    Ok(py.allow_threads(|| {
        with_zh_tokenizer(|tokenizer| {
            tokenizer
                .cut(&source, true)
                .into_iter()
                .map(str::to_owned)
                .collect()
        })
    }))
}

#[pyfunction]
fn count_zh_candidates(
    py: Python<'_>,
    chapters: Vec<PyBackedStr>,
    common_words: Vec<PyBackedStr>,
    max_batch_chars: usize,
) -> PyResult<Vec<(String, usize)>> {
    py.allow_threads(|| count_zh_candidates_impl(chapters, common_words, max_batch_chars))
        .map_err(PyValueError::new_err)
}

#[pyfunction]
fn count_zh_candidates_topk(
    py: Python<'_>,
    chapters: Vec<PyBackedStr>,
    common_words: Vec<PyBackedStr>,
    max_batch_chars: usize,
    limit: usize,
) -> PyResult<Vec<(String, usize)>> {
    py.allow_threads(|| count_zh_candidates_topk_impl(
        chapters,
        common_words,
        max_batch_chars,
        limit,
    ))
    .map_err(PyValueError::new_err)
}

#[pyfunction]
fn summarize_zh_windows(
    py: Python<'_>,
    chapters: Vec<PyBackedStr>,
    shortlisted_candidates: Vec<PyBackedStr>,
    window_size: usize,
    window_step: usize,
    threshold: usize,
) -> PyResult<(Vec<(String, usize)>, Vec<(String, String, usize)>)> {
    py.allow_threads(|| {
        summarize_zh_windows_impl(
            chapters,
            shortlisted_candidates,
            window_size,
            window_step,
            threshold,
        )
    })
    .map_err(PyValueError::new_err)
}

#[pyfunction]
fn summarize_zh_windows_compact(
    py: Python<'_>,
    chapters: Vec<PyBackedStr>,
    shortlisted_candidates: Vec<PyBackedStr>,
    window_size: usize,
    window_step: usize,
    threshold: usize,
) -> PyResult<(Vec<String>, Vec<(usize, usize)>, Vec<(usize, usize, usize)>)> {
    py.allow_threads(|| {
        summarize_zh_windows_compact_impl(
            chapters,
            shortlisted_candidates,
            window_size,
            window_step,
            threshold,
        )
    })
    .map_err(PyValueError::new_err)
}

#[pyfunction]
fn summarize_zh_windows_raw(
    py: Python<'_>,
    chapters: Vec<PyBackedStr>,
    shortlisted_candidates: Vec<PyBackedStr>,
    window_size: usize,
    window_step: usize,
) -> PyResult<(Vec<(usize, usize)>, Vec<(usize, usize)>)> {
    py.allow_threads(|| {
        let (_, importance_counts, pair_counts) = summarize_zh_window_counts_impl(
            chapters,
            shortlisted_candidates,
            window_size,
            window_step,
        )?;
        Ok((
            importance_counts
                .into_iter()
                .enumerate()
                .filter_map(|(candidate_id, count)| (count > 0).then_some((candidate_id, count)))
                .collect(),
            pair_counts
                .into_iter()
                .enumerate()
                .filter_map(|(pair_key, count)| (count > 0).then_some((pair_key, count as usize)))
                .collect(),
        ))
    })
    .map_err(|err: String| PyValueError::new_err(err))
}

#[pyfunction]
fn build_zh_block_refinement_inputs_compact(
    py: Python<'_>,
    chapters: Vec<PyBackedStr>,
    common_words: Vec<PyBackedStr>,
    limit: usize,
) -> PyResult<(
    Vec<String>,
    Vec<(usize, usize)>,
    Vec<(usize, usize, usize)>,
    Vec<(usize, Vec<usize>)>,
)> {
    py.allow_threads(|| build_zh_block_refinement_inputs_compact_impl(chapters, common_words, limit))
        .map_err(PyValueError::new_err)
}

fn build_zh_block_refinement_inputs_compact_impl(
    chapters: Vec<PyBackedStr>,
    common_words: Vec<PyBackedStr>,
    limit: usize,
) -> Result<(
    Vec<String>,
    Vec<(usize, usize)>,
    Vec<(usize, usize, usize)>,
    Vec<(usize, Vec<usize>)>,
), String> {
    let normalized_chapters = normalize_zh_chapter_strings(chapters);
    let common_word_set: FxHashSet<String> = common_words
        .into_iter()
        .map(|word| word.to_string())
        .collect();
    let discovery_limit = usize::min(
        usize::max(limit.saturating_mul(ZH_BLOCK_DISCOVERY_MULTIPLIER), 1024),
        ZH_BLOCK_DISCOVERY_HARD_CAP,
    );
    let mut seed_candidates = collect_candidate_counts_with_common_words(
        normalized_chapters.iter().map(|chapter| chapter.as_str()),
        &common_word_set,
        256 * 1024,
    );
    truncate_candidate_counts_topk(&mut seed_candidates, discovery_limit);
    release_zh_tokenizer();
    if seed_candidates.is_empty() {
        return Ok((Vec::new(), Vec::new(), Vec::new(), Vec::new()));
    }

    let blocks = segment_chapters_into_blocks_from_strings(&normalized_chapters);
    if blocks.is_empty() {
        return Ok((Vec::new(), Vec::new(), Vec::new(), Vec::new()));
    }

    let effective_min_blocks = if blocks.len() <= 1 {
        1
    } else {
        ZH_BLOCK_MIN_BLOCKS
    };
    let (surface_names, surface_stats, surface_blocks, block_present_surfaces) =
        collect_seeded_surface_stats(
        &blocks,
        &common_word_set,
        &seed_candidates,
        ZH_BLOCK_MIN_OCCURRENCES,
        effective_min_blocks,
    )?;
    if surface_stats.is_empty() {
        return Ok((Vec::new(), Vec::new(), Vec::new(), Vec::new()));
    }

    let canonical_candidates = build_canonical_candidates(
        &surface_names,
        &surface_stats,
        &surface_blocks,
    );
    if canonical_candidates.is_empty() {
        return Ok((Vec::new(), Vec::new(), Vec::new(), Vec::new()));
    }

    let return_limit = usize::min(
        usize::max(limit.saturating_mul(ZH_BLOCK_RETURN_MULTIPLIER), 256),
        ZH_BLOCK_RETURN_HARD_CAP,
    );
    let selected_candidates = canonical_candidates
        .into_iter()
        .take(return_limit)
        .collect::<Vec<_>>();
    Ok(compact_selected_candidates_output(
        &surface_names,
        &selected_candidates,
        &block_present_surfaces,
    ))
}

fn collect_seeded_surface_stats(
    blocks: &[NarrativeBlock],
    common_words: &FxHashSet<String>,
    seed_candidates: &[(String, usize)],
    min_occurrences: usize,
    min_blocks: usize,
) -> Result<
    (
        Vec<String>,
        Vec<RepeatedSpanSurfaceStat>,
        Vec<Vec<usize>>,
        Vec<Vec<usize>>,
    ),
    String,
> {
    let mut seed_names = seed_candidates
        .iter()
        .filter_map(|(surface, _)| {
            let char_len = surface.chars().count();
            (char_len >= 2 && is_cjk_token(surface.as_str())).then_some(surface.clone())
        })
        .collect::<Vec<_>>();
    seed_names.sort_unstable_by(|left, right| {
        right
            .chars()
            .count()
            .cmp(&left.chars().count())
            .then_with(|| left.cmp(right))
    });
    seed_names.dedup();
    if seed_names.is_empty() {
        return Ok((Vec::new(), Vec::new(), Vec::new(), Vec::new()));
    }
    let seed_name_set: FxHashSet<String> = seed_names.iter().cloned().collect();

    let automaton = AhoCorasick::new(
        seed_names
            .iter()
            .map(|surface| surface.as_str())
            .collect::<Vec<_>>(),
    )
    .map_err(|err| err.to_string())?;
    let seed_char_lens = seed_names
        .iter()
        .map(|surface| surface.chars().count())
        .collect::<Vec<_>>();
    let mut surface_id_by_name: FxHashMap<String, usize> = FxHashMap::default();
    let mut surface_names = Vec::new();
    let mut accumulators: Vec<BlockSurfaceAccumulator> = Vec::new();
    let mut surface_blocks: Vec<Vec<usize>> = Vec::new();
    let mut block_present_surfaces = Vec::new();
    let mut char_starts = Vec::new();

    for (block_idx, block) in blocks.iter().enumerate() {
        if block.text.is_empty() {
            continue;
        }
        let chars: Vec<char> = block.text.chars().collect();
        if chars.len() < 2 {
            continue;
        }
        collect_char_starts_into(block.text.as_str(), &mut char_starts);
        let mut seen_in_block: FxHashSet<usize> = FxHashSet::default();
        let mut seen_occurrences: FxHashSet<(usize, usize, usize)> = FxHashSet::default();
        let mut char_cursor = 0usize;

        for matched in automaton.find_overlapping_iter(block.text.as_str()) {
            let seed_id = matched.pattern().as_usize();
            let start_byte = matched.start();
            while char_cursor + 1 < char_starts.len() && char_starts[char_cursor + 1] <= start_byte
            {
                char_cursor += 1;
            }
            let start_char = char_cursor;
            let end_char = start_char + seed_char_lens[seed_id];
            if end_char > chars.len() {
                continue;
            }

            record_surface_occurrence(
                &seed_names[seed_id],
                start_char,
                end_char,
                block_idx,
                &chars,
                &mut surface_id_by_name,
                &mut surface_names,
                &mut accumulators,
                &mut surface_blocks,
                &mut seen_in_block,
                &mut seen_occurrences,
                common_words,
                true,
            );
            record_local_seed_extensions(
                &seed_names[seed_id],
                start_char,
                end_char,
                block_idx,
                block.text.as_str(),
                &chars,
                &char_starts,
                common_words,
                &mut surface_id_by_name,
                &mut surface_names,
                &mut accumulators,
                &mut surface_blocks,
                &mut seen_in_block,
                &mut seen_occurrences,
            );
        }

        if seen_in_block.is_empty() {
            continue;
        }
        let mut present_ids = seen_in_block.into_iter().collect::<Vec<_>>();
        present_ids.sort_unstable();
        for &surface_id in &present_ids {
            surface_blocks[surface_id].push(block_idx);
            accumulators[surface_id].block_count += 1;
        }
        block_present_surfaces.push(present_ids);
    }

    let mut stats = Vec::new();
    for (surface_id, accumulator) in accumulators.into_iter().enumerate() {
        if accumulator.raw_occurrences < min_occurrences || accumulator.block_count < min_blocks {
            continue;
        }
        let left_entropy = entropy(&accumulator.left_contexts);
        let right_entropy = entropy(&accumulator.right_contexts);
        let boundary_entropy = left_entropy.min(right_entropy);
        let surface = surface_names[surface_id].as_str();
        if boundary_entropy < ZH_BLOCK_MIN_BOUNDARY_ENTROPY
            && !seed_name_set.contains(surface)
            && strip_zh_person_name_trailing_noise(surface).is_none()
            && !is_trusted_low_entropy_suffix_extension(surface, &seed_name_set)
        {
            continue;
        }
        let char_len = surface.chars().count();
        stats.push(RepeatedSpanSurfaceStat {
            surface_id,
            char_len,
            raw_occurrences: accumulator.raw_occurrences,
            block_count: accumulator.block_count,
            left_entropy,
            right_entropy,
            discovery_score: surface_discovery_score(
                surface,
                char_len,
                accumulator.raw_occurrences,
                accumulator.block_count,
                left_entropy,
                right_entropy,
            ),
        });
    }

    stats.sort_unstable_by(|left, right| {
        right
            .discovery_score
            .total_cmp(&left.discovery_score)
            .then_with(|| right.block_count.cmp(&left.block_count))
            .then_with(|| right.raw_occurrences.cmp(&left.raw_occurrences))
            .then_with(|| right.char_len.cmp(&left.char_len))
            .then_with(|| surface_names[left.surface_id].cmp(&surface_names[right.surface_id]))
    });

    Ok((surface_names, stats, surface_blocks, block_present_surfaces))
}

fn record_local_seed_extensions(
    seed_surface: &str,
    start_char: usize,
    end_char: usize,
    block_idx: usize,
    block_text: &str,
    chars: &[char],
    char_starts: &[usize],
    common_words: &FxHashSet<String>,
    surface_id_by_name: &mut FxHashMap<String, usize>,
    surface_names: &mut Vec<String>,
    accumulators: &mut Vec<BlockSurfaceAccumulator>,
    surface_blocks: &mut Vec<Vec<usize>>,
    seen_in_block: &mut FxHashSet<usize>,
    seen_occurrences: &mut FxHashSet<(usize, usize, usize)>,
) {
    let seed_char_len = end_char.saturating_sub(start_char);
    let extension_budget = local_extension_budget(seed_surface, seed_char_len);
    if extension_budget == 0 {
        return;
    }

    let mut run_start = start_char;
    while run_start > 0 && is_cjk_name_char(chars[run_start - 1]) {
        run_start -= 1;
    }
    let mut run_end = end_char;
    while run_end < chars.len() && is_cjk_name_char(chars[run_end]) {
        run_end += 1;
    }
    let max_prefix = usize::min(start_char.saturating_sub(run_start), extension_budget);
    let max_suffix = usize::min(run_end.saturating_sub(end_char), extension_budget);
    let allow_prefix_extensions = allows_prefix_local_extensions(seed_surface);
    let allow_suffix_extensions = allows_suffix_local_extensions(seed_surface);
    let allow_bidirectional = allows_bidirectional_local_extensions(seed_surface);

    for prefix_extra in 0..=max_prefix {
        for suffix_extra in 0..=max_suffix {
            if prefix_extra == 0 && suffix_extra == 0 {
                continue;
            }
            if prefix_extra + suffix_extra > extension_budget {
                continue;
            }
            if prefix_extra > 0 && !allow_prefix_extensions {
                continue;
            }
            if suffix_extra > 0 && !allow_suffix_extensions {
                continue;
            }
            if prefix_extra > 0 && suffix_extra > 0 && !allow_bidirectional {
                continue;
            }
            if !allows_specific_local_extension(
                seed_surface,
                prefix_extra,
                suffix_extra,
                chars.get(end_char).copied(),
            ) {
                continue;
            }

            let surface_start = start_char - prefix_extra;
            let surface_end = end_char + suffix_extra;
            let surface = &block_text[char_starts[surface_start]..char_starts[surface_end]];
            record_surface_occurrence(
                surface,
                surface_start,
                surface_end,
                block_idx,
                chars,
                surface_id_by_name,
                surface_names,
                accumulators,
                surface_blocks,
                seen_in_block,
                seen_occurrences,
                common_words,
                false,
            );
        }
    }
}

fn record_surface_occurrence(
    surface: &str,
    start_char: usize,
    end_char: usize,
    _block_idx: usize,
    chars: &[char],
    surface_id_by_name: &mut FxHashMap<String, usize>,
    surface_names: &mut Vec<String>,
    accumulators: &mut Vec<BlockSurfaceAccumulator>,
    surface_blocks: &mut Vec<Vec<usize>>,
    seen_in_block: &mut FxHashSet<usize>,
    seen_occurrences: &mut FxHashSet<(usize, usize, usize)>,
    common_words: &FxHashSet<String>,
    trust_seed_surface: bool,
) {
    if surface.is_empty() {
        return;
    }
    if !trust_seed_surface && is_low_value_surface(surface, common_words) {
        return;
    }

    let surface_id = get_or_insert_surface_id(
        surface,
        surface_id_by_name,
        surface_names,
        accumulators,
    );
    if surface_blocks.len() <= surface_id {
        surface_blocks.resize_with(surface_id + 1, Vec::new);
    }
    if !seen_occurrences.insert((surface_id, start_char, end_char)) {
        return;
    }

    let left_boundary = if start_char == 0 {
        BoundarySymbol::Start
    } else {
        normalize_boundary_symbol(chars[start_char - 1])
    };
    let right_boundary = if end_char >= chars.len() {
        BoundarySymbol::End
    } else {
        normalize_boundary_symbol(chars[end_char])
    };
    let accumulator = &mut accumulators[surface_id];
    accumulator.raw_occurrences += 1;
    *accumulator.left_contexts.entry(left_boundary).or_insert(0) += 1;
    *accumulator.right_contexts.entry(right_boundary).or_insert(0) += 1;
    seen_in_block.insert(surface_id);
}

fn local_extension_budget(surface: &str, char_len: usize) -> usize {
    if char_len == 0 {
        return 0;
    }
    if is_translit_extension_seed(surface)
        || is_zh_compound_surname(surface)
        || is_generic_two_char_extension_seed(surface)
    {
        ZH_BLOCK_LOCAL_EXTENSION_MAX_EXTRA_CHARS
    } else if looks_like_person_like_surface(surface) {
        1
    } else {
        1
    }
}

fn looks_like_person_extension_seed(surface: &str) -> bool {
    looks_like_person_like_surface(surface) || is_zh_compound_surname(surface)
}

fn is_generic_two_char_extension_seed(surface: &str) -> bool {
    surface.chars().count() == 2
        && !looks_like_person_extension_seed(surface)
        && !is_translit_extension_seed(surface)
}

fn has_low_value_generic_prefix(surface: &str) -> bool {
    surface.chars().next().is_some_and(|ch| {
        ZH_BLOCK_GENERIC_MODIFIER_PREFIX_CHARS.contains(ch)
            || ZH_BLOCK_LOW_VALUE_PREFIX_CHARS.contains(ch)
            || ZH_BLOCK_TWO_CHAR_FUNCTION_CHARS.contains(ch)
    })
}

fn is_trusted_low_entropy_suffix_extension(
    surface: &str,
    seed_name_set: &FxHashSet<String>,
) -> bool {
    let char_len = surface.chars().count();
    if !(3..=4).contains(&char_len) {
        return false;
    }

    for removed_chars in 1..=2 {
        if char_len <= removed_chars {
            continue;
        }
        let Some(seed_surface) = prefix_chars(surface, char_len - removed_chars) else {
            continue;
        };
        if !seed_name_set.contains(seed_surface) || !is_generic_two_char_extension_seed(seed_surface)
        {
            continue;
        }
        if !has_low_value_generic_prefix(seed_surface) {
            return true;
        }
        let Some(added_fragment) =
            suffix_after_removing_prefix_chars(surface, seed_surface.chars().count())
        else {
            continue;
        };
        if added_fragment
            .chars()
            .next()
            .is_some_and(|ch| ZH_BLOCK_GENERIC_ROLE_SUFFIX_CHARS.contains(ch))
        {
            return true;
        }
    }

    false
}

fn allows_suffix_local_extensions(surface: &str) -> bool {
    looks_like_person_extension_seed(surface)
        || is_translit_extension_seed(surface)
        || is_generic_two_char_extension_seed(surface)
}

fn allows_prefix_local_extensions(surface: &str) -> bool {
    if is_translit_extension_seed(surface) || is_zh_name_suffix_title(surface) {
        return true;
    }
    !looks_like_person_extension_seed(surface)
        && surface.chars().count() <= 3
}

fn allows_bidirectional_local_extensions(surface: &str) -> bool {
    is_translit_extension_seed(surface) || is_zh_name_suffix_title(surface)
}

fn is_translit_extension_seed(surface: &str) -> bool {
    surface.chars().count() <= ZH_FRAGMENT_MAX_TOKEN_CHARS
        && looks_like_zh_translit_fragment(surface)
}

fn allows_specific_local_extension(
    seed_surface: &str,
    prefix_extra: usize,
    suffix_extra: usize,
    next_char: Option<char>,
) -> bool {
    if prefix_extra > 0 && suffix_extra > 0 {
        return true;
    }
    if suffix_extra == 0 {
        return true;
    }
    if is_zh_compound_surname(seed_surface) || is_translit_extension_seed(seed_surface) {
        return true;
    }
    if is_generic_two_char_extension_seed(seed_surface) {
        return next_char.is_some_and(|ch| {
            !ZH_BLOCK_TWO_CHAR_FUNCTION_CHARS.contains(ch)
                && !ZH_BLOCK_LOW_VALUE_SUFFIX_CHARS.contains(ch)
                && !is_zh_name_trailing_block_char(ch)
                && (!has_low_value_generic_prefix(seed_surface)
                    || ZH_BLOCK_GENERIC_ROLE_SUFFIX_CHARS.contains(ch))
        });
    }
    if !looks_like_person_like_surface(seed_surface) {
        return true;
    }
    next_char.is_some_and(|ch| {
        ZH_BLOCK_TWO_CHAR_FUNCTION_CHARS.contains(ch)
            || ZH_BLOCK_LOW_VALUE_SUFFIX_CHARS.contains(ch)
            || is_zh_name_trailing_block_char(ch)
    })
}

fn segment_chapters_into_blocks_from_strings<T>(chapters: T) -> Vec<NarrativeBlock>
where
    T: IntoIterator,
    T::Item: AsRef<str>,
{
    let mut blocks = Vec::new();
    let mut char_starts = Vec::new();

    for (chapter_idx, chapter) in chapters.into_iter().enumerate() {
        let normalized = normalize_chapter_text(chapter.as_ref());
        if normalized.is_empty() {
            continue;
        }
        collect_char_starts_into(&normalized, &mut char_starts);
        let segments = segment_chapter_text_without_index(
            (chapter_idx + 1) as i64,
            (chapter_idx + 1) as i64,
            &normalized,
        );
        for segment in segments {
            let start_char = segment.start_pos.max(0) as usize;
            let end_char = segment.end_pos.max(0) as usize;
            if start_char >= end_char || end_char >= char_starts.len() {
                continue;
            }
            let block_text = normalized[char_starts[start_char]..char_starts[end_char]].trim();
            if block_text.is_empty() {
                continue;
            }
            blocks.push(NarrativeBlock {
                text: block_text.to_owned(),
            });
        }
    }

    blocks
}

fn get_or_insert_surface_id(
    surface: &str,
    surface_id_by_name: &mut FxHashMap<String, usize>,
    surface_names: &mut Vec<String>,
    accumulators: &mut Vec<BlockSurfaceAccumulator>,
) -> usize {
    if let Some(&surface_id) = surface_id_by_name.get(surface) {
        return surface_id;
    }
    let owned = surface.to_owned();
    let surface_id = surface_names.len();
    surface_id_by_name.insert(owned.clone(), surface_id);
    surface_names.push(owned);
    accumulators.push(BlockSurfaceAccumulator::default());
    surface_id
}

fn normalize_boundary_symbol(ch: char) -> BoundarySymbol {
    if ch.is_whitespace() {
        BoundarySymbol::Whitespace
    } else if !ch.is_alphanumeric() && !is_cjk_name_char(ch) {
        BoundarySymbol::Punctuation
    } else if is_cjk_name_char(ch) || ch.is_alphanumeric() {
        BoundarySymbol::Char(ch)
    } else {
        BoundarySymbol::Other
    }
}

fn entropy(counter: &FxHashMap<BoundarySymbol, CandidateCount>) -> f64 {
    let total = counter.values().map(|count| *count as usize).sum::<usize>();
    if total == 0 {
        return 0.0;
    }
    counter
        .values()
        .filter(|count| **count > 0)
        .map(|count| {
            let probability = (*count as f64) / (total as f64);
            -probability * probability.log2()
        })
        .sum()
}

fn is_low_value_surface(surface: &str, common_words: &FxHashSet<String>) -> bool {
    if surface.is_empty() {
        return true;
    }
    if common_words.contains(surface) {
        return true;
    }
    if all_same_chars(surface) {
        return true;
    }

    let char_len = surface.chars().count();
    if char_len == 2 && !looks_like_two_char_name(surface) {
        let first_char = surface.chars().next().unwrap_or_default();
        let last_char = surface.chars().last().unwrap_or_default();
        if !ZH_BLOCK_TWO_CHAR_HINT_SUFFIXES.contains(last_char)
            && (ZH_BLOCK_TWO_CHAR_FUNCTION_CHARS.contains(first_char)
                || ZH_BLOCK_TWO_CHAR_FUNCTION_CHARS.contains(last_char))
        {
            return true;
        }
    }

    if char_len <= 4
        && surface
            .chars()
            .any(|ch| ZH_BLOCK_LOW_VALUE_INTERIOR_CHARS.contains(ch))
        && !looks_like_zh_person_name(surface)
    {
        return true;
    }

    if char_len >= 3
        && surface
            .chars()
            .next()
            .is_some_and(|ch| ZH_BLOCK_LOW_VALUE_PREFIX_CHARS.contains(ch))
    {
        return true;
    }

    if char_len >= 3
        && surface
            .chars()
            .last()
            .is_some_and(|ch| ZH_BLOCK_LOW_VALUE_SUFFIX_CHARS.contains(ch))
    {
        return true;
    }

    false
}

fn all_same_chars(value: &str) -> bool {
    let mut chars = value.chars();
    let Some(first) = chars.next() else {
        return true;
    };
    chars.all(|ch| ch == first)
}

fn looks_like_two_char_name(surface: &str) -> bool {
    if surface.chars().count() != 2 {
        return false;
    }
    let mut chars = surface.chars();
    let Some(first_char) = chars.next() else {
        return false;
    };
    let Some(last_char) = chars.next() else {
        return false;
    };
    chars.next().is_none()
        && (is_zh_single_surname_char(first_char)
            || ZH_BLOCK_EXTRA_SINGLE_SURNAMES.contains(first_char))
        && !ZH_BLOCK_TWO_CHAR_FUNCTION_CHARS.contains(last_char)
}

fn looks_like_person_like_surface(surface: &str) -> bool {
    looks_like_zh_person_name(surface) || looks_like_two_char_name(surface)
}

fn is_zh_single_surname_char(ch: char) -> bool {
    ZH_SINGLE_SURNAMES.trim().contains(ch)
}

fn zh_variant_char_map() -> &'static FxHashMap<char, char> {
    static VARIANT_CHAR_MAP: OnceLock<FxHashMap<char, char>> = OnceLock::new();
    VARIANT_CHAR_MAP.get_or_init(|| {
        ZH_VARIANT_CHAR_LINES
            .lines()
            .filter_map(|line| {
                let trimmed = line.trim();
                if trimmed.is_empty() || trimmed.starts_with('#') {
                    return None;
                }
                let mut parts = trimmed.split('\t');
                let src = parts.next()?.trim();
                let dst = parts.next()?.trim();
                if parts.next().is_some() || src.chars().count() != 1 || dst.chars().count() != 1
                {
                    return None;
                }
                Some((src.chars().next()?, dst.chars().next()?))
            })
            .collect()
    })
}

fn normalize_zh_variant_chars(value: &str) -> Cow<'_, str> {
    if value.is_empty() {
        return Cow::Borrowed(value);
    }

    let variant_map = zh_variant_char_map();
    if variant_map.is_empty() {
        return Cow::Borrowed(value);
    }

    let mut changed = false;
    let mut normalized = String::with_capacity(value.len());
    for ch in value.chars() {
        let mapped = variant_map.get(&ch).copied().unwrap_or(ch);
        changed |= mapped != ch;
        normalized.push(mapped);
    }

    if changed {
        Cow::Owned(normalized)
    } else {
        Cow::Borrowed(value)
    }
}

fn normalize_zh_chapter_strings(chapters: Vec<PyBackedStr>) -> Vec<String> {
    chapters
        .into_iter()
        .map(|chapter| normalize_zh_variant_chars(chapter.as_ref()).into_owned())
        .collect()
}

fn surface_discovery_score(
    surface: &str,
    char_len: usize,
    raw_occurrences: usize,
    block_count: usize,
    left_entropy: f64,
    right_entropy: f64,
) -> f64 {
    left_entropy.min(right_entropy) * 2.0
        + (raw_occurrences as f64 + 1.0).ln() * 2.2
        + (block_count as f64 + 1.0).ln() * 2.8
        + surface_shape_bonus(surface, char_len)
}

fn surface_shape_bonus(surface: &str, char_len: usize) -> f64 {
    let mut bonus = 0.0;
    if looks_like_person_like_surface(surface) {
        bonus += 3.0;
    }
    if char_len >= 3 {
        bonus += 1.0;
    } else if surface
        .chars()
        .last()
        .is_some_and(|ch| ZH_BLOCK_TWO_CHAR_HINT_SUFFIXES.contains(ch))
    {
        bonus += 1.25;
    } else {
        bonus -= 1.0;
    }
    if strip_zh_person_name_trailing_noise(surface).is_some() {
        bonus -= 1.5;
    }
    bonus
}

fn build_canonical_candidates(
    surface_names: &[String],
    surface_stats: &[RepeatedSpanSurfaceStat],
    surface_blocks: &[Vec<usize>],
) -> Vec<CanonicalCandidate> {
    if surface_stats.is_empty() {
        return Vec::new();
    }

    let stats_by_id: FxHashMap<usize, &RepeatedSpanSurfaceStat> = surface_stats
        .iter()
        .map(|stat| (stat.surface_id, stat))
        .collect();
    let surface_id_by_name: FxHashMap<String, usize> = surface_names
        .iter()
        .enumerate()
        .map(|(surface_id, surface)| (surface.clone(), surface_id))
        .collect();
    let mut dominant_extensions = dominant_extension_map(
        surface_names,
        surface_stats,
        &stats_by_id,
        &surface_id_by_name,
        surface_blocks,
    );
    dominant_extensions.extend(generic_surface_family_map(
        surface_names,
        surface_stats,
        &stats_by_id,
        &surface_id_by_name,
        surface_blocks,
    ));
    dominant_extensions.extend(low_value_affix_surface_map(
        surface_names,
        &surface_id_by_name,
    ));

    let mut grouped_surfaces: FxHashMap<usize, Vec<usize>> = FxHashMap::default();
    for stat in surface_stats {
        let canonical_id = resolve_canonical_surface(stat.surface_id, &dominant_extensions);
        grouped_surfaces
            .entry(canonical_id)
            .or_default()
            .push(stat.surface_id);
    }

    let mut canonical_candidates = Vec::new();
    for (canonical_id, mut cluster_surface_ids) in grouped_surfaces {
        let mut cluster_blocks: FxHashSet<usize> = FxHashSet::default();
        let mut raw_occurrences = 0usize;
        let mut discovery_score = 0.0f64;
        for surface_id in &cluster_surface_ids {
            if let Some(stat) = stats_by_id.get(surface_id) {
                raw_occurrences += stat.raw_occurrences;
                discovery_score = discovery_score.max(stat.discovery_score);
            }
            for block_id in &surface_blocks[*surface_id] {
                cluster_blocks.insert(*block_id);
            }
        }
        let block_count = cluster_blocks.len();
        if block_count < ZH_BLOCK_MIN_BLOCKS {
            continue;
        }
        cluster_surface_ids.sort_unstable_by(|left, right| {
            let left_stat = stats_by_id
                .get(left)
                .copied()
                .expect("missing left surface stat");
            let right_stat = stats_by_id
                .get(right)
                .copied()
                .expect("missing right surface stat");
            (*left != canonical_id)
                .cmp(&(*right != canonical_id))
                .then_with(|| right_stat.discovery_score.total_cmp(&left_stat.discovery_score))
                .then_with(|| right_stat.char_len.cmp(&left_stat.char_len))
                .then_with(|| surface_names[*left].cmp(&surface_names[*right]))
        });
        let importance = block_count + usize::min(raw_occurrences / 2, block_count);
        canonical_candidates.push(CanonicalCandidate {
            canonical_id,
            importance,
            block_count,
            discovery_score: discovery_score
                + (cluster_surface_ids.len().saturating_sub(1) as f64) * 0.1,
            surface_ids: cluster_surface_ids,
        });
    }

    canonical_candidates.sort_unstable_by(|left, right| {
        let left_len = stats_by_id
            .get(&left.canonical_id)
            .map(|stat| stat.char_len)
            .unwrap_or(0);
        let right_len = stats_by_id
            .get(&right.canonical_id)
            .map(|stat| stat.char_len)
            .unwrap_or(0);
        right
            .discovery_score
            .total_cmp(&left.discovery_score)
            .then_with(|| right.importance.cmp(&left.importance))
            .then_with(|| right.block_count.cmp(&left.block_count))
            .then_with(|| right_len.cmp(&left_len))
            .then_with(|| surface_names[left.canonical_id].cmp(&surface_names[right.canonical_id]))
    });

    canonical_candidates
}

fn low_value_affix_surface_map(
    surface_names: &[String],
    surface_id_by_name: &FxHashMap<String, usize>,
) -> FxHashMap<usize, usize> {
    let mut families = FxHashMap::default();

    for (surface_id, surface) in surface_names.iter().enumerate() {
        let char_len = surface.chars().count();
        if char_len < 3 {
            continue;
        }

        let first_char = surface.chars().next().unwrap_or_default();
        if ZH_BLOCK_GENERIC_MODIFIER_PREFIX_CHARS.contains(first_char)
            || ZH_BLOCK_LOW_VALUE_PREFIX_CHARS.contains(first_char)
            || ZH_BLOCK_TWO_CHAR_FUNCTION_CHARS.contains(first_char)
        {
            if let Some(stripped) = suffix_after_removing_prefix_chars(surface, 1) {
                if let Some(&canonical_id) = surface_id_by_name.get(stripped) {
                    families.insert(surface_id, canonical_id);
                    continue;
                }
            }
        }

        let last_char = surface.chars().last().unwrap_or_default();
        if ZH_BLOCK_LOW_VALUE_SUFFIX_CHARS.contains(last_char)
            || ZH_BLOCK_TWO_CHAR_FUNCTION_CHARS.contains(last_char)
            || is_zh_name_trailing_block_char(last_char)
        {
            if let Some(stripped) = prefix_chars(surface, char_len - 1) {
                if let Some(&canonical_id) = surface_id_by_name.get(stripped) {
                    families.insert(surface_id, canonical_id);
                }
            }
        }
    }

    families
}

fn dominant_extension_map(
    surface_names: &[String],
    surface_stats: &[RepeatedSpanSurfaceStat],
    stats_by_id: &FxHashMap<usize, &RepeatedSpanSurfaceStat>,
    surface_id_by_name: &FxHashMap<String, usize>,
    surface_blocks: &[Vec<usize>],
) -> FxHashMap<usize, usize> {
    let person_extension_options =
        build_person_extension_options(surface_names, surface_id_by_name);
    let mut dominant = FxHashMap::default();

    for stat in surface_stats {
        let surface_id = stat.surface_id;
        let surface = surface_names[surface_id].as_str();
        let blocks = &surface_blocks[surface_id];
        if blocks.is_empty() {
            continue;
        }

        if let Some(canonical) = strip_zh_person_name_trailing_noise(surface) {
            if let Some(&canonical_id) = surface_id_by_name.get(canonical) {
                dominant.insert(surface_id, canonical_id);
                continue;
            }
        }

        if blocks.len() <= 1 || !looks_like_person_like_surface(surface) {
            continue;
        }

        let mut seen_options: FxHashSet<usize> = FxHashSet::default();
        let mut options: Vec<(f64, f64, usize)> = Vec::new();
        if let Some(candidate_ids) = person_extension_options.get(&surface_id) {
            for &other_id in candidate_ids {
                if !seen_options.insert(other_id) || other_id == surface_id {
                    continue;
                }
                let other_surface = surface_names[other_id].as_str();
                if strip_zh_person_name_trailing_noise(other_surface) == Some(surface) {
                    continue;
                }
                let Some(other_stat) = stats_by_id.get(&other_id).copied() else {
                    continue;
                };
                if other_stat.left_entropy.min(other_stat.right_entropy)
                    < ZH_BLOCK_MIN_BOUNDARY_ENTROPY
                {
                    continue;
                }
                let overlap = count_sorted_overlap(blocks, &surface_blocks[other_id]);
                if overlap == 0 {
                    continue;
                }
                let containment = overlap as f64 / blocks.len().max(1) as f64;
                if containment < ZH_BLOCK_MIN_EXTENSION_CONTAINMENT {
                    continue;
                }
                let specificity = other_stat.discovery_score
                    + (other_stat.char_len.saturating_sub(stat.char_len) as f64) * 0.5;
                options.push((specificity, containment, other_id));
            }
        }
        if options.is_empty() {
            continue;
        }

        options.sort_unstable_by(|left, right| {
            let left_stat = stats_by_id
                .get(&left.2)
                .copied()
                .expect("missing dominant left stat");
            let right_stat = stats_by_id
                .get(&right.2)
                .copied()
                .expect("missing dominant right stat");
            right
                .0
                .total_cmp(&left.0)
                .then_with(|| right.1.total_cmp(&left.1))
                .then_with(|| right_stat.char_len.cmp(&left_stat.char_len))
                .then_with(|| surface_names[left.2].cmp(&surface_names[right.2]))
        });
        let best_score = options[0].0;
        let second_score = options.get(1).map(|item| item.0).unwrap_or(f64::NEG_INFINITY);
        if best_score - second_score < ZH_BLOCK_MIN_EXTENSION_SCORE_MARGIN {
            continue;
        }
        dominant.insert(surface_id, options[0].2);
    }

    dominant
}

fn generic_surface_family_map(
    surface_names: &[String],
    surface_stats: &[RepeatedSpanSurfaceStat],
    stats_by_id: &FxHashMap<usize, &RepeatedSpanSurfaceStat>,
    surface_id_by_name: &FxHashMap<String, usize>,
    surface_blocks: &[Vec<usize>],
) -> FxHashMap<usize, usize> {
    let (prefix_extensions, suffix_extensions) =
        build_one_char_extension_options(surface_names, surface_id_by_name);
    let mut families = FxHashMap::default();

    for stat in surface_stats {
        let surface_id = stat.surface_id;
        if families.contains_key(&surface_id) || looks_like_zh_person_name(&surface_names[surface_id]) {
            continue;
        }

        if let Some(best_prefix_extension) = best_generic_extension(
            surface_id,
            true,
            &prefix_extensions,
            stats_by_id,
            surface_names,
            surface_blocks,
        ) {
            let prefix_char = surface_names[best_prefix_extension]
                .chars()
                .next()
                .unwrap_or_default();
            if ZH_BLOCK_GENERIC_MODIFIER_PREFIX_CHARS.contains(prefix_char)
                || ZH_BLOCK_LOW_VALUE_PREFIX_CHARS.contains(prefix_char)
                || ZH_BLOCK_TWO_CHAR_FUNCTION_CHARS.contains(prefix_char)
            {
                families.insert(best_prefix_extension, surface_id);
            } else {
                families.insert(surface_id, best_prefix_extension);
            }
            continue;
        }

        if let Some(best_suffix_extension) = best_generic_extension(
            surface_id,
            false,
            &suffix_extensions,
            stats_by_id,
            surface_names,
            surface_blocks,
        ) {
            let suffix_char = surface_names[best_suffix_extension]
                .chars()
                .last()
                .unwrap_or_default();
            if ZH_BLOCK_LOW_VALUE_SUFFIX_CHARS.contains(suffix_char)
                || ZH_BLOCK_TWO_CHAR_FUNCTION_CHARS.contains(suffix_char)
                || is_zh_name_trailing_block_char(suffix_char)
            {
                families.insert(best_suffix_extension, surface_id);
            } else {
                families.insert(surface_id, best_suffix_extension);
            }
        }
    }

    families
}

fn best_generic_extension(
    surface_id: usize,
    choose_prefix_extension: bool,
    extension_options: &FxHashMap<usize, Vec<usize>>,
    stats_by_id: &FxHashMap<usize, &RepeatedSpanSurfaceStat>,
    surface_names: &[String],
    surface_blocks: &[Vec<usize>],
) -> Option<usize> {
    let stat = stats_by_id.get(&surface_id).copied()?;
    let blocks = &surface_blocks[surface_id];
    if stat.char_len < 2 || blocks.is_empty() {
        return None;
    }

    let directional_entropy = if choose_prefix_extension {
        stat.left_entropy
    } else {
        stat.right_entropy
    };
    if directional_entropy > ZH_BLOCK_FRAGMENT_DIRECTIONAL_ENTROPY_MAX {
        return None;
    }

    let mut seen_options: FxHashSet<usize> = FxHashSet::default();
    let mut options: Vec<(f64, usize, usize)> = Vec::new();
    if let Some(candidate_ids) = extension_options.get(&surface_id) {
        for &other_id in candidate_ids {
            if !seen_options.insert(other_id) || other_id == surface_id {
                continue;
            }
            let overlap = count_sorted_overlap(blocks, &surface_blocks[other_id]);
            let containment = overlap as f64 / blocks.len().max(1) as f64;
            if containment < ZH_BLOCK_FRAGMENT_EXTENSION_MIN_CONTAINMENT {
                continue;
            }
            options.push((containment, overlap, other_id));
        }
    }
    if options.is_empty() {
        return None;
    }

    options.sort_unstable_by(|left, right| {
        let left_len = stats_by_id
            .get(&left.2)
            .map(|stat| stat.char_len)
            .unwrap_or(0);
        let right_len = stats_by_id
            .get(&right.2)
            .map(|stat| stat.char_len)
            .unwrap_or(0);
        right
            .0
            .total_cmp(&left.0)
            .then_with(|| right.1.cmp(&left.1))
            .then_with(|| right_len.cmp(&left_len))
            .then_with(|| surface_names[left.2].cmp(&surface_names[right.2]))
    });
    let best_surface = options[0].2;
    let best_overlap = options[0].1;
    let second_overlap = options.get(1).map(|item| item.1).unwrap_or(0);
    if second_overlap > 0
        && (second_overlap as f64 / best_overlap.max(1) as f64)
            >= ZH_BLOCK_FRAGMENT_EXTENSION_MAX_SECONDARY_RATIO
    {
        return None;
    }
    Some(best_surface)
}

fn build_person_extension_options(
    surface_names: &[String],
    surface_id_by_name: &FxHashMap<String, usize>,
) -> FxHashMap<usize, Vec<usize>> {
    let mut options: FxHashMap<usize, Vec<usize>> = FxHashMap::default();

    for (other_id, other_name) in surface_names.iter().enumerate() {
        if !looks_like_zh_person_name(other_name) {
            continue;
        }
        let char_len = other_name.chars().count();
        for removed_chars in 1..=2 {
            if char_len <= removed_chars {
                continue;
            }
            let mut seen_short_ids: FxHashSet<usize> = FxHashSet::default();
            if let Some(short_name) = prefix_chars(other_name, char_len - removed_chars) {
                if let Some(&short_id) = surface_id_by_name.get(short_name) {
                    if seen_short_ids.insert(short_id) {
                        options.entry(short_id).or_default().push(other_id);
                    }
                }
            }
            if let Some(short_name) = suffix_after_removing_prefix_chars(other_name, removed_chars) {
                if let Some(&short_id) = surface_id_by_name.get(short_name) {
                    if seen_short_ids.insert(short_id) {
                        options.entry(short_id).or_default().push(other_id);
                    }
                }
            }
        }
    }

    options
}

fn build_one_char_extension_options(
    surface_names: &[String],
    surface_id_by_name: &FxHashMap<String, usize>,
) -> (FxHashMap<usize, Vec<usize>>, FxHashMap<usize, Vec<usize>>) {
    let mut prefix_extensions: FxHashMap<usize, Vec<usize>> = FxHashMap::default();
    let mut suffix_extensions: FxHashMap<usize, Vec<usize>> = FxHashMap::default();

    for (other_id, other_name) in surface_names.iter().enumerate() {
        let char_len = other_name.chars().count();
        if char_len <= 1 {
            continue;
        }
        if let Some(short_name) = suffix_after_removing_prefix_chars(other_name, 1) {
            if let Some(&short_id) = surface_id_by_name.get(short_name) {
                prefix_extensions.entry(short_id).or_default().push(other_id);
            }
        }
        if let Some(short_name) = prefix_chars(other_name, char_len - 1) {
            if let Some(&short_id) = surface_id_by_name.get(short_name) {
                suffix_extensions.entry(short_id).or_default().push(other_id);
            }
        }
    }

    (prefix_extensions, suffix_extensions)
}

fn resolve_canonical_surface(
    surface_id: usize,
    dominant_extensions: &FxHashMap<usize, usize>,
) -> usize {
    let mut current = surface_id;
    let mut seen: FxHashSet<usize> = FxHashSet::default();
    seen.insert(current);
    while let Some(next) = dominant_extensions.get(&current).copied() {
        if !seen.insert(next) {
            break;
        }
        current = next;
    }
    current
}

fn compact_selected_candidates_output(
    surface_names: &[String],
    selected_candidates: &[CanonicalCandidate],
    block_present_surfaces: &[Vec<usize>],
) -> (
    Vec<String>,
    Vec<(usize, usize)>,
    Vec<(usize, usize, usize)>,
    Vec<(usize, Vec<usize>)>,
) {
    if selected_candidates.is_empty() {
        return (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    }

    let mut surface_to_canonical = vec![None; surface_names.len()];
    for candidate in selected_candidates {
        for &surface_id in &candidate.surface_ids {
            surface_to_canonical[surface_id] = Some(candidate.canonical_id);
        }
    }

    let mut pair_counts: FxHashMap<(usize, usize), usize> = FxHashMap::default();
    let mut present_canonicals = Vec::new();
    for present_surface_ids in block_present_surfaces {
        present_canonicals.clear();
        for &surface_id in present_surface_ids {
            if let Some(canonical_id) = surface_to_canonical[surface_id] {
                present_canonicals.push(canonical_id);
            }
        }
        if present_canonicals.len() < 2 {
            continue;
        }
        present_canonicals.sort_unstable();
        present_canonicals.dedup();
        for index in 0..present_canonicals.len() {
            let left_id = present_canonicals[index];
            for &right_id in &present_canonicals[index + 1..] {
                *pair_counts.entry((left_id, right_id)).or_insert(0) += 1;
            }
        }
    }

    let mut local_to_compact = vec![usize::MAX; surface_names.len()];
    let mut compact_names = Vec::new();
    let mut importance_items = Vec::with_capacity(selected_candidates.len());
    let mut canonical_surface_items = Vec::with_capacity(selected_candidates.len());

    for candidate in selected_candidates {
        let compact_canonical_id = ensure_compact_surface_id(
            candidate.canonical_id,
            surface_names,
            &mut local_to_compact,
            &mut compact_names,
        );
        importance_items.push((compact_canonical_id, candidate.importance));
        let mut compact_surface_ids = Vec::with_capacity(candidate.surface_ids.len());
        for &surface_id in &candidate.surface_ids {
            compact_surface_ids.push(ensure_compact_surface_id(
                surface_id,
                surface_names,
                &mut local_to_compact,
                &mut compact_names,
            ));
        }
        canonical_surface_items.push((compact_canonical_id, compact_surface_ids));
    }

    let mut pair_items = pair_counts.into_iter().collect::<Vec<_>>();
    pair_items.sort_unstable_by(|left, right| {
        right
            .1
            .cmp(&left.1)
            .then_with(|| surface_names[left.0 .0].cmp(&surface_names[right.0 .0]))
            .then_with(|| surface_names[left.0 .1].cmp(&surface_names[right.0 .1]))
    });
    let compact_pairs = pair_items
        .into_iter()
        .map(|((left_id, right_id), count)| {
            (
                ensure_compact_surface_id(
                    left_id,
                    surface_names,
                    &mut local_to_compact,
                    &mut compact_names,
                ),
                ensure_compact_surface_id(
                    right_id,
                    surface_names,
                    &mut local_to_compact,
                    &mut compact_names,
                ),
                count,
            )
        })
        .collect();

    (
        compact_names,
        importance_items,
        compact_pairs,
        canonical_surface_items,
    )
}

fn ensure_compact_surface_id(
    surface_id: usize,
    surface_names: &[String],
    local_to_compact: &mut [usize],
    compact_names: &mut Vec<String>,
) -> usize {
    if local_to_compact[surface_id] != usize::MAX {
        return local_to_compact[surface_id];
    }
    let compact_id = compact_names.len();
    compact_names.push(surface_names[surface_id].clone());
    local_to_compact[surface_id] = compact_id;
    compact_id
}

fn count_sorted_overlap(left: &[usize], right: &[usize]) -> usize {
    let mut left_idx = 0usize;
    let mut right_idx = 0usize;
    let mut overlap = 0usize;
    while left_idx < left.len() && right_idx < right.len() {
        match left[left_idx].cmp(&right[right_idx]) {
            std::cmp::Ordering::Less => left_idx += 1,
            std::cmp::Ordering::Greater => right_idx += 1,
            std::cmp::Ordering::Equal => {
                overlap += 1;
                left_idx += 1;
                right_idx += 1;
            }
        }
    }
    overlap
}

fn suffix_after_removing_prefix_chars(value: &str, count: usize) -> Option<&str> {
    if count == 0 {
        return Some(value);
    }
    let mut seen = 0usize;
    for (byte_idx, ch) in value.char_indices() {
        seen += 1;
        if seen == count {
            return Some(&value[byte_idx + ch.len_utf8()..]);
        }
    }
    None
}

fn count_zh_candidates_impl(
    chapters: Vec<PyBackedStr>,
    common_words: Vec<PyBackedStr>,
    max_batch_chars: usize,
) -> Result<Vec<(String, usize)>, String> {
    let mut sorted_counts = collect_candidate_counts(chapters, common_words, max_batch_chars);
    sort_candidate_counts(&mut sorted_counts);
    release_zh_tokenizer();
    Ok(sorted_counts)
}

fn count_zh_candidates_topk_impl(
    chapters: Vec<PyBackedStr>,
    common_words: Vec<PyBackedStr>,
    max_batch_chars: usize,
    limit: usize,
) -> Result<Vec<(String, usize)>, String> {
    let mut sorted_counts = collect_candidate_counts(chapters, common_words, max_batch_chars);
    truncate_candidate_counts_topk(&mut sorted_counts, limit);
    release_zh_tokenizer();
    Ok(sorted_counts)
}

fn collect_candidate_counts(
    chapters: Vec<PyBackedStr>,
    common_words: Vec<PyBackedStr>,
    max_batch_chars: usize,
) -> Vec<(String, usize)> {
    let normalized_chapters = normalize_zh_chapter_strings(chapters);
    let common_word_set: FxHashSet<String> = common_words
        .into_iter()
        .map(|word| word.to_string())
        .collect();
    collect_candidate_counts_with_common_words(
        normalized_chapters.iter().map(|chapter| chapter.as_str()),
        &common_word_set,
        max_batch_chars,
    )
}

fn collect_candidate_counts_with_common_words<T>(
    chapters: T,
    common_word_set: &FxHashSet<String>,
    max_batch_chars: usize,
) -> Vec<(String, usize)>
where
    T: IntoIterator,
    T::Item: AsRef<str>,
{
    let mut candidate_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();
    let mut recovered_name_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();
    let mut fragment_pair_counts: FxHashMap<(String, String), CandidateCount> =
        FxHashMap::default();
    let mut fragment_outgoing_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();
    let mut fragment_incoming_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();
    let batch_limit = max_batch_chars.max(1);
    let mut batch_text = String::new();

    for chapter in chapters {
        let chapter: &str = chapter.as_ref();
        if chapter.is_empty() {
            continue;
        }
        if chapter.len() >= batch_limit {
            flush_zh_count_batch(
                &mut batch_text,
                common_word_set,
                &mut candidate_counts,
                &mut recovered_name_counts,
                &mut fragment_pair_counts,
                &mut fragment_outgoing_counts,
                &mut fragment_incoming_counts,
            );
            count_zh_batch(
                chapter,
                common_word_set,
                &mut candidate_counts,
                &mut recovered_name_counts,
                &mut fragment_pair_counts,
                &mut fragment_outgoing_counts,
                &mut fragment_incoming_counts,
            );
            continue;
        }

        if !batch_text.is_empty() && batch_text.len() + 2 + chapter.len() > batch_limit {
            flush_zh_count_batch(
                &mut batch_text,
                common_word_set,
                &mut candidate_counts,
                &mut recovered_name_counts,
                &mut fragment_pair_counts,
                &mut fragment_outgoing_counts,
                &mut fragment_incoming_counts,
            );
        }
        if !batch_text.is_empty() {
            batch_text.push('\n');
            batch_text.push('\n');
        }
        batch_text.push_str(chapter);
    }
    flush_zh_count_batch(
        &mut batch_text,
        common_word_set,
        &mut candidate_counts,
        &mut recovered_name_counts,
        &mut fragment_pair_counts,
        &mut fragment_outgoing_counts,
        &mut fragment_incoming_counts,
    );
    merge_recovered_zh_name_counts(&mut candidate_counts, recovered_name_counts);
    recover_bound_zh_fragment_candidates(
        &mut candidate_counts,
        common_word_set,
        fragment_pair_counts,
        fragment_outgoing_counts,
        fragment_incoming_counts,
    );
    merge_zh_person_name_shadow_counts(&mut candidate_counts);

    candidate_counts
        .into_iter()
        .map(|(name, count)| (name, count as usize))
        .collect()
}

fn merge_zh_person_name_shadow_counts(
    candidate_counts: &mut FxHashMap<String, CandidateCount>,
) {
    if candidate_counts.is_empty() {
        return;
    }

    let shadow_entries: Vec<(String, String, CandidateCount)> = candidate_counts
        .iter()
        .filter_map(|(candidate, count)| {
            let canonical = strip_zh_person_name_trailing_noise(candidate)?;
            candidate_counts.contains_key(canonical).then_some((
                candidate.clone(),
                canonical.to_owned(),
                *count,
            ))
        })
        .collect();

    for (shadow, canonical, count) in shadow_entries {
        if shadow == canonical || count == 0 {
            continue;
        }
        if candidate_counts.remove(&shadow).is_none() {
            continue;
        }
        *candidate_counts.entry(canonical).or_insert(0) += count;
    }
}

fn candidate_count_cmp(left: &(String, usize), right: &(String, usize)) -> std::cmp::Ordering {
    right
        .1
        .cmp(&left.1)
        .then_with(|| right.0.chars().count().cmp(&left.0.chars().count()))
        .then_with(|| left.0.cmp(&right.0))
}

fn sort_candidate_counts(items: &mut Vec<(String, usize)>) {
    items.sort_unstable_by(candidate_count_cmp);
}

fn truncate_candidate_counts_topk(items: &mut Vec<(String, usize)>, limit: usize) {
    if limit == 0 {
        items.clear();
        return;
    }
    if items.len() <= limit {
        return;
    }

    let split_index = limit - 1;
    items.select_nth_unstable_by(split_index, candidate_count_cmp);
    items.truncate(limit);
    sort_candidate_counts(items);
}

fn flush_zh_count_batch(
    batch_text: &mut String,
    common_words: &FxHashSet<String>,
    candidate_counts: &mut FxHashMap<String, CandidateCount>,
    recovered_name_counts: &mut FxHashMap<String, CandidateCount>,
    fragment_pair_counts: &mut FxHashMap<(String, String), CandidateCount>,
    fragment_outgoing_counts: &mut FxHashMap<String, CandidateCount>,
    fragment_incoming_counts: &mut FxHashMap<String, CandidateCount>,
) {
    if batch_text.is_empty() {
        return;
    }
    count_zh_batch(
        batch_text.as_str(),
        common_words,
        candidate_counts,
        recovered_name_counts,
        fragment_pair_counts,
        fragment_outgoing_counts,
        fragment_incoming_counts,
    );
    batch_text.clear();
}

fn merge_recovered_zh_name_counts(
    candidate_counts: &mut FxHashMap<String, CandidateCount>,
    recovered_name_counts: FxHashMap<String, CandidateCount>,
) {
    for (candidate, count) in recovered_name_counts {
        if count < ZH_SPLIT_NAME_MIN_COUNT {
            continue;
        }
        match candidate_counts.entry(candidate) {
            std::collections::hash_map::Entry::Occupied(mut entry) => {
                if *entry.get() < count {
                    *entry.get_mut() = count;
                }
            }
            std::collections::hash_map::Entry::Vacant(entry) => {
                entry.insert(count);
            }
        }
    }
}

fn summarize_zh_windows_impl(
    chapters: Vec<PyBackedStr>,
    shortlisted_candidates: Vec<PyBackedStr>,
    window_size: usize,
    window_step: usize,
    threshold: usize,
) -> Result<(Vec<(String, usize)>, Vec<(String, String, usize)>), String> {
    let (candidate_names, importance_items, pair_items) = summarize_zh_windows_compact_impl(
        chapters,
        shortlisted_candidates,
        window_size,
        window_step,
        threshold,
    )?;
    if candidate_names.is_empty() {
        return Ok((Vec::new(), Vec::new()));
    }

    let importance = importance_items
        .into_iter()
        .map(|(candidate_id, count)| (candidate_names[candidate_id].clone(), count))
        .collect();
    let pairs = pair_items
        .into_iter()
        .map(|(left_id, right_id, count)| {
            (
                candidate_names[left_id].clone(),
                candidate_names[right_id].clone(),
                count,
            )
        })
        .collect();
    Ok((importance, pairs))
}

fn summarize_zh_windows_compact_impl(
    chapters: Vec<PyBackedStr>,
    shortlisted_candidates: Vec<PyBackedStr>,
    window_size: usize,
    window_step: usize,
    threshold: usize,
) -> Result<(Vec<String>, Vec<(usize, usize)>, Vec<(usize, usize, usize)>), String> {
    let (candidate_names, importance_counts, pair_counts) = summarize_zh_window_counts_impl(
        chapters,
        shortlisted_candidates,
        window_size,
        window_step,
    )?;
    summarize_zh_window_compact_items(candidate_names, importance_counts, pair_counts, threshold)
}

fn summarize_zh_window_compact_items(
    candidate_names: Vec<String>,
    importance_counts: Vec<usize>,
    pair_counts: Vec<u32>,
    threshold: usize,
) -> Result<(Vec<String>, Vec<(usize, usize)>, Vec<(usize, usize, usize)>), String> {
    if candidate_names.is_empty() {
        return Ok((Vec::new(), Vec::new(), Vec::new()));
    }

    let candidate_count = candidate_names.len();
    let mut included_candidate_ids = Vec::new();
    let mut importance_items = Vec::new();
    for (candidate_id, count) in importance_counts.into_iter().enumerate() {
        if count < threshold {
            continue;
        }
        included_candidate_ids.push(candidate_id);
        importance_items.push((candidate_id, count));
    }
    if importance_items.is_empty() {
        return Ok((Vec::new(), Vec::new(), Vec::new()));
    }

    let included_count = included_candidate_ids.len();
    let max_pair_items = included_count.saturating_mul(included_count.saturating_sub(1)) / 2;
    let mut pair_items: Vec<(usize, usize, usize)> = Vec::with_capacity(max_pair_items);
    for (index, &left_id) in included_candidate_ids.iter().enumerate() {
        let row_offset = left_id * candidate_count;
        for &right_id in &included_candidate_ids[index + 1..] {
            let count = pair_counts[row_offset + right_id] as usize;
            if count > 0 {
                pair_items.push((left_id, right_id, count));
            }
        }
    }
    pair_items.sort_unstable_by(|left, right| {
        right
            .2
            .cmp(&left.2)
            .then_with(|| left.0.cmp(&right.0))
            .then_with(|| left.1.cmp(&right.1))
    });

    Ok((candidate_names, importance_items, pair_items))
}
fn summarize_zh_window_counts_impl(
    chapters: Vec<PyBackedStr>,
    shortlisted_candidates: Vec<PyBackedStr>,
    window_size: usize,
    window_step: usize,
) -> Result<(Vec<String>, Vec<usize>, Vec<u32>), String> {
    let normalized_chapters = normalize_zh_chapter_strings(chapters);
    let mut shortlisted_candidates: Vec<String> = shortlisted_candidates
        .into_iter()
        .map(|candidate| normalize_zh_variant_chars(candidate.as_ref()).into_owned())
        .collect();
    if shortlisted_candidates.is_empty() {
        return Ok((Vec::new(), Vec::new(), Vec::new()));
    }

    shortlisted_candidates.sort_unstable();
    shortlisted_candidates.dedup();
    if shortlisted_candidates.is_empty() {
        return Ok((Vec::new(), Vec::new(), Vec::new()));
    }

    let window_size = window_size.max(1);
    let window_step = window_step.max(1);
    shortlisted_candidates.retain(|candidate| candidate.chars().count() <= window_size);
    if shortlisted_candidates.is_empty() {
        return Ok((Vec::new(), Vec::new(), Vec::new()));
    }

    let candidate_count = shortlisted_candidates.len();
    let candidate_char_lens: Vec<usize> = shortlisted_candidates
        .iter()
        .map(|candidate| candidate.chars().count())
        .collect();
    let pair_matrix_len = candidate_count
        .checked_mul(candidate_count)
        .ok_or_else(|| "candidate matrix too large".to_string())?;
    let automaton =
        AhoCorasick::new(&shortlisted_candidates).map_err(|err| err.to_string())?;
    let ascii_shortlist = shortlisted_candidates
        .iter()
        .all(|candidate| candidate.is_ascii());

    let mut importance_counts = vec![0usize; candidate_count];
    let mut pair_counts = vec![0u32; pair_matrix_len];
    let mut active_counts = vec![0u32; candidate_count];
    let mut active_ids = Vec::new();
    let mut active_listed = vec![false; candidate_count];
    let mut present_ids = Vec::new();
    let mut char_starts = Vec::new();
    let mut chapter_window_starts = Vec::new();
    let mut start_events: Vec<Vec<usize>> = Vec::new();
    let mut end_events: Vec<Vec<usize>> = Vec::new();

    for chapter in normalized_chapters {
        let chapter: &str = chapter.as_str();
        if chapter.trim().is_empty() {
            continue;
        }
        let ascii_chapter = chapter.is_ascii();
        let char_count = if ascii_chapter {
            chapter.len()
        } else {
            collect_char_starts_into(chapter, &mut char_starts);
            char_starts.len().saturating_sub(1)
        };
        if char_count == 0 {
            continue;
        }
        window_starts_into(
            char_count,
            window_size,
            window_step,
            &mut chapter_window_starts,
        );
        if chapter_window_starts.is_empty() {
            continue;
        }
        let window_count = chapter_window_starts.len();
        prepare_event_buckets(&mut start_events, window_count);
        prepare_event_buckets(&mut end_events, window_count + 1);
        if ascii_chapter && ascii_shortlist && candidate_count <= 64 {
            collect_ascii_window_events(
                chapter,
                &shortlisted_candidates,
                &candidate_char_lens,
                window_size,
                &chapter_window_starts,
                &mut start_events,
                &mut end_events,
            );
        } else {
            let mut char_cursor = 0usize;
            for mat in automaton.find_overlapping_iter(chapter) {
                let start_byte = mat.start();
                while char_cursor + 1 < char_starts.len()
                    && char_starts[char_cursor + 1] <= start_byte
                {
                    char_cursor += 1;
                }
                let candidate_id = mat.pattern().as_usize();
                let start_char = char_cursor;
                let end_char = start_char + candidate_char_lens[candidate_id];
                if end_char > char_count {
                    continue;
                }

                let min_window_start = end_char.saturating_sub(window_size);
                let max_window_start = start_char;
                let first_window_idx = chapter_window_starts
                    .partition_point(|&window_start| window_start < min_window_start);
                let end_window_idx = chapter_window_starts
                    .partition_point(|&window_start| window_start <= max_window_start);
                if first_window_idx >= end_window_idx {
                    continue;
                }
                start_events[first_window_idx].push(candidate_id);
                end_events[end_window_idx].push(candidate_id);
            }
        }

        active_ids.clear();
        active_counts.fill(0);
        active_listed.fill(false);
        for window_idx in 0..window_count {
            for &candidate_id in &end_events[window_idx] {
                active_counts[candidate_id] = active_counts[candidate_id]
                    .checked_sub(1)
                    .expect("window activity underflow");
            }
            for &candidate_id in &start_events[window_idx] {
                if !active_listed[candidate_id] {
                    active_ids.push(candidate_id);
                    active_listed[candidate_id] = true;
                }
                active_counts[candidate_id] = active_counts[candidate_id]
                    .checked_add(1)
                    .expect("window activity overflow");
            }

            present_ids.clear();
            let mut write_idx = 0usize;
            for read_idx in 0..active_ids.len() {
                let candidate_id = active_ids[read_idx];
                if active_counts[candidate_id] == 0 {
                    active_listed[candidate_id] = false;
                    continue;
                }
                active_ids[write_idx] = candidate_id;
                write_idx += 1;
                present_ids.push(candidate_id);
            }
            active_ids.truncate(write_idx);
            if present_ids.is_empty() {
                continue;
            }

            present_ids.sort_unstable();
            for (index, &left_id) in present_ids.iter().enumerate() {
                importance_counts[left_id] += 1;
                let row_offset = left_id * candidate_count;
                for &right_id in &present_ids[index + 1..] {
                    let pair_key = row_offset + right_id;
                    pair_counts[pair_key] += 1;
                }
            }
        }
    }

    Ok((shortlisted_candidates, importance_counts, pair_counts))
}

fn collect_ascii_window_events(
    chapter: &str,
    shortlisted_candidates: &[String],
    candidate_char_lens: &[usize],
    window_size: usize,
    chapter_window_starts: &[usize],
    start_events: &mut [Vec<usize>],
    end_events: &mut [Vec<usize>],
) {
    for (candidate_id, candidate) in shortlisted_candidates.iter().enumerate() {
        if candidate.is_empty() {
            continue;
        }
        let mut search_start = 0usize;
        while search_start <= chapter.len() {
            let Some(relative_start) = chapter[search_start..].find(candidate.as_str()) else {
                break;
            };
            let start_char = search_start + relative_start;
            let end_char = start_char + candidate_char_lens[candidate_id];
            let min_window_start = end_char.saturating_sub(window_size);
            let max_window_start = start_char;
            let first_window_idx = chapter_window_starts
                .partition_point(|&window_start| window_start < min_window_start);
            let end_window_idx = chapter_window_starts
                .partition_point(|&window_start| window_start <= max_window_start);
            if first_window_idx < end_window_idx {
                start_events[first_window_idx].push(candidate_id);
                end_events[end_window_idx].push(candidate_id);
            }
            search_start = start_char.saturating_add(1);
        }
    }
}
#[cfg(test)]
fn collect_char_starts(text: &str) -> Vec<usize> {
    let mut char_starts = Vec::new();
    collect_char_starts_into(text, &mut char_starts);
    char_starts
}

fn collect_char_starts_into(text: &str, char_starts: &mut Vec<usize>) {
    char_starts.clear();
    char_starts.extend(text.char_indices().map(|(idx, _)| idx));
    char_starts.push(text.len());
}

fn prepare_event_buckets(buckets: &mut Vec<Vec<usize>>, required_len: usize) {
    if buckets.len() < required_len {
        buckets.resize_with(required_len, Vec::new);
    }
    for bucket in buckets.iter_mut().take(required_len) {
        bucket.clear();
    }
}

fn count_zh_batch(
    text: &str,
    common_words: &FxHashSet<String>,
    candidate_counts: &mut FxHashMap<String, CandidateCount>,
    recovered_name_counts: &mut FxHashMap<String, CandidateCount>,
    fragment_pair_counts: &mut FxHashMap<(String, String), CandidateCount>,
    fragment_outgoing_counts: &mut FxHashMap<String, CandidateCount>,
    fragment_incoming_counts: &mut FxHashMap<String, CandidateCount>,
) {
    let mut batch_counts: FxHashMap<Cow<'_, str>, CandidateCount> = FxHashMap::default();
    let mut tokenizer = None::<std::sync::MutexGuard<'_, Option<Jieba>>>;
    COUNT_RE_HAN_DEFAULT.with(|re_han| {
        COUNT_RE_SKIP_DEFAULT.with(|re_skip| {
            for state in SplitMatches::new(re_han, text) {
                match state {
                    SplitState::Matched(matched) => {
                        let block = matched.as_str();
                        if is_simple_ascii_alnum_block(block) {
                            count_zh_candidate_token(block, common_words, &mut batch_counts);
                            continue;
                        }
                        let tokenizer = tokenizer
                            .get_or_insert_with(|| {
                                zh_tokenizer_state()
                                    .lock()
                                    .expect("zh tokenizer mutex poisoned")
                            })
                            .get_or_insert_with(Jieba::new);
                        let mut previous_cjk_token = None::<String>;
                        let mut previous_fragment_token = None::<String>;
                        for token in tokenizer.cut(block, true) {
                            let normalized = normalize_token(token);
                            count_zh_candidate_token_normalized(
                                normalized.clone(),
                                common_words,
                                &mut batch_counts,
                            );
                            if let Some(left) = previous_cjk_token.as_deref() {
                                if let Some(candidate) =
                                    merge_split_zh_name_tokens(left, normalized.as_ref())
                                {
                                    count_recovered_zh_name_candidate(
                                        candidate,
                                        common_words,
                                        recovered_name_counts,
                                    );
                                }
                            }
                            if is_zh_fragment_token(normalized.as_ref(), common_words) {
                                if let Some(left) = previous_fragment_token.as_deref() {
                                    count_zh_fragment_pair(
                                        left,
                                        normalized.as_ref(),
                                        fragment_pair_counts,
                                        fragment_outgoing_counts,
                                        fragment_incoming_counts,
                                    );
                                }
                                previous_fragment_token = Some(normalized.to_string());
                            } else {
                                previous_fragment_token = None;
                            }
                            if is_cjk_token(normalized.as_ref()) {
                                previous_cjk_token = Some(normalized.into_owned());
                            } else {
                                previous_cjk_token = None;
                            }
                        }
                    }
                    SplitState::Unmatched(unmatched) => {
                        for skip_state in SplitMatches::new(re_skip, unmatched) {
                            let word = skip_state.as_str();
                            if word.is_empty() || skip_state.is_matched() {
                                continue;
                            }
                            let mut word_indices = word.char_indices().map(|(idx, _)| idx).peekable();
                            while let Some(byte_start) = word_indices.next() {
                                let token = if let Some(byte_end) = word_indices.peek() {
                                    &word[byte_start..*byte_end]
                                } else {
                                    &word[byte_start..]
                                };
                                count_zh_candidate_token(token, common_words, &mut batch_counts);
                            }
                        }
                    }
                }
            }
        });
    });
    for (candidate, count) in batch_counts {
        if let Some(existing) = candidate_counts.get_mut(candidate.as_ref()) {
            *existing = existing
                .checked_add(count)
                .expect("candidate count overflow");
        } else {
            candidate_counts.insert(candidate.into_owned(), count);
        }
    }
}

fn is_simple_ascii_alnum_block(value: &str) -> bool {
    !value.is_empty() && value.chars().all(|ch| ch.is_ascii_alphanumeric())
}

fn count_zh_candidate_token<'a>(
    token: &'a str,
    common_words: &FxHashSet<String>,
    batch_counts: &mut FxHashMap<Cow<'a, str>, CandidateCount>,
) {
    let normalized = normalize_token(token);
    count_zh_candidate_token_normalized(normalized, common_words, batch_counts);
}

fn count_zh_candidate_token_normalized<'a>(
    normalized: Cow<'a, str>,
    common_words: &FxHashSet<String>,
    batch_counts: &mut FxHashMap<Cow<'a, str>, CandidateCount>,
) {
    let normalized_ref = normalized.as_ref();
    if !has_min_chars(normalized_ref, 2) {
        return;
    }
    if common_words.contains(normalized_ref) {
        return;
    }
    match classify_match_normalization(normalized_ref) {
        MatchNormalization::None => {}
        MatchNormalization::AsciiLower => {
            let match_candidate = normalized_ref.to_ascii_lowercase();
            if common_words.contains(match_candidate.as_str()) {
                return;
            }
        }
        MatchNormalization::UnicodeCaseFold => {
            let match_candidate = normalize_for_matching(normalized_ref);
            if match_candidate.as_ref() != normalized_ref
                && common_words.contains(match_candidate.as_ref())
            {
                return;
            }
        }
    }
    if let Some(count) = batch_counts.get_mut(normalized_ref) {
        *count = count.checked_add(1).expect("batch candidate count overflow");
    } else {
        batch_counts.insert(normalized, 1);
    }
}

fn count_recovered_zh_name_candidate(
    candidate: String,
    common_words: &FxHashSet<String>,
    recovered_name_counts: &mut FxHashMap<String, CandidateCount>,
) {
    if common_words.contains(candidate.as_str()) {
        return;
    }
    if let Some(existing) = recovered_name_counts.get_mut(candidate.as_str()) {
        *existing = existing
            .checked_add(1)
            .expect("recovered candidate count overflow");
    } else {
        recovered_name_counts.insert(candidate, 1);
    }
}

fn is_zh_fragment_token(token: &str, common_words: &FxHashSet<String>) -> bool {
    !token.is_empty()
        && token.chars().count() <= ZH_FRAGMENT_MAX_TOKEN_CHARS
        && is_cjk_token(token)
        && !common_words.contains(token)
        && (looks_like_zh_translit_fragment(token) || is_zh_name_suffix_title(token))
}

fn increment_candidate_count<K>(counts: &mut FxHashMap<K, CandidateCount>, key: K)
where
    K: std::hash::Hash + Eq,
{
    if let Some(existing) = counts.get_mut(&key) {
        *existing = existing
            .checked_add(1)
            .expect("candidate count overflow");
    } else {
        counts.insert(key, 1);
    }
}

fn count_zh_fragment_pair(
    left: &str,
    right: &str,
    pair_counts: &mut FxHashMap<(String, String), CandidateCount>,
    outgoing_counts: &mut FxHashMap<String, CandidateCount>,
    incoming_counts: &mut FxHashMap<String, CandidateCount>,
) {
    increment_candidate_count(pair_counts, (left.to_owned(), right.to_owned()));
    increment_candidate_count(outgoing_counts, left.to_owned());
    increment_candidate_count(incoming_counts, right.to_owned());
}

fn recover_bound_zh_fragment_candidates(
    candidate_counts: &mut FxHashMap<String, CandidateCount>,
    common_words: &FxHashSet<String>,
    pair_counts: FxHashMap<(String, String), CandidateCount>,
    outgoing_counts: FxHashMap<String, CandidateCount>,
    incoming_counts: FxHashMap<String, CandidateCount>,
) {
    if pair_counts.is_empty() {
        return;
    }

    let mut best_successor: FxHashMap<String, (String, CandidateCount)> = FxHashMap::default();
    let mut best_predecessor: FxHashMap<String, (String, CandidateCount)> = FxHashMap::default();
    let mut ambiguous_successors: FxHashSet<String> = FxHashSet::default();
    let mut ambiguous_predecessors: FxHashSet<String> = FxHashSet::default();

    for ((left, right), count) in pair_counts {
        if count < ZH_FRAGMENT_EXTENSION_MIN_COUNT {
            continue;
        }
        let outgoing = outgoing_counts.get(left.as_str()).copied().unwrap_or(0);
        let incoming = incoming_counts.get(right.as_str()).copied().unwrap_or(0);
        if outgoing == 0 || incoming == 0 {
            continue;
        }
        if (count as f32 / outgoing as f32) < ZH_FRAGMENT_DOMINANCE_THRESHOLD
            || (count as f32 / incoming as f32) < ZH_FRAGMENT_DOMINANCE_THRESHOLD
        {
            continue;
        }

        match best_successor.get(left.as_str()) {
            Some((_, best_count)) if *best_count > count => {}
            Some((best_right, best_count)) if *best_count == count && best_right != &right => {
                ambiguous_successors.insert(left.clone());
            }
            _ => {
                best_successor.insert(left.clone(), (right.clone(), count));
                ambiguous_successors.remove(left.as_str());
            }
        }

        match best_predecessor.get(right.as_str()) {
            Some((_, best_count)) if *best_count > count => {}
            Some((best_left, best_count)) if *best_count == count && best_left != &left => {
                ambiguous_predecessors.insert(right.clone());
            }
            _ => {
                best_predecessor.insert(right.clone(), (left.clone(), count));
                ambiguous_predecessors.remove(right.as_str());
            }
        }
    }

    let start_tokens: Vec<String> = best_successor
        .keys()
        .filter(|left| {
            !ambiguous_successors.contains(left.as_str())
                && !best_predecessor.contains_key(left.as_str())
                && looks_like_zh_translit_fragment(left.as_str())
        })
        .cloned()
        .collect();

    for start in start_tokens {
        let mut fragments = vec![start.clone()];
        let mut chain_count = CandidateCount::MAX;
        let mut current = start;
        let mut seen: FxHashSet<String> = FxHashSet::default();
        seen.insert(current.clone());

        while !ambiguous_successors.contains(current.as_str()) {
            if is_zh_name_suffix_title(current.as_str()) {
                break;
            }
            let Some((next_token, edge_count)) = best_successor.get(current.as_str()) else {
                break;
            };
            let next_token = next_token.clone();
            if seen.contains(next_token.as_str()) || ambiguous_predecessors.contains(next_token.as_str()) {
                break;
            }
            let Some((predecessor, _)) = best_predecessor.get(next_token.as_str()) else {
                break;
            };
            if predecessor != &current {
                break;
            }

            fragments.push(next_token.clone());
            chain_count = chain_count.min(*edge_count);
            seen.insert(next_token.clone());
            current = next_token;
            if is_zh_name_suffix_title(current.as_str()) {
                break;
            }
        }

        if fragments.len() < 2 {
            continue;
        }

        let merged = fragments.concat();
        if merged.chars().count() < 3
            || merged.chars().collect::<FxHashSet<char>>().len() < 2
            || common_words.contains(merged.as_str())
        {
            continue;
        }

        match candidate_counts.get_mut(merged.as_str()) {
            Some(existing) => {
                if *existing < chain_count {
                    *existing = chain_count;
                }
            }
            None => {
                candidate_counts.insert(merged, chain_count);
            }
        }
        for fragment in fragments {
            let should_remove = if let Some(existing) = candidate_counts.get_mut(fragment.as_str()) {
                *existing = existing.saturating_sub(chain_count);
                *existing == 0
            } else {
                false
            };
            if should_remove {
                candidate_counts.remove(fragment.as_str());
            }
        }
    }
}

fn merge_split_zh_name_tokens(left: &str, right: &str) -> Option<String> {
    if !is_cjk_token(left) || !is_cjk_token(right) {
        return None;
    }

    let left_len = left.chars().count();
    let right_len = right.chars().count();
    if right_len == 1 && right.chars().next().is_some_and(is_zh_name_trailing_block_char) {
        return None;
    }

    if left_len == 2 && is_zh_compound_surname(left) && matches!(right_len, 1 | 2) {
        return Some(format!("{left}{right}"));
    }
    if left_len == 3 && prefix_chars(left, 2).is_some_and(is_zh_compound_surname) && right_len == 1
    {
        return Some(format!("{left}{right}"));
    }
    if left_len == 1 && is_zh_single_surname(left) && right_len == 2 {
        return Some(format!("{left}{right}"));
    }
    if left_len == 2 && prefix_chars(left, 1).is_some_and(is_zh_single_surname) && right_len == 1
    {
        return Some(format!("{left}{right}"));
    }
    None
}

fn is_cjk_token(value: &str) -> bool {
    !value.is_empty() && value.chars().all(is_cjk_name_char)
}

fn is_cjk_name_char(ch: char) -> bool {
    matches!(
        ch as u32,
        0x3400..=0x4DBF
            | 0x4E00..=0x9FFF
            | 0xF900..=0xFAFF
            | 0x20000..=0x2A6DF
            | 0x2A700..=0x2B73F
            | 0x2B740..=0x2B81F
            | 0x2B820..=0x2CEAF
            | 0x2CEB0..=0x2EBEF
            | 0x2F800..=0x2FA1F
    )
}

fn is_zh_single_surname(value: &str) -> bool {
    let mut chars = value.chars();
    matches!(
        chars.next(),
        Some(ch)
            if chars.next().is_none()
                && ZH_SINGLE_SURNAMES.trim().contains(ch)
    )
}

fn zh_compound_surnames() -> &'static FxHashSet<&'static str> {
    static COMPOUND_SURNAMES: OnceLock<FxHashSet<&'static str>> = OnceLock::new();
    COMPOUND_SURNAMES.get_or_init(|| {
        ZH_COMPOUND_SURNAMES
            .lines()
            .map(str::trim)
            .filter(|surname| !surname.is_empty())
            .collect()
    })
}

fn is_zh_compound_surname(value: &str) -> bool {
    zh_compound_surnames().contains(value)
}

fn is_zh_name_trailing_block_char(ch: char) -> bool {
    ZH_NAME_TRAILING_NOISE_CHARS.trim().contains(ch)
}

fn looks_like_zh_person_name(value: &str) -> bool {
    if !is_cjk_token(value) {
        return false;
    }

    match value.chars().count() {
        2 => prefix_chars(value, 1).is_some_and(is_zh_single_surname),
        3 => {
            prefix_chars(value, 1).is_some_and(is_zh_single_surname)
                || prefix_chars(value, 2).is_some_and(is_zh_compound_surname)
        }
        4 => prefix_chars(value, 2).is_some_and(is_zh_compound_surname),
        _ => false,
    }
}

fn strip_zh_person_name_trailing_noise(value: &str) -> Option<&str> {
    if !is_cjk_token(value) || value.chars().count() < 3 {
        return None;
    }

    let (last_byte_idx, last_char) = value.char_indices().last()?;
    if !is_zh_name_trailing_block_char(last_char) {
        return None;
    }

    let canonical = &value[..last_byte_idx];
    looks_like_zh_person_name(canonical).then_some(canonical)
}

fn zh_translit_chars() -> &'static FxHashSet<char> {
    static TRANSLIT_CHARS: OnceLock<FxHashSet<char>> = OnceLock::new();
    TRANSLIT_CHARS.get_or_init(|| {
        ZH_TRANSLIT_CHARS
            .chars()
            .filter(|ch| !ch.is_whitespace())
            .collect()
    })
}

fn looks_like_zh_translit_fragment(value: &str) -> bool {
    !value.is_empty()
        && is_cjk_token(value)
        && value.chars().all(|ch| zh_translit_chars().contains(&ch))
}

fn zh_name_suffix_titles() -> &'static FxHashSet<&'static str> {
    static SUFFIX_TITLES: OnceLock<FxHashSet<&'static str>> = OnceLock::new();
    SUFFIX_TITLES.get_or_init(|| {
        ZH_NAME_SUFFIX_TITLES
            .lines()
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .collect()
    })
}

fn is_zh_name_suffix_title(value: &str) -> bool {
    zh_name_suffix_titles().contains(value)
}

fn prefix_chars(value: &str, count: usize) -> Option<&str> {
    if count == 0 {
        return Some("");
    }
    let mut seen = 0usize;
    for (byte_idx, ch) in value.char_indices() {
        seen += 1;
        if seen == count {
            return Some(&value[..byte_idx + ch.len_utf8()]);
        }
    }
    None
}

fn normalize_token(token: &str) -> Cow<'_, str> {
    let trimmed = trim_token(token);
    if trimmed.is_empty() {
        return Cow::Borrowed(trimmed);
    }
    if is_simple_nfkc_token(trimmed) {
        return Cow::Borrowed(trimmed);
    }
    let normalized: String = trimmed.nfkc().collect();
    if normalized == trimmed {
        Cow::Borrowed(trimmed)
    } else {
        Cow::Owned(trim_owned_token(normalized))
    }
}

fn is_simple_nfkc_token(value: &str) -> bool {
    value
        .chars()
        .all(|ch| ch.is_ascii() || is_simple_nfkc_cjk(ch))
}

fn is_simple_nfkc_cjk(ch: char) -> bool {
    matches!(ch as u32, 0x3400..=0x4DBF | 0x4E00..=0x9FFF | 0xF900..=0xFAFF)
}

fn normalize_for_matching(value: &str) -> Cow<'_, str> {
    let folded: String = value.case_fold().collect();
    if folded == value {
        Cow::Borrowed(value)
    } else {
        Cow::Owned(folded)
    }
}

fn classify_match_normalization(value: &str) -> MatchNormalization {
    let mut saw_ascii_upper = false;
    for ch in value.chars() {
        if ch.is_ascii_uppercase() {
            saw_ascii_upper = true;
            continue;
        }
        if !ch.is_ascii() && ch.is_alphabetic() && !is_simple_nfkc_cjk(ch) {
            return MatchNormalization::UnicodeCaseFold;
        }
    }
    if saw_ascii_upper {
        MatchNormalization::AsciiLower
    } else {
        MatchNormalization::None
    }
}

fn trim_owned_token(value: String) -> String {
    let trimmed = trim_token(&value);
    if trimmed.len() == value.len() {
        value
    } else {
        trimmed.to_owned()
    }
}

fn trim_token(value: &str) -> &str {
    value.trim_matches(is_trim_char)
}

fn is_trim_char(ch: char) -> bool {
    matches!(
        ch,
        ' '
            | '\t'
            | '\r'
            | '\n'
            | '.'
            | ','
            | '!'
            | '?'
            | ';'
            | ':'
            | '"'
            | '\''
            | '('
            | ')'
            | '['
            | ']'
            | '{'
            | '}'
            | '<'
            | '>'
            | '，'
            | '。'
            | '！'
            | '？'
            | '；'
            | '：'
            | '、'
            | '“'
            | '”'
            | '‘'
            | '’'
            | '（'
            | '）'
            | '【'
            | '】'
            | '《'
            | '》'
            | '…'
            | '·'
            | '-'
            | '—'
    )
}

fn has_min_chars(value: &str, min_chars: usize) -> bool {
    if min_chars <= 1 {
        return !value.is_empty();
    }
    value.chars().nth(min_chars - 1).is_some()
}

#[cfg(test)]
fn window_starts(
    char_count: usize,
    window_size: usize,
    window_step: usize,
) -> Vec<usize> {
    let mut starts = Vec::new();
    window_starts_into(char_count, window_size, window_step, &mut starts);
    starts
}

fn window_starts_into(
    char_count: usize,
    window_size: usize,
    window_step: usize,
    starts: &mut Vec<usize>,
) {
    starts.clear();
    if char_count == 0 {
        return;
    }
    if char_count <= window_size {
        starts.push(0);
        return;
    }

    let last_start = char_count - window_size;
    let mut start = 0usize;
    while start < last_start {
        starts.push(start);
        match start.checked_add(window_step) {
            Some(next_start) => start = next_start,
            None => break,
        }
    }
    if starts.last().copied() != Some(last_start) {
        starts.push(last_start);
    }
}

#[pyfunction]
fn plan_update<'py>(
    py: Python<'py>,
    existing_payload: Option<&[u8]>,
    requested_language: Option<String>,
    chapters: Vec<(i64, String, String)>,
    targets: Vec<(String, String, String, Vec<String>)>,
) -> PyResult<Py<PyDict>> {
    let request = build_request(requested_language, chapters, targets);
    let existing_payload = existing_payload.map(|payload| payload.to_vec());
    let result = py.allow_threads(|| plan_update_result(existing_payload.as_deref(), &request));
    update_plan_dict(py, &result)
}

#[pyfunction]
fn assemble_payload<'py>(
    py: Python<'py>,
    request_json: &[u8],
    chapter_shards_json: &[u8],
    existing_payload: Option<&[u8]>,
) -> PyResult<Py<PyTuple>> {
    let request_json = request_json.to_vec();
    let chapter_shards_json = chapter_shards_json.to_vec();
    let existing_payload = existing_payload.map(|payload| payload.to_vec());
    let (payload_bytes, result_bytes) = py.allow_threads(|| {
        assemble_payload_bytes(
            &request_json,
            &chapter_shards_json,
            existing_payload.as_deref(),
        )
    })?;
    let tuple = PyTuple::new(
        py,
        [
            PyBytes::new(py, &payload_bytes).into_any(),
            PyBytes::new(py, &result_bytes).into_any(),
        ],
    )?;
    Ok(tuple.unbind())
}

#[pyfunction]
fn build_full<'py>(py: Python<'py>, request_json: &[u8]) -> PyResult<Py<PyTuple>> {
    let request_json = request_json.to_vec();
    let (payload_bytes, result_bytes) = py.allow_threads(|| build_full_bytes(&request_json))?;
    let tuple = PyTuple::new(
        py,
        [
            PyBytes::new(py, &payload_bytes).into_any(),
            PyBytes::new(py, &result_bytes).into_any(),
        ],
    )?;
    Ok(tuple.unbind())
}

#[pyfunction]
fn update_incremental<'py>(
    py: Python<'py>,
    existing_payload: &[u8],
    request_json: &[u8],
) -> PyResult<Py<PyTuple>> {
    let existing_payload = existing_payload.to_vec();
    let request_json = request_json.to_vec();
    let (payload_bytes, result_bytes) = py.allow_threads(|| {
        update_incremental_bytes(&existing_payload, &request_json)
    })?;
    let tuple = PyTuple::new(
        py,
        [
            PyBytes::new(py, &payload_bytes).into_any(),
            PyBytes::new(py, &result_bytes).into_any(),
        ],
    )?;
    Ok(tuple.unbind())
}

#[pyfunction]
fn build_full_structured<'py>(
    py: Python<'py>,
    requested_language: Option<String>,
    chapters: Vec<(i64, String, String)>,
    targets: Vec<(String, String, String, Vec<String>)>,
) -> PyResult<Py<PyTuple>> {
    let request = build_request(requested_language, chapters, targets);
    let (payload_bytes, result) = py.allow_threads(|| build_full_request(request))?;
    let tuple = PyTuple::new(
        py,
        [
            PyBytes::new(py, &payload_bytes).into_any(),
            build_result_any(py, &result)?,
        ],
    )?;
    Ok(tuple.unbind())
}

#[pyfunction]
fn update_incremental_structured<'py>(
    py: Python<'py>,
    existing_payload: &[u8],
    requested_language: Option<String>,
    chapters: Vec<(i64, String, String)>,
    targets: Vec<(String, String, String, Vec<String>)>,
) -> PyResult<Py<PyTuple>> {
    let request = build_request(requested_language, chapters, targets);
    let existing_payload = existing_payload.to_vec();
    let (payload_bytes, result) = py.allow_threads(|| {
        update_incremental_request(&existing_payload, request)
    })?;
    let tuple = PyTuple::new(
        py,
        [
            PyBytes::new(py, &payload_bytes).into_any(),
            build_result_any(py, &result)?,
        ],
    )?;
    Ok(tuple.unbind())
}

fn build_request(
    requested_language: Option<String>,
    chapters: Vec<(i64, String, String)>,
    targets: Vec<(String, String, String, Vec<String>)>,
) -> BuildRequest {
    BuildRequest {
        format_version: STATE_PROTO_PAYLOAD_FORMAT_VERSION,
        requested_language,
        chapters: chapters
            .into_iter()
            .map(|(chapter_id, text, signature)| RequestChapter {
                chapter_id,
                text,
                signature: Some(signature),
            })
            .collect(),
        targets: targets
            .into_iter()
            .map(|(id, canonical_name, kind, aliases)| RequestTarget {
                id,
                canonical_name,
                kind,
                aliases,
            })
            .collect(),
    }
}

fn update_plan_dict<'py>(py: Python<'py>, result: &UpdatePlanResult) -> PyResult<Py<PyDict>> {
    let data = PyDict::new(py);
    data.set_item("mode", result.mode.as_str())?;
    data.set_item("supported_incremental", result.supported_incremental)?;
    data.set_item("existing_payload_compatible", result.existing_payload_compatible)?;
    data.set_item("target_catalog_changed", result.target_catalog_changed)?;
    data.set_item("dirty_chapter_ids", result.dirty_chapter_ids.clone())?;
    data.set_item("fallback_reason", result.fallback_reason.clone())?;
    data.set_item("no_changes", result.no_changes)?;
    Ok(data.unbind())
}

fn build_result_dict<'py>(py: Python<'py>, result: &BuildResult) -> PyResult<Py<PyDict>> {
    let data = PyDict::new(py);
    data.set_item("payload_bytes", result.payload_bytes)?;
    data.set_item("chapter_count", result.chapter_count)?;
    data.set_item("chapter_chars", result.chapter_chars)?;
    data.set_item("target_count", result.target_count)?;
    data.set_item("segment_count", result.segment_count)?;
    data.set_item("mention_posting_count", result.mention_posting_count)?;
    data.set_item("claim_atom_count", result.claim_atom_count)?;
    data.set_item("coverage_rep_count", result.coverage_rep_count)?;
    data.set_item("segmentation_ms", result.segmentation_ms)?;
    data.set_item("mention_ms", result.mention_ms)?;
    data.set_item("claim_ms", result.claim_ms)?;
    data.set_item("coverage_ms", result.coverage_ms)?;
    data.set_item("serialize_ms", result.serialize_ms)?;
    data.set_item("duration_ms", result.duration_ms)?;
    data.set_item("plan_mode", result.plan_mode.as_str())?;
    data.set_item("incremental_applied", result.incremental_applied)?;
    data.set_item("rebuilt_chapter_count", result.rebuilt_chapter_count)?;
    data.set_item("reused_chapter_count", result.reused_chapter_count)?;
    data.set_item("fallback_reason", result.fallback_reason.clone())?;
    Ok(data.unbind())
}

fn build_result_any<'py>(py: Python<'py>, result: &BuildResult) -> PyResult<Bound<'py, PyAny>> {
    Ok(build_result_dict(py, result)?.into_bound(py).into_any())
}

#[pymodule]
fn _novwr_state_proto(_py: Python<'_>, module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(payload_format_version, module)?)?;
    module.add_function(wrap_pyfunction!(tokenize_zh_text, module)?)?;
    module.add_function(wrap_pyfunction!(count_zh_candidates, module)?)?;
    module.add_function(wrap_pyfunction!(count_zh_candidates_topk, module)?)?;
    module.add_function(wrap_pyfunction!(summarize_zh_windows, module)?)?;
    module.add_function(wrap_pyfunction!(summarize_zh_windows_compact, module)?)?;
    module.add_function(wrap_pyfunction!(summarize_zh_windows_raw, module)?)?;
    module.add_function(wrap_pyfunction!(build_zh_block_refinement_inputs_compact, module)?)?;
    module.add_function(wrap_pyfunction!(plan_update, module)?)?;
    module.add_function(wrap_pyfunction!(assemble_payload, module)?)?;
    module.add_function(wrap_pyfunction!(build_full, module)?)?;
    module.add_function(wrap_pyfunction!(update_incremental, module)?)?;
    module.add_function(wrap_pyfunction!(build_full_structured, module)?)?;
    module.add_function(wrap_pyfunction!(update_incremental_structured, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_token_keeps_fast_path_and_compatibility_path_equivalent() {
        assert_eq!(normalize_token("顾衡").as_ref(), "顾衡");
        assert_eq!(normalize_token("，顾衡。").as_ref(), "顾衡");
        assert_eq!(normalize_token("ＡＢＣ").as_ref(), "ABC");
        assert_eq!(normalize_token("﹙顾衡﹚").as_ref(), "顾衡");
        assert_eq!(normalize_token("Ⅳ").as_ref(), "IV");
    }

    #[test]
    fn classify_match_normalization_uses_ascii_and_unicode_paths() {
        assert_eq!(classify_match_normalization("顾衡"), MatchNormalization::None);
        assert_eq!(classify_match_normalization("ABC"), MatchNormalization::AsciiLower);
        assert_eq!(
            classify_match_normalization("ÄBC"),
            MatchNormalization::UnicodeCaseFold
        );
    }

    fn naive_summarize_zh_window_counts(
        chapters: &[String],
        shortlisted_candidates: &[String],
        window_size: usize,
        window_step: usize,
    ) -> Result<(Vec<String>, Vec<usize>, Vec<u32>), String> {
        let mut shortlisted_candidates: Vec<String> = shortlisted_candidates.to_vec();
        shortlisted_candidates.sort_unstable();
        shortlisted_candidates.dedup();
        let candidate_count = shortlisted_candidates.len();
        let pair_matrix_len = candidate_count
            .checked_mul(candidate_count)
            .ok_or_else(|| "candidate matrix too large".to_string())?;
        let automaton =
            AhoCorasick::new(&shortlisted_candidates).map_err(|err| err.to_string())?;
        let mut importance_counts = vec![0usize; candidate_count];
        let mut pair_counts = vec![0u32; pair_matrix_len];
        let mut seen_generations = vec![0u64; candidate_count];
        let mut window_generation = 0u64;
        let mut present_ids = Vec::new();

        for chapter in chapters {
            let chapter: &str = chapter.as_str();
            let char_starts = collect_char_starts(chapter);
            let char_count = char_starts.len().saturating_sub(1);
            if char_count == 0 {
                continue;
            }
            for start_char in window_starts(char_count, window_size, window_step) {
                window_generation += 1;
                present_ids.clear();
                let end_char = (start_char + window_size).min(char_count);
                let start_byte = char_starts[start_char];
                let end_byte = char_starts[end_char];
                let window_text = &chapter[start_byte..end_byte];

                for mat in automaton.find_overlapping_iter(window_text) {
                    let candidate_id = mat.pattern().as_usize();
                    if seen_generations[candidate_id] == window_generation {
                        continue;
                    }
                    seen_generations[candidate_id] = window_generation;
                    present_ids.push(candidate_id);
                }
                if present_ids.is_empty() {
                    continue;
                }
                present_ids.sort_unstable();
                for (index, &left_id) in present_ids.iter().enumerate() {
                    importance_counts[left_id] += 1;
                    let row_offset = left_id * candidate_count;
                    for &right_id in &present_ids[index + 1..] {
                        pair_counts[row_offset + right_id] += 1;
                    }
                }
            }
        }

        Ok((shortlisted_candidates, importance_counts, pair_counts))
    }

    #[test]
    fn naive_summary_handles_overlapping_candidates() {
        let chapters = vec![
            "顾衡在云港司守夜。顾衡与林秋又回到云港司，云港司里提起旧案。".to_owned(),
        ];
        let shortlisted_candidates = vec![
            "顾衡".to_owned(),
            "云港".to_owned(),
            "云港司".to_owned(),
            "林秋".to_owned(),
            "旧案".to_owned(),
        ];

        let (_, importance_counts, pair_counts) = naive_summarize_zh_window_counts(
            &chapters,
            &shortlisted_candidates,
            12,
            6,
        )
        .expect("naive summary should succeed");

        assert!(importance_counts.iter().any(|count| *count > 0));
        assert!(pair_counts.iter().any(|count| *count > 0));
    }

    #[test]
    fn merge_split_zh_name_tokens_recovers_names_and_blocks_noise() {
        assert_eq!(
            merge_split_zh_name_tokens("慕容雪", "晴").as_deref(),
            Some("慕容雪晴")
        );
        assert_eq!(
            merge_split_zh_name_tokens("欧阳", "明月").as_deref(),
            Some("欧阳明月")
        );
        assert_eq!(
            merge_split_zh_name_tokens("顾慎", "为").as_deref(),
            Some("顾慎为")
        );
        assert_eq!(merge_split_zh_name_tokens("张纲", "一"), None);
        assert_eq!(merge_split_zh_name_tokens("张钢", "走"), None);
    }

    #[test]
    fn strip_zh_person_name_trailing_noise_keeps_person_roots_only() {
        assert_eq!(strip_zh_person_name_trailing_noise("罗碧不"), Some("罗碧"));
        assert_eq!(strip_zh_person_name_trailing_noise("顾慎为看"), Some("顾慎为"));
        assert_eq!(strip_zh_person_name_trailing_noise("炙皇星看"), None);
        assert_eq!(strip_zh_person_name_trailing_noise("战士们"), None);
    }

    #[test]
    fn merge_zh_person_name_shadow_counts_merges_only_safe_variants() {
        let mut candidate_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();
        candidate_counts.insert("罗碧".to_owned(), 10);
        candidate_counts.insert("罗碧不".to_owned(), 3);
        candidate_counts.insert("罗碧看".to_owned(), 2);
        candidate_counts.insert("炙皇星看".to_owned(), 4);

        merge_zh_person_name_shadow_counts(&mut candidate_counts);

        assert_eq!(candidate_counts.get("罗碧"), Some(&15));
        assert_eq!(candidate_counts.get("罗碧不"), None);
        assert_eq!(candidate_counts.get("罗碧看"), None);
        assert_eq!(candidate_counts.get("炙皇星看"), Some(&4));
    }

    #[test]
    fn sort_candidate_counts_prefers_longer_names_when_counts_tie() {
        let mut items = vec![
            ("慕容雪".to_owned(), 3usize),
            ("慕容雪晴".to_owned(), 3usize),
            ("顾慎".to_owned(), 2usize),
            ("顾慎为".to_owned(), 2usize),
        ];

        sort_candidate_counts(&mut items);

        assert_eq!(items[0].0, "慕容雪晴");
        assert_eq!(items[1].0, "慕容雪");
        assert_eq!(items[2].0, "顾慎为");
        assert_eq!(items[3].0, "顾慎");
    }

    #[test]
    fn count_zh_batch_recovers_split_person_names() {
        let mut candidate_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();
        let mut recovered_name_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();
        let mut fragment_pair_counts: FxHashMap<(String, String), CandidateCount> =
            FxHashMap::default();
        let mut fragment_outgoing_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();
        let mut fragment_incoming_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();

        count_zh_batch(
            "慕容雪晴来到大厅。慕容雪晴看着欧阳明月，欧阳明月也看着慕容雪晴。顾慎为与荷女对视。顾慎为没有说话。",
            &FxHashSet::default(),
            &mut candidate_counts,
            &mut recovered_name_counts,
            &mut fragment_pair_counts,
            &mut fragment_outgoing_counts,
            &mut fragment_incoming_counts,
        );
        merge_recovered_zh_name_counts(&mut candidate_counts, recovered_name_counts);
        recover_bound_zh_fragment_candidates(
            &mut candidate_counts,
            &FxHashSet::default(),
            fragment_pair_counts,
            fragment_outgoing_counts,
            fragment_incoming_counts,
        );

        assert_eq!(candidate_counts.get("慕容雪晴"), Some(&3));
        assert_eq!(candidate_counts.get("欧阳明月"), Some(&2));
        assert_eq!(candidate_counts.get("顾慎为"), Some(&2));
    }

    #[test]
    fn count_zh_batch_recovers_bound_fragment_names_and_discounts_fragments() {
        let mut candidate_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();
        let mut recovered_name_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();
        let mut fragment_pair_counts: FxHashMap<(String, String), CandidateCount> =
            FxHashMap::default();
        let mut fragment_outgoing_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();
        let mut fragment_incoming_counts: FxHashMap<String, CandidateCount> = FxHashMap::default();

        count_zh_batch(
            "拉蒂莉娅看见坎贝斯莉太太。拉蒂莉娅向坎贝斯莉太太行礼。拉蒂莉娅又遇见坎贝斯莉太太。",
            &FxHashSet::default(),
            &mut candidate_counts,
            &mut recovered_name_counts,
            &mut fragment_pair_counts,
            &mut fragment_outgoing_counts,
            &mut fragment_incoming_counts,
        );
        merge_recovered_zh_name_counts(&mut candidate_counts, recovered_name_counts);
        recover_bound_zh_fragment_candidates(
            &mut candidate_counts,
            &FxHashSet::default(),
            fragment_pair_counts,
            fragment_outgoing_counts,
            fragment_incoming_counts,
        );

        assert_eq!(candidate_counts.get("拉蒂莉娅"), Some(&3));
        assert_eq!(candidate_counts.get("坎贝斯莉太太"), Some(&3));
        assert_eq!(candidate_counts.get("拉蒂"), None);
        assert_eq!(candidate_counts.get("贝斯"), None);
        assert_eq!(candidate_counts.get("太太"), None);
    }
}
