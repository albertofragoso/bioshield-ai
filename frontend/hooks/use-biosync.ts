'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getBiomarkerStatus,
  extractBiomarkers,
  uploadBiomarkers,
  deleteBiomarkers,
} from '@/lib/api/biosync'
import type { BiomarkerUploadRequest } from '@/lib/api/types'

export const biosyncKeys = {
  status: () => ['biosync-status'] as const,
}

export function useBiomarkerStatus() {
  return useQuery({
    queryKey: biosyncKeys.status(),
    queryFn: getBiomarkerStatus,
    staleTime: 5 * 60 * 1000,
    retry: (_, err) => (err as { status?: number })?.status !== 404,
  })
}

export function useExtractBiomarkers() {
  return useMutation({ mutationFn: extractBiomarkers })
}

export function useUploadBiomarkers() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: uploadBiomarkers,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: biosyncKeys.status() }),
  })
}

export function useDeleteBiomarkers() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteBiomarkers,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: biosyncKeys.status() }),
  })
}
