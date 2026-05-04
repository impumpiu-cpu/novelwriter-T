// SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
// SPDX-License-Identifier: AGPL-3.0-only

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import '@/lib/uiMessagePacks/novel'
import { ChevronDown, ChevronRight, Info } from 'lucide-react'
import { DriftWarningPopover } from '@/components/generation/DriftWarningPopover'
import type { TextAnnotation } from '@/components/ui/plain-text-content'
import { useCreateChapter } from '@/hooks/novel/useCreateChapter'
import { useAuth } from '@/contexts/AuthContext'
import { useUiLocale } from '@/contexts/UiLocaleContext'
import { addToWhitelist, getWhitelist } from '@/lib/postcheckWhitelistStorage'
import { setActiveWarnings } from '@/lib/postcheckActiveWarningsStorage'
import { downloadTextFile } from '@/lib/downloadTextFile'
import { cn } from '@/lib/utils'
import { api } from '@/services/api'
import type { ContinueDebugSummary } from '@/types/api'
import { ContinuationResultsHeader } from './continuation-results/ContinuationResultsHeader'
import { ContinuationResultsPane } from './continuation-results/ContinuationResultsPane'
import {
  ContinuationResultsEmptyState,
  ContinuationResultsLoadingState,
  ContinuationResultsReloadErrorState,
  ContinuationResultsStreamErrorState,
} from './continuation-results/ContinuationResultsStates'
import { ContinuationResultsTabs } from './continuation-results/ContinuationResultsTabs'
import {
  resolveDriftWarnings,
  resolveProseWarnings,
  resolveResultsDebug,
} from './continuation-results/helpers'
import { useContinuationResultsSource } from './continuation-results/useContinuationResultsSource'

export function ContinuationResultsStage({
  novelId,
  activeChapterNum,
  activeChapterReference,
  showInjectionSummaryRail,
  onToggleInjectionSummaryRail,
  onDebugChange,
  assistOpen,
  onToggleAssist,
}: {
  novelId: number
  activeChapterNum: number | null
  activeChapterReference?: string | null
  showInjectionSummaryRail: boolean
  onToggleInjectionSummaryRail: () => void
  onDebugChange: (debug: ContinueDebugSummary | null) => void
  assistOpen?: boolean
  onToggleAssist?: () => void
}) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, refreshQuota } = useAuth()
  const { locale, t } = useUiLocale()
  const [activeTab, setActiveTab] = useState(0)
  const [showFeedbackForm, setShowFeedbackForm] = useState(false)
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false)
  const [whitelist, setWhitelist] = useState<string[]>(() => getWhitelist(novelId))
  const createChapter = useCreateChapter(novelId)

  const {
    locationState,
    legacyResponse,
    persisted,
    variants,
    fallbackNotice,
    fallbackVersions,
    nonStreamVersions,
    persistedDebug,
    persistedError,
    reloadedWarnings,
    streamDebug,
    streamError,
    isDone,
    isQuotaExhausted,
    isStreamMode,
    isFallbackMode,
    isLegacyMode,
    isReloadMode,
    retryStream,
    retryReload,
  } = useContinuationResultsSource({
    novelId,
    activeChapterNum,
    location,
    navigate,
    locale,
    t,
  })

  const handleDismissTerm = useCallback((term: string) => {
    addToWhitelist(novelId, term)
    setWhitelist((prev) => [...prev, term])
  }, [novelId])

  const driftWarnings = useMemo(() => resolveDriftWarnings({
    isStreamMode,
    isDone,
    streamDebug,
    legacyDebug: legacyResponse?.debug,
    reloadedWarnings,
  }), [isDone, isStreamMode, legacyResponse?.debug, reloadedWarnings, streamDebug])

  const driftAnnotations: TextAnnotation[] = useMemo(() => {
    if (driftWarnings.length === 0) return []

    const targetVersion = activeTab + 1
    return driftWarnings
      .filter((warning) => (warning.version == null || warning.version === targetVersion) && !whitelist.includes(warning.term))
      .map((warning) => ({
        id: `drift-${warning.code}-${warning.term}`,
        term: warning.term,
        className: 'nw-drift-highlight',
        renderPopover: ({ onClose }: { onClose: () => void }) => (
          <DriftWarningPopover
            code={warning.code}
            term={warning.term}
            onDismiss={() => {
              handleDismissTerm(warning.term)
              onClose()
            }}
          />
        ),
      }))
  }, [activeTab, driftWarnings, handleDismissTerm, whitelist])

  useEffect(() => {
    setActiveTab(0)
  }, [isFallbackMode, isLegacyMode, isReloadMode, isStreamMode, persisted, variants.length])

  const currentVariant = isStreamMode && !isFallbackMode ? variants[activeTab] : undefined
  const currentLegacyVersion = isFallbackMode
    ? fallbackVersions[activeTab]
    : (isLegacyMode ? nonStreamVersions[activeTab] : undefined)
  const currentContent = currentVariant?.content ?? currentLegacyVersion?.content ?? ''
  const allDone = isLegacyMode || isFallbackMode || isDone
  const tabCount = isStreamMode && !isFallbackMode ? variants.length : (isFallbackMode ? fallbackVersions.length : nonStreamVersions.length)

  const debug = resolveResultsDebug({
    isStreamMode,
    streamDebug,
    legacyDebug: legacyResponse?.debug,
    persistedDebug,
    studioResultsDebug: locationState?.studioResultsDebug ?? null,
  })
  const summary = debug
    ? {
        entities: debug.injected_entities.length,
        relationships: debug.injected_relationships.length,
        systems: debug.injected_systems.length,
      }
    : null

  useEffect(() => {
    onDebugChange(debug)
  }, [debug, onDebugChange])

  const handleAdopt = useCallback(() => {
    if (!currentContent) return
    createChapter.mutate(
      { content: currentContent },
      {
        onSuccess: (chapter) => {
          const currentDebug = resolveResultsDebug({
            isStreamMode,
            streamDebug,
            legacyDebug: legacyResponse?.debug,
            persistedDebug,
            studioResultsDebug: locationState?.studioResultsDebug ?? null,
          })
          const allWarnings = currentDebug?.drift_warnings ?? (reloadedWarnings.length > 0 ? reloadedWarnings : undefined)
          if (allWarnings?.length) {
            const targetVersion = activeTab + 1
            const activeWarnings = allWarnings.filter(
              (warning) => (warning.version == null || warning.version === targetVersion) && !whitelist.includes(warning.term),
            )
            if (activeWarnings.length > 0) {
              setActiveWarnings(novelId, chapter.chapter_number, activeWarnings, chapter.created_at)
            }
          }
          navigate(`/novel/${novelId}?chapter=${chapter.chapter_number}`, { state: null })
        },
      },
    )
  }, [
    activeTab,
    createChapter,
    currentContent,
    isStreamMode,
    legacyResponse?.debug,
    locationState?.studioResultsDebug,
    navigate,
    novelId,
    persistedDebug,
    reloadedWarnings,
    streamDebug,
    whitelist,
  ])

  const handleExportAll = useCallback(() => {
    const versions = isStreamMode && !isFallbackMode
      ? variants
      : (isFallbackMode ? fallbackVersions : nonStreamVersions)
    if (versions.length === 0) return
    const content = versions
      .map((variant, index) => `${t('continuation.results.exportVersionHeader', { n: index + 1 })}\n\n${variant.content}\n`)
      .join('\n\n')
    downloadTextFile(`continuation_versions_${new Date().toISOString().slice(0, 10)}.txt`, content)
  }, [fallbackVersions, isFallbackMode, isStreamMode, nonStreamVersions, t, variants])

  const handleFeedbackSubmit = useCallback(async (answers: Parameters<typeof api.submitFeedback>[0]) => {
    setFeedbackSubmitting(true)
    try {
      await api.submitFeedback(answers)
      await refreshQuota()
      setShowFeedbackForm(false)
      retryStream()
    } finally {
      setFeedbackSubmitting(false)
    }
  }, [refreshQuota, retryStream])

  const proseWarnings = useMemo(() => {
    const targetVersion = activeTab + 1
    return resolveProseWarnings({
      isStreamMode,
      isFallbackMode,
      isDone,
      streamDebug,
      legacyDebug: legacyResponse?.debug,
      persistedDebug,
      studioResultsDebug: locationState?.studioResultsDebug ?? null,
    }).filter((warning) => warning.version == null || warning.version === targetVersion)
  }, [
    activeTab,
    isDone,
    isFallbackMode,
    isStreamMode,
    legacyResponse?.debug,
    locationState?.studioResultsDebug,
    persistedDebug,
    streamDebug,
  ])

  if (!isStreamMode && !isLegacyMode) {
    if (isReloadMode && !persistedError && nonStreamVersions.length === 0) {
      return <ContinuationResultsLoadingState label={t('continuation.results.loading')} />
    }

    if (isReloadMode && persistedError) {
      return (
        <ContinuationResultsReloadErrorState
          error={persistedError}
          onRetry={retryReload}
          onBack={() => navigate(`/novel/${novelId}`, { state: null })}
          t={t}
        />
      )
    }

    return (
      <ContinuationResultsEmptyState
        onBack={() => navigate(`/novel/${novelId}`, { state: null })}
        t={t}
      />
    )
  }

  if (streamError) {
    return (
      <ContinuationResultsStreamErrorState
        error={streamError}
        isQuotaExhausted={isQuotaExhausted}
        feedbackAlreadySubmitted={Boolean(user?.feedback_submitted)}
        showFeedbackForm={showFeedbackForm}
        feedbackSubmitting={feedbackSubmitting}
        onOpenFeedback={() => setShowFeedbackForm(true)}
        onCloseFeedback={() => setShowFeedbackForm(false)}
        onSubmitFeedback={handleFeedbackSubmit}
        onRetry={retryStream}
        onBackToWrite={() => navigate(`/novel/${novelId}?stage=write`, { state: null })}
        onReturnToWorkspace={() => navigate(`/novel/${novelId}`, { state: null })}
        onGoToSettings={() => navigate('/settings')}
        t={t}
      />
    )
  }

  return (
    <div className="flex-1 min-w-0 flex flex-col gap-5 px-8 py-6 lg:px-12 overflow-hidden">
      <ContinuationResultsHeader
        activeChapterNum={activeChapterNum}
        activeChapterReference={activeChapterReference}
        fallbackNotice={fallbackNotice}
        isStreamMode={isStreamMode}
        isDone={isDone}
        currentContent={currentContent}
        allDone={allDone}
        createPending={createChapter.isPending}
        onAdopt={handleAdopt}
        onBackToWrite={() => navigate(`/novel/${novelId}?stage=write`, { state: null })}
        onExportAll={handleExportAll}
        assistOpen={assistOpen}
        onToggleAssist={onToggleAssist}
        t={t}
      />

      <ContinuationResultsTabs
        tabCount={tabCount}
        activeTab={activeTab}
        isStreamMode={isStreamMode}
        isFallbackMode={isFallbackMode}
        isLegacyMode={isLegacyMode}
        variants={variants}
        onSelect={setActiveTab}
        t={t}
      />

      <ContinuationResultsPane
        isStreamMode={isStreamMode}
        isFallbackMode={isFallbackMode}
        currentVariant={currentVariant}
        currentLegacyVersion={currentLegacyVersion}
        driftAnnotations={driftAnnotations}
        proseWarnings={proseWarnings}
        onRetryStream={retryStream}
        t={t}
      />

      {summary ? (
        <button
          type="button"
          onClick={onToggleInjectionSummaryRail}
          className={cn(
            'shrink-0 rounded-[10px] border px-4 py-3 flex items-center justify-between gap-3 text-left transition-colors',
            showInjectionSummaryRail
              ? 'border-[hsl(var(--accent)/0.3)] bg-[hsl(var(--accent)/0.06)]'
              : 'border-[var(--nw-glass-border)] bg-[hsl(var(--background)/0.35)] hover:bg-[hsl(var(--background)/0.45)]',
          )}
        >
          <div className="flex items-center gap-2 min-w-0">
            <Info size={14} className={showInjectionSummaryRail ? 'text-accent' : 'text-muted-foreground'} />
            <span className={cn('text-xs truncate', showInjectionSummaryRail ? 'text-accent' : 'text-muted-foreground')}>
              {t('continuation.results.injectionSummary', {
                entities: summary.entities,
                relationships: summary.relationships,
                systems: summary.systems,
              })}
            </span>
          </div>
          {showInjectionSummaryRail ? (
            <ChevronDown size={14} className="text-accent shrink-0" />
          ) : (
            <ChevronRight size={14} className="text-muted-foreground shrink-0" />
          )}
        </button>
      ) : null}
    </div>
  )
}
