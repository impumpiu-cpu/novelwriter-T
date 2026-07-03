import { describe, expect, it } from 'vitest'

// Тест полноты локалей: каждый ключ каталога должен разрешаться в каждой
// поддерживаемой локали (напрямую или через цепочку фолбэков), а базовые
// каталоги ru (локаль по умолчанию) и zh (исходный каталог) — быть полными.
// Регистрируем все route-scoped пакеты сообщений перед проверкой.
import '@/lib/uiMessagePacks/copilot'
import '@/lib/uiMessagePacks/home'
import '@/lib/uiMessagePacks/legal'
import '@/lib/uiMessagePacks/novel'

import { SUPPORTED_UI_LOCALES } from '@/lib/uiLocaleSchema'
import { translateUiMessage, uiMessages, type UiMessageKey } from '@/lib/uiMessages'

function collectAllKeys(): UiMessageKey[] {
  const keys = new Set<string>()
  for (const locale of SUPPORTED_UI_LOCALES) {
    for (const key of Object.keys(uiMessages[locale])) {
      keys.add(key)
    }
  }
  return [...keys].sort() as UiMessageKey[]
}

describe('ui message locale completeness', () => {
  const allKeys = collectAllKeys()

  it('has a non-empty message catalog', () => {
    expect(allKeys.length).toBeGreaterThan(0)
  })

  it.each(SUPPORTED_UI_LOCALES.map((locale) => [locale] as const))(
    'resolves every catalog key for locale "%s" without a missing marker',
    (locale) => {
      const missing = allKeys.filter((key) =>
        translateUiMessage(locale, key, {}).startsWith('[missing:'),
      )
      expect(missing).toEqual([])
    },
  )

  it.each([['ru'], ['zh']] as const)(
    'keeps the "%s" catalog complete without relying on fallback locales',
    (locale) => {
      const missing = allKeys.filter((key) => uiMessages[locale][key] === undefined)
      expect(missing).toEqual([])
    },
  )
})
