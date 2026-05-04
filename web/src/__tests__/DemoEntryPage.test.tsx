import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { createTestQueryClient } from '@/__tests__/support/queryClient'

const { authState, listNovelsMock } = vi.hoisted(() => ({
  authState: {
    isLoggedIn: false,
    isLoading: false,
  },
  listNovelsMock: vi.fn(),
}))

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => authState,
}))

vi.mock('@/services/api', () => ({
  api: {
    listNovels: listNovelsMock,
  },
}))

import { DemoEntryPage } from '@/pages/DemoEntryPage'

function LocationProbe() {
  const location = useLocation()
  return (
    <>
      <div data-testid="location-path">{location.pathname}{location.search}</div>
      <div data-testid="location-state">{JSON.stringify(location.state ?? null)}</div>
    </>
  )
}

function renderDemoEntry(initialPath = '/demo') {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/demo" element={<DemoEntryPage />} />
          <Route path="/login" element={<LocationProbe />} />
          <Route path="/library" element={<LocationProbe />} />
          <Route path="/novel/:novelId" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('DemoEntryPage', () => {
  beforeEach(() => {
    authState.isLoggedIn = false
    authState.isLoading = false
    listNovelsMock.mockReset()
  })

  it('sends signed-out users through login while preserving the demo intent', async () => {
    renderDemoEntry('/demo')

    await waitFor(() => {
      expect(screen.getByTestId('location-path')).toHaveTextContent('/login')
    })
    expect(screen.getByTestId('location-state')).toHaveTextContent('{"from":"/demo"}')
    expect(listNovelsMock).not.toHaveBeenCalled()
  })

  it('opens the seeded demo studio for signed-in users', async () => {
    authState.isLoggedIn = true
    listNovelsMock.mockResolvedValue([
      { id: 3, is_seeded_demo: false },
      { id: 9, is_seeded_demo: true },
    ])

    renderDemoEntry('/demo')

    await waitFor(() => {
      expect(screen.getByTestId('location-path')).toHaveTextContent('/novel/9?demoGuide=open')
    })
  })

  it('falls back to library when no seeded demo exists', async () => {
    authState.isLoggedIn = true
    listNovelsMock.mockResolvedValue([{ id: 3, is_seeded_demo: false }])

    renderDemoEntry('/demo')

    await waitFor(() => {
      expect(screen.getByTestId('location-path')).toHaveTextContent('/library')
    })
  })
})
