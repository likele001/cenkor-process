// Copyright (C) 2026 CenkorProcess Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

export type UomOut = {
  id: number
  code: string
  name: string
  is_base: boolean
}

export type UomIn = {
  code: string
  name: string
  is_base?: boolean
}

export type WarehouseOut = {
  id: number
  code: string
  name: string
  is_active: boolean
}

export type WarehouseIn = {
  code: string
  name: string
}

export type MaterialOut = {
  id: number
  code: string
  name: string
  base_uom_id: number
  density_kg_l: string | null
  shelf_life_days: number | null
  is_active: boolean
}

export type MaterialIn = {
  code: string
  name: string
  base_uom_id: number
  density_kg_l?: string | number | null
  shelf_life_days?: number | null
}

export type UomConversionIn = {
  from_uom_id: number
  to_uom_id: number
  material_id?: number | null
  factor?: string | number | null
  density_kg_l?: string | number | null
  note?: string | null
}

export type UomConvertOut = {
  from_uom_id: number
  to_uom_id: number
  material_id: number | null
  qty: string
  result: string
  mode: string
  density_kg_l: string | null
}

export const masterApi = {
  listUoms() {
    return http.request<UomOut[]>({ url: '/v1/uoms', method: 'GET' })
  },
  createUom(data: UomIn) {
    return http.request<UomOut>({ url: '/v1/uoms', method: 'POST', data })
  },

  listMaterials() {
    return http.request<MaterialOut[]>({ url: '/v1/materials', method: 'GET' })
  },
  createMaterial(data: MaterialIn) {
    return http.request<MaterialOut>({ url: '/v1/materials', method: 'POST', data })
  },

  listWarehouses() {
    return http.request<WarehouseOut[]>({ url: '/v1/warehouses', method: 'GET' })
  },
  createWarehouse(data: WarehouseIn) {
    return http.request<WarehouseOut>({ url: '/v1/warehouses', method: 'POST', data })
  },

  createConversion(data: UomConversionIn) {
    return http.request<{ id: number }>({ url: '/v1/uom-conversions', method: 'POST', data })
  },

  convert(params: { qty: string | number; from_uom_id: number; to_uom_id: number; material_id?: number | null }) {
    return http.request<UomConvertOut>({ url: '/v1/uom/convert', method: 'GET', params })
  },
}