import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { UiLocaleProvider } from '@/contexts/UiLocaleContext'
import { ContinuationResultsStage } from '@/components/studio/stages/ContinuationResultsStage'
import { createTestQueryClient } from '@/__tests__/support/queryClient'

const mockUseAuth = vi.fn()

vi.mock('@/components/ui/plain-text-content', () => ({
  PlainTextContent: ({
    content,
    emptyLabel,
  }: {
    content?: string | null
    emptyLabel?: string
  }) => <div data-testid="plain-text-content">{content || emptyLabel}</div>,
}))

vi.mock('@/components/feedback/FeedbackForm', () => ({
  FeedbackForm: () => null,
}))

vi.mock('@/components/generation/DriftWarningPopover', () => ({
  DriftWarningPopover: () => null,
}))

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: (...args: unknown[]) => mockUseAuth(...args),
}))

vi.mock('@/services/api', () => ({
  api: {
    getContinuations: vi.fn(),
    continueNovel: vi.fn(),
    createChapter: vi.fn(),
    submitFeedback: vi.fn(),
  },
  streamContinuation: vi.fn(),
  buildContinuationRequestId: vi.fn(() => 'test-continuation-request-id'),
  ApiError: class ApiError extends Error {
    status: number

    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

import { api, streamContinuation } from '@/services/api'

const mockGetContinuations = api.getContinuations as ReturnType<typeof vi.fn>
const mockContinueNovel = api.continueNovel as ReturnType<typeof vi.fn>
const mockStreamContinuation = streamContinuation as ReturnType<typeof vi.fn>

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location-search">{location.search}</div>
}

describe('ContinuationResultsStage runtime', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()

    mockUseAuth.mockReturnValue({
      user: { feedback_submitted: false },
      refreshQuota: vi.fn().mockResolvedValue(undefined),
    })

    mockGetContinuations.mockResolvedValue([
      {
        id: 101,
        novel_id: 7,
        content: '已持久化的续写结果',
        created_at: '2026-03-03T00:00:00Z',
      },
    ])
    mockContinueNovel.mockResolvedValue({
      continuations: [],
      debug: {
        context_chapters: 3,
        injected_systems: [],
        injected_entities: [],
        injected_relationships: [],
        relevant_entity_ids: [],
        ambiguous_keywords_disabled: [],
        drift_warnings: [],
        prose_warnings: [],
      },
    })
  })

  it('recovers persisted results inside the embedded studio results stage without hook-order crashes', async () => {
    const queryClient = createTestQueryClient()
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <UiLocaleProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/novel/7?stage=results&chapter=3&continuations=0:101&total_variants=1']}>
            <Routes>
              <Route
                path="/novel/:novelId"
                element={(
                  <ContinuationResultsStage
                    novelId={7}
                    activeChapterNum={3}
                    showInjectionSummaryRail={false}
                    onToggleInjectionSummaryRail={vi.fn()}
                    onDebugChange={vi.fn()}
                  />
                )}
              />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </UiLocaleProvider>,
    )

    expect(screen.getByText('正在加载续写结果...')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByTestId('plain-text-content')).toHaveTextContent('已持久化的续写结果')
    })

    expect(mockGetContinuations).toHaveBeenCalledWith(7, [101])
    expect(
      consoleErrorSpy.mock.calls.some((call) => call.some((arg) => String(arg).includes('Rendered more hooks than during the previous render'))),
    ).toBe(false)

    consoleErrorSpy.mockRestore()
  })

  it('falls back to non-stream continuation when early streaming transport fails', async () => {
    const queryClient = createTestQueryClient()

    mockStreamContinuation.mockReturnValue({
      [Symbol.asyncIterator]() {
        return {
          async next() {
            throw new Error('Malformed NDJSON line: {bad-json}')
          },
        }
      },
    })
    mockContinueNovel.mockResolvedValue({
      continuations: [
        {
          id: 201,
          novel_id: 7,
          chapter_number: 4,
          content: '这是稳定返回的续写结果',
          rating: null,
          created_at: '2026-03-21T00:00:00Z',
        },
      ],
      debug: {
        context_chapters: 3,
        injected_systems: [],
        injected_entities: [],
        injected_relationships: [],
        relevant_entity_ids: [],
        ambiguous_keywords_disabled: [],
        drift_warnings: [],
        prose_warnings: [],
      },
    })

    render(
      <UiLocaleProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter
            initialEntries={[
              {
                pathname: '/novel/7',
                search: '?stage=results&chapter=3',
                state: {
                  novelId: 7,
                  streamParams: { num_versions: 1 },
                },
              },
            ]}
          >
            <Routes>
              <Route
                path="/novel/:novelId"
                element={(
                  <>
                    <ContinuationResultsStage
                      novelId={7}
                      activeChapterNum={3}
                      showInjectionSummaryRail={false}
                      onToggleInjectionSummaryRail={vi.fn()}
                      onDebugChange={vi.fn()}
                    />
                    <LocationProbe />
                  </>
                )}
              />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </UiLocaleProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('plain-text-content')).toHaveTextContent('这是稳定返回的续写结果')
    })

    expect(screen.getByText('当前网络不适合实时流式输出，已自动切换到稳定返回模式。')).toBeVisible()
    expect(mockStreamContinuation).toHaveBeenCalledWith(
      7,
      { num_versions: 1 },
      expect.objectContaining({ continuationRequestId: 'test-continuation-request-id' }),
    )
    expect(mockContinueNovel).toHaveBeenCalledWith(
      7,
      { num_versions: 1 },
      {
        deliveryMode: 'stream-fallback',
        continuationRequestId: 'test-continuation-request-id',
      },
    )
    await waitFor(() => {
      expect(screen.getByTestId('location-search')).toHaveTextContent('continuations=0%3A201')
      expect(screen.getByTestId('location-search')).toHaveTextContent('total_variants=1')
    })
  })
})
