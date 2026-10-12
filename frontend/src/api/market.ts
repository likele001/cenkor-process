// Copyright (C) 2026 CenkorProcess Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

/** 应用中心应用项（hub 目录 + 已购授权 + 本地已装 合并视图） */
export interface MarketApp {
  key: string
  name: string
  description: string
  icon: string
  category: string
  latest_version: string
  price: number | null
  licensed: boolean
  license_state: string
  license_expires_at: string | null
  bound_instances: number
  max_instances: number
  installed: boolean
  installed_version: string
  enabled: boolean
}

/** 连接状态（hub 地址 / 绑定账号） */
export interface MarketStatus {
  hub_url: string
  product: string
  bound: boolean
  account: string
  instance_uid: string
  /** 最近一次授权快照同步时 hub 是否可达；null = 还没同步过（未绑定或刚重启） */
  hub_reachable?: boolean | null
  /** 已购且仍在有效期内的扩展数（含未安装的） */
  purchased_count?: number
  /** 已装、且 hub 上有更新版本的扩展数；hub 未给版本号时不计入 */
  updatable_count?: number
  /** 最早到期的授权（ISO 字符串）；全部为买断则 null */
  nearest_expiry?: string | null
  /** 以上统计所依据的快照时间 */
  snapshot_synced_at?: string
}

/** 设备码绑定：发起后返回给用户去门户确认的信息 */
export interface BindStartResult {
  user_code: string
  verification_uri: string
  verification_uri_complete?: string
  expires_in: number
  interval: number
}

/** 设备码轮询结果 */
export interface BindPollResult {
  status: 'idle' | 'pending' | 'approved' | 'expired' | 'denied' | 'consumed' | 'error'
  account?: string
  message?: string
}

export function getMarketStatus() {
  return http.get<MarketStatus>('/v1/market/status')
}

export function saveMarketHub(hubUrl: string) {
  return http.put<{ message: string; hub_url: string }>('/v1/market/hub', { hub_url: hubUrl })
}

export function bindStart() {
  return http.post<BindStartResult>('/v1/market/bind/start')
}

export function bindPoll() {
  return http.get<BindPollResult>('/v1/market/bind/poll')
}

export function bindCancel() {
  return http.post<{ message: string }>('/v1/market/bind/cancel')
}

export function bindUnbind() {
  return http.post<{ message: string }>('/v1/market/bind/unbind')
}

export function getMarketApps() {
  return http.get<{
    items: MarketApp[]
    hub_url: string
    bound: boolean
    account: string
  }>('/v1/market/apps')
}

export function installMarketApp(appKey: string) {
  return http.post<{ message: string; key: string; version: string; path: string; hot_loaded: boolean }>(
    '/v1/market/install',
    { app_key: appKey },
  )
}

export function uninstallMarketApp(appKey: string) {
  return http.post<{ message: string; key: string }>('/v1/market/uninstall', { app_key: appKey })
}

/** 本地启停（复用扩展宿主已有端点） */
export function enableExtension(key: string) {
  return http.post<{ key: string; enabled: boolean }>(`/v1/extensions/${key}/enable`)
}

export function disableExtension(key: string) {
  return http.post<{ key: string; enabled: boolean }>(`/v1/extensions/${key}/disable`)
}
