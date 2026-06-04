'use client'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { login, register, logout } from '@/lib/api/auth'
import type { LoginRequest, RegisterRequest } from '@/lib/api/types'

export function useLogin() {
  return useMutation({ mutationFn: login })
}

export function useRegister() {
  return useMutation({
    mutationFn: async (body: RegisterRequest) => {
      await register(body)
      await login(body as LoginRequest)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      await queryClient.cancelQueries()
      queryClient.removeQueries({ predicate: () => true })
    },
  })
}
