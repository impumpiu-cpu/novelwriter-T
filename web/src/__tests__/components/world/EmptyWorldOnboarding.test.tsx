import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { EmptyWorldOnboarding } from '@/components/detail/EmptyWorldOnboarding'

vi.mock('@/contexts/UiLocaleContext', () => ({
  useUiLocale: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('@/components/ui/glass-surface', () => ({
  GlassSurface: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

describe('EmptyWorldOnboarding', () => {
  function setup(overrides?: Parameters<typeof EmptyWorldOnboarding>[0]) {
    const props: Parameters<typeof EmptyWorldOnboarding>[0] = {
      onGenerate: vi.fn(),
      onBootstrap: vi.fn(),
      onDismiss: vi.fn(),
      ...overrides,
    }
    render(<EmptyWorldOnboarding {...props} />)
    return props
  }

  it('enables extract and shows default description when chapters are available', () => {
    setup({ onBootstrap: vi.fn(), onGenerate: vi.fn(), onDismiss: vi.fn(), chaptersAvailable: true })

    const extract = screen.getByTestId('world-onboarding-bootstrap') as HTMLButtonElement
    expect(extract.disabled).toBe(false)
    expect(screen.getByText('worldModel.onboarding.extractDescription')).toBeInTheDocument()
    expect(screen.queryByText('worldModel.onboarding.extractUnavailable')).not.toBeInTheDocument()
  })

  it('disables extract and swaps description when chapters are not yet available', async () => {
    const onBootstrap = vi.fn()
    setup({ onBootstrap, onGenerate: vi.fn(), onDismiss: vi.fn(), chaptersAvailable: false })

    const extract = screen.getByTestId('world-onboarding-bootstrap') as HTMLButtonElement
    expect(extract.disabled).toBe(true)
    expect(screen.getByText('worldModel.onboarding.extractUnavailable')).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(extract)
    expect(onBootstrap).not.toHaveBeenCalled()
  })

  it('disables extract while a bootstrap trigger is pending', () => {
    setup({ onBootstrap: vi.fn(), onGenerate: vi.fn(), onDismiss: vi.fn(), bootstrapPending: true })

    const extract = screen.getByTestId('world-onboarding-bootstrap') as HTMLButtonElement
    expect(extract.disabled).toBe(true)
    expect(screen.getByText('worldModel.common.processing')).toBeInTheDocument()
  })
})
