import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UiLocaleProvider } from '@/contexts/UiLocaleContext'
import { AtlasAssistWorkbench } from '@/components/atlas/workbench/AtlasAssistWorkbench'

const ACTIVE_PENDING_STARTED_AT = 2_000_000_000_000

const mockUseNovelCopilot = vi.fn()
const mockUseOptionalNovelShell = vi.fn()
const mockUseNovelWindowIndex = vi.fn()
const mockUseWorldEntities = vi.fn()
const mockUseWorldRelationships = vi.fn()
const mockUseWorldSystems = vi.fn()

vi.mock('@/components/novel-copilot/NovelCopilotContext', () => ({
  useNovelCopilot: () => mockUseNovelCopilot(),
}))

vi.mock('@/components/novel-shell/NovelShellContext', () => ({
  useOptionalNovelShell: () => mockUseOptionalNovelShell(),
}))

vi.mock('@/hooks/novel/useNovelWindowIndex', () => ({
  useNovelWindowIndex: (...args: unknown[]) => mockUseNovelWindowIndex(...args),
}))

vi.mock('@/hooks/world/useEntities', () => ({
  useWorldEntities: (...args: unknown[]) => mockUseWorldEntities(...args),
}))

vi.mock('@/hooks/world/useRelationships', () => ({
  useWorldRelationships: (...args: unknown[]) => mockUseWorldRelationships(...args),
}))

vi.mock('@/hooks/world/useSystems', () => ({
  useWorldSystems: (...args: unknown[]) => mockUseWorldSystems(...args),
}))

vi.mock('@/components/world-model/shared/BootstrapPanel', () => ({
  BootstrapPanel: ({
    onTriggerStart,
    onJobAccepted,
  }: {
    onTriggerStart?: (startedAtMs: number) => void
    onJobAccepted?: (job: { job_id: number }, startedAtMs: number) => void
  }) => (
    <div data-testid="bootstrap-panel">
      <button
        type="button"
        data-testid="mock-bootstrap-start"
        onClick={() => onTriggerStart?.(ACTIVE_PENDING_STARTED_AT)}
      >
        start
      </button>
      <button
        type="button"
        data-testid="mock-bootstrap-accepted"
        onClick={() => onJobAccepted?.({ job_id: 41 }, ACTIVE_PENDING_STARTED_AT)}
      >
        accepted
      </button>
    </div>
  ),
}))

vi.mock('@/components/world-model/shared/WorldGenerationDialog', () => ({
  WorldGenerationDialog: ({
    open,
    onGenerateSuccess,
    onImportSuccess,
  }: {
    open: boolean
    onGenerateSuccess?: (response: {
      entities_created: number
      relationships_created: number
      systems_created: number
      warnings: []
    }) => void
    onImportSuccess?: (response: {
      pack_id: string
      counts: {
        entities_created: number
        entities_updated: number
        entities_deleted: number
        attributes_created: number
        attributes_updated: number
        attributes_deleted: number
        relationships_created: number
        relationships_updated: number
        relationships_deleted: number
        systems_created: number
        systems_updated: number
        systems_deleted: number
      }
      warnings: []
    }) => void
  }) => (
    <div data-testid="world-generation-dialog">
      {open ? 'open' : 'closed'}
      {open ? (
        <>
          <button
            type="button"
            data-testid="mock-atlas-world-gen-success"
            onClick={() => onGenerateSuccess?.({
              entities_created: 1,
              relationships_created: 0,
              systems_created: 1,
              warnings: [],
            })}
          >
            success
          </button>
          <button
            type="button"
            data-testid="mock-atlas-world-import-success"
            onClick={() => onImportSuccess?.({
              pack_id: 'pack-1',
              counts: {
                entities_created: 2,
                entities_updated: 0,
                entities_deleted: 0,
                attributes_created: 0,
                attributes_updated: 0,
                attributes_deleted: 0,
                relationships_created: 1,
                relationships_updated: 0,
                relationships_deleted: 0,
                systems_created: 1,
                systems_updated: 0,
                systems_deleted: 0,
              },
              warnings: [],
            })}
          >
            import-success
          </button>
        </>
      ) : null}
    </div>
  ),
}))

function renderWorkbench(overrides?: Partial<Parameters<typeof AtlasAssistWorkbench>[0]>) {
  localStorage.setItem('novwr_ui_locale', 'zh')
  document.documentElement.lang = 'zh-CN'

  return render(
    <UiLocaleProvider>
      <AtlasAssistWorkbench
        novelId={7}
        tab="entities"
        width={360}
        onResize={vi.fn()}
        selectedEntityId={9}
        selectedEntityName="苏瑶"
        worldEntityCount={5}
        worldSystemCount={2}
        handoff={null}
        onHandoffChange={vi.fn()}
        onOpenDraftReview={vi.fn()}
        {...overrides}
      />
    </UiLocaleProvider>,
  )
}

describe('AtlasAssistWorkbench', () => {
  const openDrawer = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockUseNovelCopilot.mockReturnValue({ openDrawer })
    mockUseOptionalNovelShell.mockReturnValue({
      routeState: { surface: 'atlas', worldTab: 'entities', stage: null },
    })
    mockUseNovelWindowIndex.mockReturnValue({
      data: { status: 'fresh', revision: 2, built_revision: 2, error: null, job: null },
    })
    mockUseWorldEntities.mockReturnValue({ data: [{ id: 1 }] })
    mockUseWorldRelationships.mockReturnValue({ data: [{ id: 2 }] })
    mockUseWorldSystems.mockReturnValue({ data: [{ id: 3 }] })
  })

  it('separates research from governance assist and wires Atlas-owned actions', async () => {
    const user = userEvent.setup()
    const onOpenDraftReview = vi.fn()
    renderWorkbench({ onOpenDraftReview })

    expect(screen.getByTestId('atlas-assist-sections')).toHaveAttribute('data-stage', 'attention')
    expect(screen.getByTestId('atlas-assist-attention-banner')).toHaveAttribute('data-tone', 'needs_review')
    expect(screen.getByTestId('atlas-assist-research-section')).toBeInTheDocument()
    expect(screen.getByTestId('atlas-assist-governance-section')).toBeInTheDocument()
    expect(screen.getByTestId('atlas-assist-governance-section')).toHaveAttribute('data-prominence', 'elevated')
    expect(screen.queryByTestId('atlas-assist-queue-meta')).not.toBeInTheDocument()
    expect(screen.queryByTestId('atlas-assist-open-review')).not.toBeInTheDocument()

    const sections = screen.getByTestId('atlas-assist-sections')
    const panels = Array.from(sections.querySelectorAll('[data-testid="atlas-assist-governance-section"], [data-testid="atlas-assist-research-section"]'))
      .map((node) => node.getAttribute('data-testid'))
    expect(panels).toEqual(['atlas-assist-governance-section', 'atlas-assist-research-section'])

    await user.click(screen.getByTestId('atlas-assist-open-whole-book'))
    expect(openDrawer).toHaveBeenCalledTimes(1)
    expect(openDrawer.mock.calls[0]?.[0]).toMatchObject({
      mode: 'research',
      scope: 'whole_book',
      context: { surface: 'atlas', tab: 'entities' },
    })

    await user.click(screen.getByTestId('atlas-assist-context-action'))
    expect(openDrawer).toHaveBeenCalledTimes(2)
    expect(openDrawer.mock.calls[1]?.[0]).toMatchObject({
      mode: 'current_entity',
      scope: 'current_entity',
      context: { surface: 'atlas', tab: 'entities', entity_id: 9 },
    })

    await user.click(screen.getByTestId('atlas-assist-attention-action'))
    expect(onOpenDraftReview).toHaveBeenCalledWith('entities')

    expect(screen.getByTestId('world-generation-dialog')).toHaveTextContent('closed')
    await user.click(screen.getByTestId('atlas-assist-generate'))
    expect(screen.getByTestId('world-generation-dialog')).toHaveTextContent('open')
  })

  it('switches the contextual action to draft-cleanup when Atlas is already in review mode', async () => {
    const user = userEvent.setup()
    renderWorkbench({ tab: 'review', selectedEntityId: null, selectedEntityName: null })

    expect(screen.getByTestId('atlas-assist-sections')).toHaveAttribute('data-stage', 'governance')
    expect(screen.queryByTestId('atlas-assist-attention-banner')).not.toBeInTheDocument()
    expect(screen.queryByTestId('atlas-assist-open-review')).not.toBeInTheDocument()
    expect(screen.queryByTestId('atlas-assist-queue-meta')).not.toBeInTheDocument()
    expect(screen.getByTestId('atlas-assist-governance-section')).toHaveAttribute('data-prominence', 'default')

    await user.click(screen.getByTestId('atlas-assist-context-action'))

    expect(openDrawer).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'draft_cleanup',
        scope: 'current_tab',
        context: expect.objectContaining({ surface: 'atlas', tab: 'review' }),
      }),
      expect.anything(),
    )
  })

  it('keeps generation as an explicit review handoff instead of auto-opening review immediately', async () => {
    const user = userEvent.setup()
    const onOpenDraftReview = vi.fn()
    const onHandoffChange = vi.fn()
    renderWorkbench({ onOpenDraftReview, onHandoffChange })

    await user.click(screen.getByTestId('atlas-assist-generate'))
    await user.click(screen.getByTestId('mock-atlas-world-gen-success'))

    expect(onOpenDraftReview).not.toHaveBeenCalled()
    expect(onHandoffChange).toHaveBeenCalledWith({
      kind: 'generate_review',
      entityCount: 1,
      relationshipCount: 0,
      systemCount: 1,
    })
  })

  it('keeps worldpack import as an explicit in-place handoff instead of hard-navigating away', async () => {
    const user = userEvent.setup()
    const onHandoffChange = vi.fn()
    renderWorkbench({ onHandoffChange })

    await user.click(screen.getByTestId('atlas-assist-generate'))
    await user.click(screen.getByTestId('mock-atlas-world-import-success'))

    expect(onHandoffChange).toHaveBeenCalledWith({
      kind: 'generate_success',
      entityCount: 2,
      relationshipCount: 1,
      systemCount: 1,
    })
  })

  it('arms a pending extraction handoff so Atlas can upgrade the URL after async completion', async () => {
    const user = userEvent.setup()
    const onPendingHandoffChange = vi.fn()
    renderWorkbench({ onPendingHandoffChange })

    await user.click(screen.getByTestId('mock-bootstrap-start'))

    expect(onPendingHandoffChange).toHaveBeenCalledWith({
      kind: 'extract',
      startedAtMs: ACTIVE_PENDING_STARTED_AT,
      jobId: null,
    })

    await user.click(screen.getByTestId('mock-bootstrap-accepted'))

    expect(onPendingHandoffChange).toHaveBeenCalledWith({
      kind: 'extract',
      startedAtMs: ACTIVE_PENDING_STARTED_AT,
      jobId: 41,
    })
  })

  it('keeps the contextual action hidden on systems when no system-specific research launcher exists yet', () => {
    renderWorkbench({ tab: 'systems', selectedEntityId: null, selectedEntityName: null })

    expect(screen.queryByTestId('atlas-assist-context-action')).not.toBeInTheDocument()
  })

  it('waits for a selected entity before exposing relationship research', () => {
    renderWorkbench({ tab: 'relationships', selectedEntityId: null, selectedEntityName: null })

    expect(screen.queryByTestId('atlas-assist-context-action')).not.toBeInTheDocument()
  })

  it('routes backlog review CTA to the first real draft kind instead of the current Atlas tab', async () => {
    const user = userEvent.setup()
    const onOpenDraftReview = vi.fn()
    mockUseWorldEntities.mockReturnValue({ data: [{ id: 1 }] })
    mockUseWorldRelationships.mockReturnValue({ data: [] })
    mockUseWorldSystems.mockReturnValue({ data: [] })

    renderWorkbench({
      tab: 'relationships',
      onOpenDraftReview,
    })

    await user.click(screen.getByTestId('atlas-assist-attention-action'))

    expect(onOpenDraftReview).toHaveBeenCalledWith('entities')
  })

  it('keeps Atlas in attention mode while a URL-backed extraction handoff is still pending', () => {
    renderWorkbench({
      pending: {
        kind: 'extract',
        startedAtMs: ACTIVE_PENDING_STARTED_AT,
        jobId: 41,
      },
    })

    expect(screen.getByTestId('atlas-assist-sections')).toHaveAttribute('data-stage', 'attention')
    expect(screen.getByTestId('atlas-assist-attention-banner')).toHaveAttribute('data-tone', 'running')
    expect(screen.queryByTestId('atlas-assist-queue-meta')).not.toBeInTheDocument()
  })
})
