import { describe, expect, it } from 'vitest'
import { getLlmApiErrorMessage, getLlmConfigWarning } from '@/lib/llmErrorMessages'
import { ApiError } from '@/services/api'

describe('llmErrorMessages', () => {
  it('maps incomplete BYOK config to actionable copy', () => {
    const err = new ApiError(400, 'HTTP 400', {
      code: 'llm_config_incomplete',
      detail: { code: 'llm_config_incomplete' },
    })

    expect(getLlmApiErrorMessage(err)).toContain('конфигурация BYOK неполна')
  })

  it('maps operator disable to explicit copy', () => {
    const err = new ApiError(503, 'HTTP 503', {
      code: 'ai_manually_disabled',
      detail: { code: 'ai_manually_disabled' },
    })

    expect(getLlmApiErrorMessage(err)).toContain('функции ИИ отключены')
  })

  it('maps duplicate-click admission errors to actionable copy', () => {
    const continuationErr = new ApiError(409, 'HTTP 409', {
      code: 'continuation_duplicate_request',
      detail: { code: 'continuation_duplicate_request' },
    })
    const bootstrapErr = new ApiError(409, 'HTTP 409', {
      code: 'bootstrap_index_already_fresh',
      detail: { code: 'bootstrap_index_already_fresh' },
    })

    expect(getLlmApiErrorMessage(continuationErr)).toContain('уже обрабатывается')
    expect(getLlmApiErrorMessage(bootstrapErr)).toContain('уже актуален')
  })

  it('warns when the current BYOK config is partial', () => {
    expect(
      getLlmConfigWarning({ baseUrl: 'https://example.com/v1', apiKey: '', model: '' }),
    ).toContain('только часть конфигурации BYOK')
    expect(
      getLlmConfigWarning({ baseUrl: 'https://example.com/v1', apiKey: 'k', model: 'm' }),
    ).toBeNull()
  })
})
