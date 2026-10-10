<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('batch.detailTitle')" :description="batch ? `${batch.batch_no}` : ''">
    <template #actions>
      <el-button size="small" @click="goBack">{{ t('common.back') }}</el-button>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button v-if="batch && batch.status === 'draft'" type="success" size="small" @click="onRelease">
        {{ t('batch.release') }}
      </el-button>
      <el-button
        v-if="batch && batch.status === 'released'"
        type="primary"
        size="small"
        @click="openComplete"
      >
        {{ t('batch.complete') }}
      </el-button>
    </template>

    <div v-loading="loading">
      <el-descriptions v-if="batch" :column="3" border size="small" class="mb-4">
        <el-descriptions-item :label="t('batch.batchNo')">{{ batch.batch_no }}</el-descriptions-item>
        <el-descriptions-item :label="t('batch.recipe')">{{ recipeLabel(batch.recipe_id) }}</el-descriptions-item>
        <el-descriptions-item :label="t('batch.recipeVersion')">v{{ batch.recipe_version }}</el-descriptions-item>
        <el-descriptions-item :label="t('batch.product')">{{ materialLabel(batch.product_material_id) }}</el-descriptions-item>
        <el-descriptions-item :label="t('batch.plannedQty')">
          {{ batch.planned_qty }} {{ uomLabel(batch.uom_id) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('batch.plannedDate')">{{ batch.planned_date || '—' }}</el-descriptions-item>
        <el-descriptions-item :label="t('batch.producedQty')">{{ batch.produced_qty ?? '—' }}</el-descriptions-item>
        <el-descriptions-item :label="t('batch.scrapQty')">{{ batch.scrap_qty }}</el-descriptions-item>
        <el-descriptions-item :label="t('common.status')">
          <el-tag size="small" :type="tagType(batch.status)">{{ label(batch.status) }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('batch.operations')" name="operations">
          <el-table :data="operations" size="small" border>
            <el-table-column prop="seq" :label="t('recipe.seq')" width="80" />
            <el-table-column prop="name" :label="t('common.name')" min-width="160" />
            <el-table-column prop="op_type" :label="t('batch.operations')" width="130" />
            <el-table-column :label="t('common.status')" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="tagType(row.status)">{{ label(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('compliance.tempC')" width="110">
              <template #default="{ row }">{{ row.temp_c ?? '—' }}</template>
            </el-table-column>
            <el-table-column :label="t('compliance.durationMin')" width="120">
              <template #default="{ row }">{{ row.duration_min ?? '—' }}</template>
            </el-table-column>
          </el-table>
          <AdminEmpty v-if="!loading && !operations.length" :description="t('batch.noOperations')" />
        </el-tab-pane>

        <el-tab-pane :label="t('batch.dispenses')" name="dispenses">
          <el-table :data="dispenses" size="small" border>
            <el-table-column :label="t('batch.lot')" min-width="150">
              <template #default="{ row }">{{ row.lot_id ?? '—' }}</template>
            </el-table-column>
            <el-table-column :label="t('recipe.material')" min-width="150">
              <template #default="{ row }">{{ materialLabel(row.material_id) }}</template>
            </el-table-column>
            <el-table-column :label="t('batch.plannedQty')" width="120">
              <template #default="{ row }">{{ row.planned_qty }}</template>
            </el-table-column>
            <el-table-column :label="t('batch.actualQty')" width="120">
              <template #default="{ row }">{{ row.actual_qty }}</template>
            </el-table-column>
            <el-table-column :label="t('recipe.tolPct')" width="100">
              <template #default="{ row }">{{ row.tol_pct }}</template>
            </el-table-column>
            <el-table-column :label="t('common.status')" width="110">
              <template #default="{ row }">
                <el-tag v-if="row.deviated" size="small" type="warning">{{ t('batch.deviated') }}</el-tag>
                <span v-else class="text-el-placeholder">—</span>
              </template>
            </el-table-column>
          </el-table>
          <AdminEmpty v-if="!loading && !dispenses.length" :description="t('batch.noDispenses')" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 产出入库 -->
    <el-dialog v-model="completeVisible" :title="t('batch.completeTitle')" width="900px" top="5vh">
      <div class="flex items-center justify-between mb-2">
        <span class="text-[13px] font-semibold text-[var(--el-text-color-primary)]">
          {{ t('batch.dispensePlanTitle') }}
        </span>
        <el-button size="small" :loading="planLoading" @click="loadPlan">{{ t('common.refresh') }}</el-button>
      </div>

      <el-table :data="planLines" size="small" border>
        <el-table-column :label="t('recipe.material')" min-width="170">
          <template #default="{ row }">{{ materialLabel(row.material_id) }}</template>
        </el-table-column>
        <el-table-column :label="t('batch.plannedQty')" width="110">
          <template #default="{ row }">{{ row.planned_qty }}</template>
        </el-table-column>
        <el-table-column :label="t('batch.actualQty')" width="150">
          <template #default="{ row }">
            <el-input v-model="actualMap[row.component_id ?? row.material_id]" size="small" />
          </template>
        </el-table-column>
        <el-table-column :label="t('batch.lot')" width="150">
          <template #default="{ row }">
            <el-input v-model="lotMap[row.component_id ?? row.material_id]" size="small" placeholder="—" />
          </template>
        </el-table-column>
        <el-table-column :label="t('recipe.isKey')" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_key" size="small" type="warning">{{ t('common.yes') }}</el-tag>
            <span v-else class="text-el-placeholder">—</span>
          </template>
        </el-table-column>
      </el-table>
      <AdminEmpty v-if="!planLoading && !planLines.length" :description="t('batch.planEmpty')" />

      <el-form label-width="130px" class="mt-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
          <el-form-item :label="t('batch.producedQty')">
            <el-input v-model="completeForm.produced_qty" placeholder="1000" />
          </el-form-item>
          <el-form-item :label="t('batch.warehouse')">
            <el-select v-model="completeForm.warehouse_id" class="w-full">
              <el-option v-for="w in warehouses" :key="w.id" :label="`${w.name} (${w.code})`" :value="w.id" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item>
          <el-checkbox v-model="completeForm.auto_issue">{{ t('batch.autoIssue') }}</el-checkbox>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="completeForm.allow_deviation">{{ t('batch.allowDeviation') }}</el-checkbox>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="completeForm.allow_unplanned">{{ t('batch.allowUnplanned') }}</el-checkbox>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="completeVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="completing" @click="onComplete">{{ t('batch.complete') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import AdminEmpty from '@/components/admin/AdminEmpty.vue'
import { masterApi, type MaterialOut, type UomOut, type WarehouseOut } from '@/api/master'
import { recipeApi, type RecipeOut } from '@/api/recipe'
import {
  batchApi,
  type BatchDetailOut,
  type DispensePlanLine,
  type BatchCompleteIn,
} from '@/api/batch'
import { useStatus } from '@/composables/useStatus'

const { t } = useI18n()
const { label, tagType } = useStatus()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const batch = ref<BatchDetailOut | null>(null)
const operations = ref<BatchDetailOut['operations']>([])
const dispenses = ref<BatchDetailOut['dispenses']>([])
const recipes = ref<RecipeOut[]>([])
const uoms = ref<UomOut[]>([])
const materials = ref<MaterialOut[]>([])
const warehouses = ref<WarehouseOut[]>([])
const activeTab = ref('operations')

const completeVisible = ref(false)
const planLoading = ref(false)
const completing = ref(false)
const planLines = ref<DispensePlanLine[]>([])
const actualMap = reactive<Record<string, string>>({})
const lotMap = reactive<Record<string, string>>({})
const completeForm = reactive({
  produced_qty: '',
  warehouse_id: undefined as number | undefined,
  auto_issue: true,
  allow_deviation: false,
  allow_unplanned: false,
})

function recipeLabel(id: number) {
  const r = recipes.value.find((x) => x.id === id)
  return r ? `${r.name} (${r.code})` : String(id)
}

function materialLabel(id: number) {
  const m = materials.value.find((x) => x.id === id)
  return m ? `${m.name} (${m.code})` : String(id)
}

function uomLabel(id: number) {
  const u = uoms.value.find((x) => x.id === id)
  return u ? u.code : String(id)
}

function goBack() {
  router.push('/batches')
}

async function load() {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    const [detail, recipeList, uomList, materialList, warehouseList] = await Promise.all([
      batchApi.get(id),
      recipeApi.list(),
      masterApi.listUoms(),
      masterApi.listMaterials(),
      masterApi.listWarehouses(),
    ])
    batch.value = detail
    operations.value = detail.operations || []
    dispenses.value = detail.dispenses || []
    recipes.value = recipeList
    uoms.value = uomList
    materials.value = materialList
    warehouses.value = warehouseList
  } finally {
    loading.value = false
  }
}

async function onRelease() {
  if (!batch.value) return
  await batchApi.release(batch.value.id)
  ElMessage.success(t('batch.releasedOk'))
  await load()
}

async function loadPlan() {
  if (!batch.value) return
  planLoading.value = true
  try {
    const plan = await batchApi.dispensePlan(batch.value.id)
    planLines.value = plan.lines || []
    for (const line of planLines.value) {
      const key = String(line.component_id ?? line.material_id)
      actualMap[key] = line.planned_qty
      lotMap[key] = ''
    }
    if (!completeForm.produced_qty) completeForm.produced_qty = plan.planned_qty
  } finally {
    planLoading.value = false
  }
}

function openComplete() {
  completeForm.produced_qty = batch.value?.planned_qty ?? ''
  completeForm.warehouse_id = warehouses.value[0]?.id
  completeForm.auto_issue = true
  completeForm.allow_deviation = false
  completeForm.allow_unplanned = false
  completeVisible.value = true
  loadPlan()
}

async function onComplete() {
  if (!batch.value) return
  completing.value = true
  try {
    const payload: BatchCompleteIn = {
      produced_qty: completeForm.produced_qty,
      warehouse_id: completeForm.warehouse_id ?? null,
      auto_issue: completeForm.auto_issue,
      allow_deviation: completeForm.allow_deviation,
      allow_unplanned: completeForm.allow_unplanned,
      dispenses: planLines.value.map((line) => {
        const key = String(line.component_id ?? line.material_id)
        const lotRaw = lotMap[key]
        return {
          component_id: line.component_id,
          material_id: line.material_id,
          planned_qty: line.planned_qty,
          actual_qty: actualMap[key] || line.planned_qty,
          uom_id: line.uom_id,
          tol_pct: line.tol_pct,
          lot_id: lotRaw ? Number(lotRaw) : null,
        }
      }),
    }
    const res = await batchApi.complete(batch.value.id, payload)
    ElMessage.success(`${t('batch.completeOk')} · ${t('batch.producedLot')}: ${res.produced_lot_no}`)
    completeVisible.value = false
    await load()
  } finally {
    completing.value = false
  }
}

onMounted(load)
</script>