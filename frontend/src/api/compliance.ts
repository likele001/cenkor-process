// Copyright (C) 2026 CenkorProcess Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

// ---------- HACCP / CCP ----------
export type CcpOut = {
  id: number
  code: string
  name: string
  process_step: string | null
  param_key: string
  uom_id: number | null
  limit_min: string | null
  limit_max: string | null
  target_value: string | null
  critical: boolean
  monitor_freq: string | null
  corrective_action: string | null
  is_active: boolean
}

export type CcpIn = {
  code: string
  name: string
  process_step?: string | null
  param_key?: string
  uom_id?: number | null
  limit_min?: string | number | null
  limit_max?: string | number | null
  target_value?: string | number | null
  critical?: boolean
  monitor_freq?: string | null
  corrective_action?: string | null
}

export type CcpRecordOut = {
  id: number
  ccp_id: number
  batch_id: number | null
  operation_id: number | null
  lot_id: number | null
  measured_value: string
  uom_id: number | null
  measured_at: string
  operator_id: number | null
  status: string
  deviation_note: string | null
  corrective_action: string | null
  verified_by: number | null
  verified_at: string | null
}

export type CcpRecordIn = {
  ccp_id: number
  batch_id?: number | null
  operation_id?: number | null
  lot_id?: number | null
  measured_value: string | number
  uom_id?: number | null
  measured_at?: string | null
  operator_id?: number | null
  deviation_note?: string | null
  corrective_action?: string | null
}

// ---------- CIP ----------
export type CipLogOut = {
  id: number
  station: string
  batch_id: number | null
  cip_type: string
  start_at: string
  end_at: string | null
  duration_min: number | null
  caustic_conc_pct: string | null
  caustic_temp_c: string | null
  acid_conc_pct: string | null
  acid_temp_c: string | null
  rinse_conductivity: string | null
  final_rinse_ph: string | null
  result: string
  operator_id: number | null
  note: string | null
}

export type CipLogIn = {
  station: string
  batch_id?: number | null
  cip_type?: string
  start_at: string
  end_at?: string | null
  duration_min?: number | null
  caustic_conc_pct?: string | number | null
  caustic_temp_c?: string | number | null
  acid_conc_pct?: string | number | null
  acid_temp_c?: string | number | null
  rinse_conductivity?: string | number | null
  final_rinse_ph?: string | number | null
  operator_id?: number | null
  note?: string | null
}

// ---------- CoA ----------
export type CoaOut = {
  id: number
  coa_no: string
  lot_id: number | null
  material_id: number
  batch_id: number | null
  direction: string
  sample_at: string | null
  tested_at: string | null
  tester_id: number | null
  result: string
  items: Array<Record<string, unknown>> | null
  released_by: number | null
  released_at: string | null
  locked: boolean
  note: string | null
  created_at: string
}

export type CoaIn = {
  material_id: number
  coa_no?: string | null
  lot_id?: number | null
  batch_id?: number | null
  direction?: string
  sample_at?: string | null
  tested_at?: string | null
  tester_id?: number | null
  items?: Array<Record<string, unknown>>
  note?: string | null
}

export type CoaDecideIn = {
  result: 'pass' | 'fail' | 'hold'
  released_by?: number | null
  note?: string | null
}

// ---------- 时间-温度 ----------
export type TempLogOut = {
  id: number
  batch_id: number | null
  operation_id: number | null
  ccp_id: number | null
  station: string | null
  stage: string
  recorded_at: string
  temp_c: string
  duration_min: number | null
  in_range: boolean
  note: string | null
}

export type TempLogIn = {
  temp_c: string | number
  batch_id?: number | null
  operation_id?: number | null
  ccp_id?: number | null
  station?: string | null
  stage?: string
  recorded_at?: string | null
  duration_min?: number | null
  note?: string | null
}

export type TempLogCreateOut = {
  log: TempLogOut
  in_range: boolean
  alert_raised: boolean
}

export type ComplianceAlertOut = {
  ccp_deviations: Array<Record<string, unknown>>
  temp_out_of_range: Array<Record<string, unknown>>
  cip_failed: Array<Record<string, unknown>>
  coa_failed: Array<Record<string, unknown>>
  total: number
}

export const complianceApi = {
  // CCP
  listCcps(params?: { active_only?: boolean }) {
    return http.request<CcpOut[]>({ url: '/v1/ccps', method: 'GET', params })
  },
  createCcp(data: CcpIn) {
    return http.request<CcpOut>({ url: '/v1/ccps', method: 'POST', data })
  },
  getCcp(id: number) {
    return http.request<CcpOut>({ url: `/v1/ccps/${id}`, method: 'GET' })
  },

  // CCP 监控记录
  listCcpRecords(params?: { ccp_id?: number; batch_id?: number; status?: string }) {
    return http.request<CcpRecordOut[]>({ url: '/v1/ccp-records', method: 'GET', params })
  },
  createCcpRecord(data: CcpRecordIn) {
    return http.request<CcpRecordOut>({ url: '/v1/ccp-records', method: 'POST', data })
  },
  batchCcpRecords(batchId: number) {
    return http.request<CcpRecordOut[]>({ url: `/v1/batches/${batchId}/ccp-records`, method: 'GET' })
  },

  // CIP
  listCipLogs(params?: { station?: string; batch_id?: number; result?: string }) {
    return http.request<CipLogOut[]>({ url: '/v1/cip-logs', method: 'GET', params })
  },
  createCipLog(data: CipLogIn) {
    return http.request<CipLogOut>({ url: '/v1/cip-logs', method: 'POST', data })
  },

  // CoA
  listCoa(params?: { lot_id?: number; material_id?: number; result?: string }) {
    return http.request<CoaOut[]>({ url: '/v1/coa', method: 'GET', params })
  },
  getCoa(id: number) {
    return http.request<CoaOut>({ url: `/v1/coa/${id}`, method: 'GET' })
  },
  createCoa(data: CoaIn) {
    return http.request<CoaOut>({ url: '/v1/coa', method: 'POST', data })
  },
  decideCoa(id: number, data: CoaDecideIn) {
    return http.request<Record<string, unknown>>({ url: `/v1/coa/${id}/decide`, method: 'POST', data })
  },

  // 时间-温度
  listTempLogs(params?: { batch_id?: number; ccp_id?: number; in_range?: boolean }) {
    return http.request<TempLogOut[]>({ url: '/v1/temp-logs', method: 'GET', params })
  },
  createTempLog(data: TempLogIn) {
    return http.request<TempLogCreateOut>({ url: '/v1/temp-logs', method: 'POST', data })
  },
  batchTempLogs(batchId: number) {
    return http.request<TempLogOut[]>({ url: `/v1/batches/${batchId}/temp-logs`, method: 'GET' })
  },

  // 异常看板
  alerts() {
    return http.request<ComplianceAlertOut>({ url: '/v1/compliance/alerts', method: 'GET' })
  },
}