// Copyright (C) 2026 CenkorProcess Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

export type StockLotOut = {
  id: number
  warehouse_id: number
  material_id: number
  lot_no: string
  qty: string
  uom_id: number
  produced_at: string | null
  expiry_at: string | null
  status: string
  source_batch_id: number | null
}

export type LotReceiptIn = {
  warehouse_id: number
  material_id: number
  lot_no: string
  qty: string | number
  uom_id: number
  produced_at?: string | null
  expiry_at?: string | null
  status?: string
  supplier_lot_no?: string | null
}

export type FefoPlanItem = {
  lot_id: number
  lot_no: string
  expiry_at: string | null
  take_qty: string
}

export type FefoPlanOut = {
  warehouse_id: number
  material_id: number
  need_qty: string
  enough: boolean
  plan: FefoPlanItem[]
}

export type GenealogyNode = {
  lot_id: number
  op_type: string
  amount: string
}

export type GenealogyOut = {
  lot_id: number
  parents: GenealogyNode[]
  children: GenealogyNode[]
}

export type LotMergeIn = {
  lot_ids: number[]
  lot_no?: string | null
  status?: string
}

export type LotMergeOut = {
  child_lot_id: number
  child_lot_no: string
  merged_qty: string
  expiry_at: string | null
  parents: Array<{ lot_id: number; lot_no: string; amount: string }>
}

export type LotSplitPart = {
  qty: string | number
  lot_no?: string | null
  expiry_at?: string | null
}

export type LotSplitIn = {
  parts: LotSplitPart[]
  status?: string | null
}

export type LotSplitOut = {
  parent_lot_id: number
  parent_lot_no: string
  parent_remaining: string
  children: Array<{ lot_id: number; lot_no: string; qty: string }>
}

export const stockApi = {
  listLots(params?: { warehouse_id?: number; material_id?: number; status?: string }) {
    return http.request<StockLotOut[]>({ url: '/v1/stock/lots', method: 'GET', params })
  },
  receiveLot(data: LotReceiptIn) {
    return http.request<StockLotOut>({ url: '/v1/stock/lots', method: 'POST', data })
  },
  fefoPreview(params: { warehouse_id: number; material_id: number; qty: string | number }) {
    return http.request<FefoPlanOut>({ url: '/v1/stock/fefo-preview', method: 'GET', params })
  },
  genealogy(lotId: number) {
    return http.request<GenealogyOut>({ url: `/v1/stock/genealogy/${lotId}`, method: 'GET' })
  },
  mergeLots(data: LotMergeIn) {
    return http.request<LotMergeOut>({ url: '/v1/stock/lots/merge', method: 'POST', data })
  },
  splitLot(lotId: number, data: LotSplitIn) {
    return http.request<LotSplitOut>({ url: `/v1/stock/lots/${lotId}/split`, method: 'POST', data })
  },
}