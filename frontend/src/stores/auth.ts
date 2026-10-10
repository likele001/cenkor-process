// Copyright (C) 2026 CenkorProcess Project
// SPDX-License-Identifier: AGPL-3.0
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { LoginIn, MeOut } from '@/api/auth'
import { loginApi, meApi } from '@/api/auth'
import { clearToken, getToken, setToken } from '@/utils/token'

/** JWT 账号密码登录态（对齐 CenkorMES）：/auth/login → Bearer Token → /auth/me */
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const me = ref<MeOut | null>(null)
  const permissions = computed(() => me.value?.permissions ?? [])

  const hasKey = computed(() => Boolean(token.value))

  function hasAnyPermission(codes?: string[] | string): boolean {
    if (!codes) return true
    const need = Array.isArray(codes) ? codes : [codes]
    if (need.length === 0) return true
    const set = new Set(permissions.value)
    return need.some((x) => set.has(x))
  }

  async function login(payload: LoginIn) {
    const res = await loginApi(payload)
    token.value = res.access_token
    setToken(res.access_token, Boolean(payload.remember_me))
    await fetchMe()
  }

  async function fetchMe() {
    const data = await meApi()
    me.value = data
  }

  function logout() {
    token.value = null
    me.value = null
    clearToken()
  }

  return { token, me, permissions, hasKey, hasAnyPermission, login, fetchMe, logout }
})