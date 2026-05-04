import { test, expect } from '@playwright/test'
import { mockAllApiRoutes } from '../fixtures/api-helpers'

test.describe('Novel Copilot (mock)', () => {
  test('Atlas assist workbench opens the whole-book research drawer', async ({ page }) => {
    await mockAllApiRoutes(page)
    await page.goto('/world/1')
    const drawer = page.getByTestId('novel-copilot-drawer')

    await expect(page.getByTestId('atlas-assist-workbench')).toBeVisible()
    await expect(page.getByTestId('atlas-assist-open-whole-book')).toBeVisible()
    await expect(page.getByTestId('atlas-assist-generate')).toBeVisible()
    await expect(page.getByTestId('world-build-panel')).toHaveCount(0)

    await page.getByTestId('atlas-assist-open-whole-book').click()

    await expect(drawer).toHaveAttribute('data-state', 'open')
    await expect(drawer.getByText('全书研究').first()).toBeVisible()
    await expect(drawer.getByText('研究工作台')).toBeVisible()
    await expect(drawer.getByText('盘点设定缺口')).toBeVisible()
  })

  test('light theme keeps multi-session copilot navigation usable', async ({ page }) => {
    await mockAllApiRoutes(page)
    await page.addInitScript(() => {
      localStorage.setItem('novwr_theme', 'light')
    })
    const drawer = page.getByTestId('novel-copilot-drawer')

    await page.route(/\/api\/novels\/1\/world\/entities(?:\/101)?(?:\?.*)?$/, async (route) => {
      if (route.request().method() !== 'GET') return route.abort('blockedbyclient')
      const { pathname } = new URL(route.request().url())

      if (pathname.endsWith('/world/entities/101')) {
        return route.fulfill({
          json: {
            id: 101,
            novel_id: 1,
            name: '苏瑶',
            entity_type: 'Character',
            description: '',
            aliases: [],
            attributes: [],
            status: 'confirmed',
            created_at: '2026-03-01T00:00:00Z',
            updated_at: '2026-03-01T00:00:00Z',
          },
        })
      }

      return route.fulfill({
        json: [{
          id: 101,
          novel_id: 1,
          name: '苏瑶',
          entity_type: 'Character',
          description: '',
          aliases: [],
          attributes: [],
          status: 'confirmed',
          created_at: '2026-03-01T00:00:00Z',
          updated_at: '2026-03-01T00:00:00Z',
        }],
      })
    })

    await page.goto('/world/1?tab=entities')
    await expect(page.locator('html')).toHaveClass(/light/)
    await expect(page.getByTestId('atlas-assist-open-whole-book')).toBeVisible()

    await page.getByTestId('atlas-assist-open-whole-book').click()
    await expect(drawer).toHaveAttribute('data-state', 'open')
    await expect(page.getByTestId('novel-copilot-session-strip').getByText('全书探索')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('novel-copilot-drawer')).toHaveCount(0)

    await page.getByTestId('entity-row-101').focus()
    await page.getByTestId('entity-row-101').press('Enter')
    await expect(page.getByTestId('entity-detail')).toBeVisible()
    await page.getByRole('button', { name: /AI 补完/ }).click()

    await expect(drawer).toHaveAttribute('data-state', 'open')
    await expect(page.getByTestId('novel-copilot-session-strip').getByText('苏瑶')).toBeVisible()
    await expect(drawer.getByText('实体补完')).toBeVisible()

    await page.keyboard.press('Escape')
    await expect(page.getByTestId('novel-copilot-drawer')).toHaveCount(0)
    await page.getByTestId('tab-relationships').click()
    await expect(page.getByTestId('relationship-sidebar-panel')).toBeVisible()
    await expect(page.getByRole('button', { name: /AI 建议/ })).toHaveCount(0)
    await page.getByTestId('atlas-assist-context-action').click()

    await expect(page.getByTestId('novel-copilot-session-strip').getByText('苏瑶 ↔ 相关实体')).toBeVisible()
    await expect(page.getByTestId('novel-copilot-session-strip').getByText(/^苏瑶$/)).toBeVisible()
    await expect(page.getByTestId('novel-copilot-session-strip').getByText('3 个会话')).toBeVisible()
    await expect(drawer.getByText(/^关系研究$/)).toBeVisible()
  })

  test('Copilot contextual trigger from Entity Detail', async ({ page }) => {
    await mockAllApiRoutes(page)
    const drawer = page.getByTestId('novel-copilot-drawer')

    await page.route(/\/api\/novels\/1\/world\/entities(?:\/101)?(?:\?.*)?$/, async (route) => {
      if (route.request().method() !== 'GET') return route.abort('blockedbyclient')
      const { pathname } = new URL(route.request().url())

      if (pathname.endsWith('/world/entities/101')) {
        return route.fulfill({
          json: {
            id: 101,
            novel_id: 1,
            name: '苏瑶',
            entity_type: 'Character',
            description: '',
            aliases: [],
            attributes: [],
            status: 'confirmed',
            created_at: '2026-03-01T00:00:00Z',
            updated_at: '2026-03-01T00:00:00Z',
          },
        })
      }

      return route.fulfill({
        json: [{
          id: 101,
          novel_id: 1,
          name: '苏瑶',
          entity_type: 'Character',
          description: '',
          aliases: [],
          attributes: [],
          status: 'confirmed',
          created_at: '2026-03-01T00:00:00Z',
          updated_at: '2026-03-01T00:00:00Z',
        }],
      })
    })

    await page.goto('/world/1?tab=entities')

    // Expect sidebar list item to be rendered
    await expect(page.getByTestId('entity-row-101')).toBeVisible()

    // Select entity
    await page.getByTestId('entity-row-101').focus()
    await page.getByTestId('entity-row-101').press('Enter')

    // Wait for the detail view to be populated
    await expect(page.getByTestId('entity-detail')).toBeVisible()

    // Click trigger from Entity Detail
    await page.getByRole('button', { name: /AI 补完/ }).click()

    // Drawer opens with current_entity scope
    await expect(drawer).toHaveAttribute('data-state', 'open')
    await expect(page.getByRole('heading', { name: 'Novel Copilot' })).toBeVisible()
    await expect(drawer.getByText('实体上下文').first()).toBeVisible()
    await expect(page.getByTestId('novel-copilot-session-strip').getByText('苏瑶')).toBeVisible()

    // Default landing state should indicate the entity-specific workbench
    await expect(drawer.getByText('实体补完')).toBeVisible()
    await expect(drawer.getByText('补完当前实体')).toBeVisible()
  })

  test('Copilot contextual trigger from Relationships tab', async ({ page }) => {
    await mockAllApiRoutes(page)
    const drawer = page.getByTestId('novel-copilot-drawer')

    await page.route('**/api/novels/1/world/entities**', async (route) => {
      if (route.request().method() !== 'GET') return route.abort('blockedbyclient')
      return route.fulfill({ json: [{ id: 101, novel_id: 1, name: '苏瑶', entity_type: 'Character', description: '', aliases: [], attributes: [], status: 'confirmed', created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' }] })
    })

    await page.goto('/world/1?tab=relationships')

    // Sidebar should display relation sidebar section
    await expect(page.getByTestId('relationship-sidebar-panel')).toBeVisible()
    await expect(page.getByTestId('entity-row-101')).toBeVisible()

    // Select the center entity so the session title is explicit
    await page.getByTestId('entity-row-101').focus()
    await page.getByTestId('entity-row-101').press('Enter')

    // Atlas now owns the relationship research launcher in the assist workbench.
    await expect(page.getByRole('button', { name: /AI 建议/ })).toHaveCount(0)
    await page.getByTestId('atlas-assist-context-action').click()

    // Drawer opens in the relationship context for the selected entity
    await expect(drawer).toHaveAttribute('data-state', 'open')
    await expect(page.getByRole('heading', { name: 'Novel Copilot' })).toBeVisible()
    await expect(drawer.getByText('关系上下文').first()).toBeVisible()
    await expect(page.getByTestId('novel-copilot-session-strip').getByText('苏瑶 ↔ 相关实体')).toBeVisible()
    await expect(drawer.getByText(/^关系研究$/)).toBeVisible()
    await expect(drawer.getByText('补全缺失关系')).toBeVisible()
  })
})
