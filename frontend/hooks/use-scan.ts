'use client'

import { useMutation, useQuery } from '@tanstack/react-query'
import {
  getScanResult,
  getScanHistory,
  getAlternatives,
  getSharedScan,
  linkPhotoToBarcode,
  createShareLink,
  revokeShareLink,
  contributeToOff,
} from '@/lib/api/scan'
import type { ScanResponse } from '@/lib/api/types'

export const scanKeys = {
  result: (id: string) => ['scan', id] as const,
  history: (limit: number) => ['scan-history', limit] as const,
  alternatives: (barcode?: string) => ['alternatives', barcode] as const,
  shared: (token: string) => ['shared-scan', token] as const,
}

interface ScanResultOpts {
  refetchInterval?: number
  enabled?: boolean
  gcTime?: number
  refetchOnWindowFocus?: boolean
  initialData?: () => ScanResponse | undefined
  initialDataUpdatedAt?: () => number | undefined
}

export function useScanResult(id: string, opts?: ScanResultOpts) {
  return useQuery({
    queryKey: scanKeys.result(id),
    queryFn: () => getScanResult(id),
    staleTime: Infinity,
    enabled: opts?.enabled !== undefined ? opts.enabled && !!id : !!id,
    refetchInterval: opts?.refetchInterval,
    gcTime: opts?.gcTime,
    refetchOnWindowFocus: opts?.refetchOnWindowFocus ?? false,
    initialData: opts?.initialData,
    initialDataUpdatedAt: opts?.initialDataUpdatedAt,
  })
}

export function useScanHistory(limit = 10) {
  return useQuery({
    queryKey: scanKeys.history(limit),
    queryFn: () => getScanHistory(limit),
    staleTime: 60 * 1000,
    retry: false,
  })
}

export function useAlternatives(barcode?: string) {
  return useQuery({
    queryKey: scanKeys.alternatives(barcode),
    queryFn: () => getAlternatives(barcode!),
    staleTime: 5 * 60 * 1000,
    gcTime: 0,
    enabled: !!barcode,
  })
}

export function useSharedScan(token: string) {
  return useQuery({
    queryKey: scanKeys.shared(token),
    queryFn: () => getSharedScan(token),
    staleTime: Infinity,
  })
}

export function useLinkPhotoToBarcode() {
  return useMutation({
    mutationFn: ({ pseudoBarcode, barcode }: { pseudoBarcode: string; barcode: string }) =>
      linkPhotoToBarcode(pseudoBarcode, barcode),
  })
}

export function useCreateShareLink() {
  return useMutation({ mutationFn: createShareLink })
}

export function useRevokeShareLink() {
  return useMutation({ mutationFn: revokeShareLink })
}

export function useContributeToOff() {
  return useMutation({ mutationFn: contributeToOff })
}
