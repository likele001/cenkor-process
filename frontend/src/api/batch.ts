// Copyright (C) 2026 CenkorProcess Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

export type BatchOut = {
  id: number
  batch_no: string
  recipe_id: number
  recipe_version: number
  product_material_id: number
  planned_qty: string
  uom_id: number
  planned_date: string | null
  status: string
  produced_qty: string | null
  scrap_qty: string
  yield_pct: string | null
  created_at: string
  completed_at: string | null
}

export type BatchOperationOut = {
  id: number
  seq: number
  name: string
  op_type: string
  status: string
  temp_c: string | null
  duration_min: number | null
}

export type DispenseRecordOut = {
  id: number
  material_id: number
  lot_id: number | null
  planned_qty: string
  actual_qty: string
  tol_pct: string
  deviated: boolean
}

export type BatchDetailOut = BatchOut & {
  operations: BatchOperationOut[]
  dispenses: DispenseRecordOut[]
}

export type BatchIn = {
  recipe_id: number
  planned_qty: string | number
  uom_id?: number | null
  planned_date?: string | null
  note?: string | null
}

export type DispenseIn = {
  component_id?: number | null
  material_id: number
  planned_qty: string | number
  actual_qty: string | number
  uom_id: number
  tol_pct?: string | number
  lot_id?: number | null
  operator_id?: number | null
}

export type ByproductIn = {
  material_id: number
  qty: string | number
  uom_id: number
  warehouse_id?: number | null
  status?: string
}

export type BatchCompleteIn = {
  dispenses: DispenseIn[]
  produced_qty: string | number
  byproduct?: ByproductIn[]
  warehouse_id?: number | null
  auto_issue?: boolean
  allow_deviation?: boolean
  allow_unplanned?: boolean
}

export type BatchCompleteOut = {
  batch_id: number
  batch_no: string
  status: string
  produced_lot_id: number
  produced_lot_no: string
  consumed: Array<{ lot_id: number; take_qty: string }>
  deviations: Array<{ material_id: number; planned_qty: string; actual_qty: string; tol_pct: string }>
}

export type BatchReleaseOut = {
  id: number
  batch_no: string
  status: string
  recipe_version: number
  has_snapshot: boolean
}

export type DispensePlanLine = {
  component_id: number | null
  material_id: number
  uom_id: number
  ratio_pct: string
  tol_pct: string
  planned_qty: string
  is_key: boolean
}

export type DispensePlanOut = {
  batch_id: number
  batch_no: string
  recipe_id: number | null
  recipe_version: number | null
  planned_qty: string
  yield_pct: string
  lines: DispensePlanLine[]
}

export const batchApi = {
  list() {
    return http.request<BatchOut[]>({ url: '/v1/batches', method: 'GET' })
  },
  create(data: BatchIn) {
    return http.request<BatchOut>({ url: '/v1/batches', method: 'POST', data })
  },
  get(id: number) {
    return http.request<BatchDetailOut>({ url: `/v1/batches/${id}`, method: 'GET' })
  },
  release(id: number) {
    return http.request<BatchReleaseOut>({ url: `/v1/batches/${id}/release`, method: 'POST' })
  },
  dispensePlan(id: number) {
    return http.request<DispensePlanOut>({ url: `/v1/batches/${id}/dispense-plan`, method: 'GET' })
  },
  complete(id: number, data: BatchCompleteIn) {
    return http.request<BatchCompleteOut>({ url: `/v1/batches/${id}/complete`, method: 'POST', data })
  },
}