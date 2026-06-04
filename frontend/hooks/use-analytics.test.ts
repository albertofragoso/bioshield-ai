import { describe, it, expect, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { useRecordAnalyticsEvent } from './use-analytics'

vi.mock('@/lib/api/analytics', () => ({
  recordAnalyticsEvent: vi.fn(),
}))

import * as analyticsApi from '@/lib/api/analytics'

function makeWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('useRecordAnalyticsEvent', () => {
  it('calls recordAnalyticsEvent fire-and-forget', async () => {
    const mock = vi.mocked(analyticsApi.recordAnalyticsEvent).mockResolvedValue(undefined)
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false, networkMode: 'always' } },
    })

    const { result } = renderHook(() => useRecordAnalyticsEvent(), { wrapper: makeWrapper(queryClient) })
    const payload = { event_type: 'alt_page_opened' as const, payload: { barcode: 'abc' } }

    act(() => result.current.mutate(payload))
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mock.mock.calls[0][0]).toEqual(payload)
  })

  it('resolves the mutation — fire-and-forget handled at API layer', async () => {
    // recordAnalyticsEvent wraps its own errors (try/catch in analytics.ts).
    // The hook calls it as-is; error swallowing is the API function's responsibility.
    vi.mocked(analyticsApi.recordAnalyticsEvent).mockResolvedValue(undefined)
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false, networkMode: 'always' } },
    })

    const { result } = renderHook(() => useRecordAnalyticsEvent(), { wrapper: makeWrapper(queryClient) })
    act(() => result.current.mutate({ event_type: 'alt_page_opened' as const, payload: {} }))

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})
