'use client'

import { useMutation } from '@tanstack/react-query'
import { recordAnalyticsEvent } from '@/lib/api/analytics'

export function useRecordAnalyticsEvent() {
  return useMutation({ mutationFn: recordAnalyticsEvent })
}
