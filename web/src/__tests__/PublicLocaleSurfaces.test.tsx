import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import '@/lib/uiMessagePacks/home'
import { UiLocaleProvider } from '@/contexts/UiLocaleContext'
import { HeroSection } from '@/components/home/HeroSection'
import { HomeDeferredSections } from '@/components/home/HomeDeferredSections'
import Settings from '@/pages/Settings'
import Terms from '@/pages/Terms'

const authState = vi.hoisted(() => ({
  value: {
    isLoggedIn: false,
    user: null,
    logout: vi.fn(),
    refreshQuota: vi.fn(),
  },
}))

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => authState.value,
}))

function setEnglishLocale() {
  localStorage.setItem('novwr_ui_locale', 'en')
  document.documentElement.lang = 'en'
}

function renderWithLocale(element: ReactNode) {
  return render(
    <UiLocaleProvider>
      <MemoryRouter>{element}</MemoryRouter>
    </UiLocaleProvider>,
  )
}

describe('public locale surfaces', () => {
  beforeEach(() => {
    vi.unstubAllEnvs()
    vi.stubEnv('VITE_DEPLOY_MODE', 'hosted')
    localStorage.clear()
    document.documentElement.lang = 'zh-CN'
    authState.value = {
      isLoggedIn: false,
      user: null,
      logout: vi.fn(),
      refreshQuota: vi.fn(),
    }
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('renders the marketing home copy in English', async () => {
    setEnglishLocale()

    renderWithLocale(
      <>
        <HeroSection />
        <HomeDeferredSections />
      </>,
    )

    expect(screen.getByRole('heading', { name: /Understand the world first\.\s*Write better stories\./ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Try Journey to the West Demo' })).toHaveAttribute('href', '/demo')
    expect(await screen.findByText('THREE SURFACES')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Studio, Atlas, and Copilot all work on the same novel.' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Five steps from raw text to grounded continuation.' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Writers of long-form fiction know these details matter.' })).toBeInTheDocument()
    expect(screen.queryByText('三个界面')).not.toBeInTheDocument()
    expect(screen.queryByText('设计细节')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Terms of use' })).toBeVisible()
  })

  it('renders the settings surface in English', () => {
    setEnglishLocale()
    authState.value = {
      isLoggedIn: true,
      user: {
        id: 1,
        username: 'omega',
        display_name: 'Omega',
        generation_quota: 5,
      },
      logout: vi.fn(),
      refreshQuota: vi.fn(),
    }

    renderWithLocale(<Settings />)

    expect(screen.getByRole('heading', { name: 'Settings' })).toBeVisible()
    expect(screen.getByText('Interface language')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Test connection' })).not.toBeInTheDocument()
    expect(screen.getByText('Hosted beta uses platform-managed AI credentials only', { exact: false })).toBeVisible()
    expect(screen.getByText('Nickname')).toBeVisible()
    expect(screen.getByText('Log out')).toBeVisible()
  })

  it('renders the legal terms page in English', () => {
    setEnglishLocale()

    renderWithLocale(<Terms />)

    expect(screen.getByRole('heading', { name: 'Terms of use' })).toBeVisible()
    expect(screen.getByText('Before using the service, we also recommend reading the', { exact: false })).toBeVisible()
    expect(screen.getAllByRole('link', { name: 'Privacy notice' })[0]).toBeVisible()
    expect(screen.getAllByRole('link', { name: 'Copyright notice' })[0]).toBeVisible()
  })
})
