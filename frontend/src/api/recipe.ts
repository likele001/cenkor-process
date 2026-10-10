// Copyright (C) 2026 CenkorProcess Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

export type RecipeOut = {
  id: number
  code: string
  name: string
  product_material_id: number
  version: number
  status: string
  base_batch_qty: string
  base_uom_id: number
  yield_pct: string
  note: string | null
  created_at: string
}

export type RecipeComponentOut = {
  id: number
  recipe_id: number
  material_id: number
  seq: number
  ratio_pct: string
  uom_id: number
  tol_pct: string
  is_key: boolean
}

export type RecipeDetailOut = RecipeOut & { components: RecipeComponentOut[] }

export type RecipeComponentIn = {
  material_id: number
  ratio_pct: string | number
  uom_id: number
  seq?: number
  tol_pct?: string | number
  is_key?: boolean
  note?: string | null
}

export type RecipeIn = {
  code: string
  name: string
  product_material_id: number
  version?: number
  base_batch_qty: string | number
  base_uom_id: number
  yield_pct?: string | number
  note?: string | null
  components: RecipeComponentIn[]
}

export type ScaledComponent = {
  component_id: number
  material_id: number
  uom_id: number
  ratio_pct: string
  tol_pct: string
  planned_qty: string
}

export type RecipeScaleOut = {
  recipe_id: number
  target_qty: string
  yield_pct: string
  components: ScaledComponent[]
}

export const recipeApi = {
  list() {
    return http.request<RecipeOut[]>({ url: '/v1/recipes', method: 'GET' })
  },
  create(data: RecipeIn) {
    return http.request<RecipeOut>({ url: '/v1/recipes', method: 'POST', data })
  },
  get(id: number) {
    return http.request<RecipeDetailOut>({ url: `/v1/recipes/${id}`, method: 'GET' })
  },
  release(id: number) {
    return http.request<{ id: number; status: string }>({ url: `/v1/recipes/${id}/release`, method: 'POST' })
  },
  scale(id: number, qty: string | number) {
    return http.request<RecipeScaleOut>({ url: `/v1/recipes/${id}/scale`, method: 'GET', params: { qty } })
  },
}