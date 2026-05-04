import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { UiLocaleProvider } from '@/contexts/UiLocaleContext'
import { StudioWorldEntryPanel } from '@/components/studio/rail/StudioWorldEntryPanel'

const ACTIVE_PENDING_STARTED_AT = 2_000_000_000_000

vi.mock('@/components/world-model/shared/BootstrapPanel', () => ({
  BootstrapPanel: ({
    onLifecycleChange,
    onTriggerStart,
    onJobAccepted,
  }: {
    onLifecycleChange?: (state: unknown) => void
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
      <button
        type="button"
        data-testid="mock-bootstrap-complete"
        onClick={() => onLifecycleChange?.({
          phase: 'completed',
          summary: '2 实体 · 1 关系',
          requiresReview: true,
          entityCount: 2,
          relationshipCount: 1,
        })}
      >
        complete
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
    open ? (
      <>
        <button
          type="button"
          data-testid="mock-world-gen-success"
          onClick={() => onGenerateSuccess?.({
            entities_created: 1,
            relationships_created: 0,
            systems_created: 1,
            warnings: [],
          })}
        >
          generate-success
        </button>
        <button
          type="button"
          data-testid="mock-world-import-success"
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
    ) : null
  ),
}))

function renderPanel() {
  const onOpenAtlas = vi.fn()
  const onOpenAtlasReview = vi.fn()
  const onHandoffChange = vi.fn()
  const onPendingHandoffChange = vi.fn()
  const onWarmAtlas = vi.fn()

  render(
    <UiLocaleProvider>
      <MemoryRouter>
        <StudioWorldEntryPanel
          novelId={7}
          worldEntityCount={3}
          worldSystemCount={1}
          handoff={null}
          onHandoffChange={onHandoffChange}
          onPendingHandoffChange={onPendingHandoffChange}
          onOpenAtlas={onOpenAtlas}
          onOpenAtlasReview={onOpenAtlasReview}
          onWarmAtlas={onWarmAtlas}
          prominence="compact"
        />
      </MemoryRouter>
    </UiLocaleProvider>,
  )

  return { onOpenAtlas, onOpenAtlasReview, onHandoffChange, onPendingHandoffChange, onWarmAtlas }
}

describe('StudioWorldEntryPanel', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('keeps settings generation as a soft handoff until the user explicitly opens Atlas review', async () => {
    const user = userEvent.setup()
    const { onOpenAtlas, onOpenAtlasReview, onHandoffChange } = renderPanel()

    await user.click(screen.getByTestId('world-build-generate'))
    await user.click(screen.getByTestId('mock-world-gen-success'))

    expect(onHandoffChange).toHaveBeenCalledWith({
      kind: 'generate_review',
      entityCount: 1,
      relationshipCount: 0,
      systemCount: 1,
    })
    expect(onOpenAtlas).not.toHaveBeenCalled()
    expect(onOpenAtlasReview).not.toHaveBeenCalled()
  })

  it('keeps worldpack import as an in-place Studio handoff instead of navigating away immediately', async () => {
    const user = userEvent.setup()
    const { onOpenAtlas, onOpenAtlasReview, onHandoffChange } = renderPanel()

    await user.click(screen.getByTestId('world-build-generate'))
    await user.click(screen.getByTestId('mock-world-import-success'))

    expect(onHandoffChange).toHaveBeenCalledWith({
      kind: 'generate_success',
      entityCount: 2,
      relationshipCount: 1,
      systemCount: 1,
    })
    expect(onOpenAtlas).not.toHaveBeenCalled()
    expect(onOpenAtlasReview).not.toHaveBeenCalled()
  })

  it('keeps extraction handoff state visible instead of auto-dismissing it after completion', async () => {
    vi.useFakeTimers()
    const { onHandoffChange } = renderPanel()

    act(() => {
      screen.getByTestId('mock-bootstrap-complete').click()
    })
    expect(onHandoffChange).toHaveBeenCalledWith({
      kind: 'extract_review',
      entityCount: 2,
      relationshipCount: 1,
      systemCount: null,
    })

    act(() => {
      vi.advanceTimersByTime(15_000)
    })
  })

  it('arms a pending extraction handoff so later mounts can upgrade the URL after async completion', async () => {
    const user = userEvent.setup()
    const { onPendingHandoffChange } = renderPanel()

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

  it('warms Atlas when the handoff CTA receives hover or focus', async () => {
    const user = userEvent.setup()
    const { onWarmAtlas } = renderPanel()

    await user.hover(screen.getByTestId('studio-world-entry-handoff-action'))
    expect(onWarmAtlas).toHaveBeenCalledTimes(1)

    screen.getByTestId('studio-world-entry-handoff-action').focus()
    expect(onWarmAtlas).toHaveBeenCalledTimes(2)
  })
})
