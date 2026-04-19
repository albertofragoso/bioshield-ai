"use client";

import { create } from "zustand";
import type { UserResponse } from "@/lib/api/types";

interface AuthState {
  user: UserResponse | null;
  setUser: (user: UserResponse | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  logout: () => set({ user: null }),
}));
