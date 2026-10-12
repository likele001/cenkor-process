// Copyright (C) 2026 CenkorProcess Project
// SPDX-License-Identifier: AGPL-3.0
import { useI18n } from 'vue-i18n'

export type TagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const TAG_MAP: Record<string, TagType> = {
  released: 'success',
  completed: 'success',
  pass: 'success',
  passed: 'success',
  ok: 'success',
  done: 'success',
  // 库存批次收货后停在 received（待放行），须检验单判定才转 released —— 用琥珀色标出待办
  received: 'warning',
  draft: 'info',
  drafted: 'info',
  planned: 'info',
  pending: 'info',
  hold: 'info',
  archived: 'info',
  consumed: 'info',
  in_progress: 'warning',
  running: 'warning',
  frozen: 'warning',
  quarantined: 'warning',
  deviation: 'warning',
  rejected: 'danger',
  fail: 'danger',
  expired: 'danger',
  voided: 'danger',
}

export function useStatus() {
  const { t, te } = useI18n()

  function label(status?: string | null): string {
    if (!status) return '—'
    return te(`status.${status}`) ? t(`status.${status}`) : status
  }

  function tagType(status?: string | null): TagType {
    if (!status) return 'info'
    return TAG_MAP[status] ?? 'info'
  }

  return { label, tagType }
}