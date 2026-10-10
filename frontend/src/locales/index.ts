// Copyright (C) 2026 CenkorProcess Project
// SPDX-License-Identifier: AGPL-3.0
import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import enUS from './en-US'

const STORAGE_KEY = 'cenkorprocess-locale'

export type AppLocale = 'zh-CN' | 'en-US'

export function getStoredLocale(): AppLocale {
  const v = localStorage.getItem(STORAGE_KEY)
  if (v === 'en-US') return 'en-US'
  return 'zh-CN'
}

export function setStoredLocale(locale: AppLocale) {
  localStorage.setItem(STORAGE_KEY, locale)
}

export const i18n = createI18n({
  legacy: false,
  locale: getStoredLocale(),
  fallbackLocale: {
    'en-US': ['zh-CN'],
    default: ['zh-CN'],
  },
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})