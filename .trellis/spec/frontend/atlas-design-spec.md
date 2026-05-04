# Atlas Design Specification

> Design spec for the Atlas deep governance surface.
> Uses real product design patterns from Linear, Memotron, Cursor, Fibery, and Missive as references.
> Current implementation reference: `web/src/pages/NovelAtlasPage.tsx`.

## Design Thesis

Atlas is a **strategic command center** for the novel's world model — not a crowded admin panel where overflow UI goes to live. Every pixel must serve the scan → inspect → govern workflow loop.

The experience should feel like sitting down at a purpose-built research workstation: calm but information-dense, with clear spatial zones so the user always knows where to look.

## Layout Architecture

### Shell Structure

Atlas owns its own full-height shell (see `component-guidelines.md` decision). No navbar scroll. Three spatial zones:

```text
┌──────────────────────────────────────────────────────────┐
│ Toolbar (return nav + global actions)                    │
├────────────┬─────────────────────────┬───────────────────┤
│            │                         │                   │
│  Navigator │     Center Stage        │  Copilot          │
│  (280px)   │     (flexible)          │  Workbench        │
│            │                         │  (resizable)      │
│  scan      │     inspect + author    │  AI-assisted      │
│  filter    │     + restructure       │  inquiry          │
│  select    │                         │                   │
│            │                         │                   │
├────────────┴─────────────────────────┴───────────────────┤
│ (no footer — full bleed)                                 │
└──────────────────────────────────────────────────────────┘
```

**Design reference**: Linear's three-column dark workspace (sidebar → project detail → properties/activity). Missive's multi-panel layout demonstrates that up to three columns remain legible when each column has clear purpose boundaries.

### Spatial Zone Contracts

| Zone | Role | Sizing | Scroll |
|---|---|---|---|
| Navigator | Scan-first queue: search, filter, select | Fixed 280px | Internal vertical |
| Center Stage | Inspect + author + restructure | Flexible (min 480px) | Internal vertical, tabs own sub-scroll |
| Copilot Workbench | AI inquiry + suggestion review | Resizable (default 360px, min 280px, max 50%) | Internal vertical |

The Copilot Workbench is persistent and push-based, not a modal overlay. Opening it compresses Center Stage horizontally; it never occludes content.

### Toolbar

The toolbar is a thin, transparent glass bar (≤48px) anchored to the top. It contains:

- Left: one return-to-Studio control (`返回工作台`) for visual consistency across Atlas entry paths
- Behavior: when structured Studio origin state exists, the control returns to that exact Studio stage/context; otherwise it falls back to the novel's default Studio route
- No breadcrumbs — Atlas is one-level deep from Studio

## Tab Architecture

Atlas has four workspace tabs, each a distinct governance mode:

```text
┌─ Systems ─┬─ Entities ─┬─ Relationships ─┬─ (Review) ─┐
```

The Review tab is **ephemeral** — it appears only when navigated to via draft review entry points, and disappears when the user switches to a primary tab. This prevents the tab bar from accumulating permanent visual clutter for an intermittent workflow.

### Tab 1: Systems — Hierarchy + Constraints Governance

**Purpose**: Author and restructure world systems (magic, politics, economy, etc.) with timeline, hierarchy, constraint, and list editors.

**Layout**:

```text
┌─────────────┬────────────────────────────────┐
│ System      │ System Editor                  │
│ Navigator   │                                │
│             │ ┌── name + description ──────┐ │
│ • search    │ │                            │ │
│ • draft-    │ ├── Constraints panel ───────┤ │
│   first     │ ├── Hierarchy editor ────────┤ │
│   sorting   │ ├── Timeline editor ─────────┤ │
│ • create    │ ├── List editor ─────────────┤ │
│   button    │ └────────────────────────────┘ │
│             │                                │
│ ┌─────────┐ │                                │
│ │Draft    │ │                                │
│ │Review   │ │                                │
│ │Summary  │ │                                │
│ └─────────┘ │                                │
└─────────────┴────────────────────────────────┘
```

**Design reference**: Craft's three-column editor with left navigator, center content, and insertion panel. The System Navigator uses the same scan-first queue pattern as Entity Navigator: search → filter → select → detail.

**Key interactions**:

- System Navigator: same glass sidebar pattern (280px, `--nw-glass-bg`, `backdrop-blur-2xl`) with search, draft-first sorting, and a shared `WorldBuildPanel` + `DraftReviewSummaryCard` bottom slot so generation/bootstrap entry remains available from Atlas
- Center: `SystemEditor` with collapsible panels for each sub-editor (constraints, hierarchy, timeline, list)
- Empty state: "选择一个体系开始编辑" centered in muted text

### Tab 2: Entities — Deep Entity Maintenance

**Purpose**: Inspect and maintain entity detail — names, types, descriptions, aliases, attributes, and entity metadata.

**Layout**:

```text
┌──────────────┬───────────────────────────────┐
│ Entity       │ Entity Detail                 │
│ Navigator    │                               │
│              │ ┌── header (name, type) ────┐ │
│ • search     │ ├── description ────────────┤ │
│ • type       │ ├── aliases ────────────────┤ │
│   filters    │ ├── attributes table ───────┤ │
│   (chips)    │ ├── metadata ───────────────┤ │
│ • draft-     │ └──────────────────────────┘ │
│   first      │                               │
│   sorting    │                               │
│ • confirm-   │                               │
│   all CTA    │                               │
│ • create     │                               │
│ ┌──────────┐ │                               │
│ │Draft     │ │                               │
│ │Review    │ │                               │
│ │Summary   │ │                               │
│ └──────────┘ │                               │
└──────────────┴───────────────────────────────┘
```

**Design reference**: Cursor's calm master-detail interface (left list with status indicators → right detail card). Fibery's entity profile panel (avatar, tags, properties, inline editing).

**Key interactions**:

- Entity Navigator: search, type chip filters, draft-first sorting with newest-first, batch confirm/reject all drafts, per-item confirm/reject on hover
- Navigator bottom slot keeps the shared `WorldBuildPanel` entry above `DraftReviewSummaryCard` so Atlas preserves whole-book generation / copilot launch access from the current tab
- Entity Detail: inline editable fields, attribute rows with key-value structure, draft status dot indicator (orange `hsl(var(--color-status-draft))`)
- Selection highlight: left accent border (2px accent color) on selected entity row

### Tab 3: Relationships — Graph Exploration + Relationship Editing

**Purpose**: Visual relationship graph exploration centered on a selected entity, with relationship creation/editing.

**Layout**:

```text
┌──────────────┬───────────────────────────────┐
│ Entity       │ Relationship Graph            │
│ Navigator    │                               │
│              │         ○ entity_a            │
│ • search     │        ╱                      │
│ • type       │   ○───●(center)───○ entity_c  │
│   filters    │        ╲                      │
│              │         ○ entity_b            │
│ ┌──────────┐ │                               │
│ │Relation  │ │ ┌── Relationship Inspector ─┐ │
│ │ship      │ │ │  label, description,      │ │
│ │Sidebar   │ │ │  visibility, endpoints    │ │
│ │Panel     │ │ └──────────────────────────┘ │
│ ├──────────┤ │                               │
│ │Draft     │ │                               │
│ │Review    │ │                               │
│ │Summary   │ │                               │
│ └──────────┘ │                               │
└──────────────┴───────────────────────────────┘
```

**Design reference**: Memotron's radial node-link graph with depth control and interactive node selection. The star graph layout (center entity → connected entities radially arranged) matches Atlas's existing `StarGraph` component.

**Key interactions**:

- Star graph: center entity node with radial spokes to connected entities; key by `selectedEntityId` to force remount on entity change (existing tripwire)
- Graph must remount on center-entity change — do NOT reuse React Flow instance (see `component-guidelines.md` tripwire)
- Hidden handles on star-graph custom nodes must NOT be removed (edge rendering depends on them)
- Relationship Inspector: bottom sheet or side panel for selected edge detail (label, description, visibility)
- Navigator bottom slot stacks the shared `WorldBuildPanel`, `RelationshipSidebarPanel`, and `DraftReviewSummaryCard`
- RelationshipSidebarPanel: in-navigator panel for relationship count, create button, draft review entry
- Relationship creation: modal or inline form in center stage, triggered from navigator panel

### Tab 4: Review — Batch Draft Governance

**Purpose**: Concentrated queue surface for bulk draft review across entities, relationships, and systems.

**Layout**:

```text
┌──────────────┬───────────────────────────────┐
│ Review       │ Draft Items                   │
│ Navigator    │                               │
│              │ kind=entities:                 │
│ • kind tabs  │ ┌── entity card ─── ✓ ✕ ────┐ │
│   (entities/ │ ├── entity card ─── ✓ ✕ ────┤ │
│   relations/ │ ├── entity card ─── ✓ ✕ ────┤ │
│   systems)   │ └───────────────────────────┘ │
│              │                               │
│ • search     │ kind=relationships:            │
│ • item list  │ ┌── rel card ────── ✓ ✕ ────┐ │
│   with       │ └───────────────────────────┘ │
│   highlight  │                               │
│              │ kind=systems:                  │
│              │ ┌── system card ─── ✓ ✕ ────┐ │
│              │ └───────────────────────────┘ │
└──────────────┴───────────────────────────────┘
```

**Design reference**: IKEA's filter-and-sort review panel (left sidebar with filter controls → right scrollable list of review items with approve/reject actions). PayPal's invoice filtering (search + filter tags + clean table with selection).

**Key interactions**:

- DraftReviewNavigator: kind selector (entities / relationships / systems), search, item queue with active item highlight (2.5s flash timer)
- DraftReviewTab: filterable, scrollable card list with per-item confirm / reject actions
- Exit from review: selecting a reviewed item can jump to its entity/relationship/system tab for deeper editing
- Show `kind` selector toggle UI: tab pills or radio segments at top of navigator
- Review tab visibility: appears in tab bar only when actively in review mode; otherwise hidden

## Visual Language

### Color + Material

Atlas inherits the NovWr glass surface system:

| Token | Purpose |
|---|---|
| `--nw-glass-bg` | Semi-transparent background for panels |
| `--nw-glass-bg-hover` | Hover/active state for list items |
| `--nw-glass-border` | Subtle glass border separating zones |
| `--nw-glass-border-hover` | Active filter chip border |
| `backdrop-blur-2xl` | Glass blur depth for navigator panels |

**Status colors** (existing tokens):

- Draft: `hsl(var(--color-status-draft))` — orange indicator dot
- Confirmed: `hsl(var(--color-status-confirmed))` — green for confirm actions
- Danger: `hsl(var(--color-danger))` — red for reject/delete actions
- Accent: `accent` — selection indicator (left border, active tab underline)

### Typography Hierarchy

| Element | Treatment |
|---|---|
| Tab triggers | `text-muted-foreground`, active: `text-foreground` + 2px bottom border in accent |
| Navigator item | `text-sm text-foreground`, truncated, with entity_type badge in `text-xs text-muted-foreground` |
| Section headers | `text-sm font-medium text-muted-foreground` |
| Empty states | Centered `text-muted-foreground` placeholder text |
| Editor headings | `text-base font-semibold text-foreground` |

### Spatial Rhythm

- Navigator padding: `p-4` (16px)
- List item padding: `px-4 py-2`
- Panel borders: 1px `--nw-glass-border`
- Section spacing: `space-y-2` (8px) within navigator
- Bottom slot area: `space-y-3` (12px) after border-t separator

### Animation + Interaction

- Tab switch: instant (no animation — tabs replace content)
- List selection: `transition-colors` on hover/active states
- Draft confirm/reject buttons: appear on `group-hover` / `group-focus-within`
- Review highlight: 2.5s flash timer using `setTimeout` with active item background
- Graph: React Flow handles its own pan/zoom; star graph does radial layout calculation
- Copilot workbench: drag-to-resize with cursor change on handle hover

## Cross-Surface Continuity

### Atlas ↔ Studio Bridge

| Direction | Mechanism |
|---|---|
| Studio → Atlas | URL search params carry origin state (stage, chapter) via `setAtlasStudioOriginSearchParams` |
| Atlas → Studio | Structured return via `buildStudioHostPath(nid, studioOrigin)` — returns to exact Studio context |
| Atlas → Atlas internal | Tab/entity/system/review selection via URL search params (replace mode) |
| Copilot context | Novel-scoped copilot drawer persists across Atlas tabs, `onLocateTarget` handles tab-switch + highlight |

### Copilot Integration

The `NovelCopilotDrawer` lives at the `NovelShellLayout` level, adjacent to `ArtifactStage`. When copilot surfaces a suggestion target:

1. `handleLocateCopilotTarget` receives `CopilotSuggestionTarget`
2. Routes to correct tab (entities / relationships / systems / review)
3. Sets entity/system/review selection via URL search params
4. For review targets: triggers highlight flash on the specific item

This preserves the artifact-first model: center stage shows the thing under decision, copilot assists from the side.

## Design Principles (Atlas-specific)

1. **Scan-first queues**: Navigator panels are for scanning and filtering, never for reading long descriptions. Keep items to one line + badge.
2. **Inspect in center**: All detail reading, editing, and authoring happens in center stage. Sidebars locate, center stage reveals.
3. **Glass hierarchy**: Navigator glass panels are `bg-[var(--nw-glass-bg)]` with `backdrop-blur-2xl`. Center stage is transparent over the animated background. This creates visual depth without heavy borders.
4. **Draft-first sorting**: In every navigator queue, drafts sort first (newest at top), then confirmed items alphabetically. This makes the governance backlog immediately scannable.
5. **Ephemeral governance tabs**: The Review tab appears only during active review navigation. It doesn't clutter the tab bar during normal entity/system/relationship work.
6. **No mega-screen creep**: If a new governance feature arrives that needs more than simple confirm/reject on a single item, it goes in Atlas. Atlas absorbs complexity; Studio stays focused.

## Design Reference Summary

| Product | Pattern Borrowed | Applied To |
|---|---|---|
| **Linear** | Dark three-column workspace, sidebar nav + detail + properties panel | Overall Atlas shell layout |
| **Memotron** | Radial node-link graph with depth control, graph/timeline toggle | Relationships tab star graph |
| **Cursor** | Calm master-detail with status indicators, warm off-white list | Entity Navigator → Entity Detail flow |
| **Fibery** | Table with filter/sort toolbar, colored badges, hierarchical rows | Systems workspace, entity type chips |
| **Missive** | Multi-panel dark productivity workspace, persistent side panel | Copilot workbench integration |
| **IKEA** | Review panel with filter dropdown, approve/reject per item | Draft Review tab batch governance |
| **PayPal** | Search + filter tags + clean table with selection | Review Navigator search + kind filters |

## Implementation Notes

- Atlas keeps its own full-height module shell, but routed usage now sits under `NovelShell` so the novel-scoped copilot workbench and toast scope persist across Studio/Atlas switches. `AtlasShell` remains the module-local safety wrapper for Atlas composition. See `component-guidelines.md` and `runtime-contracts.md`.
- Tab state, entity selection, system selection, and review kind all live in URL search params (replace mode). See `NovelShellRouteState.ts`.
- The `PageShell` animated background shows through the transparent center stage — route-level wrappers must NOT add opaque backgrounds. See `component-guidelines.md`.
- Graph tripwires: React Flow instance keys by entity ID for remount; hidden handles must not be removed. See `component-guidelines.md`.
