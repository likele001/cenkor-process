<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('recipe.detailTitle')" :description="recipe ? `${recipe.name} (${recipe.code})` : ''">
    <template #actions>
      <el-button size="small" @click="goBack">{{ t('common.back') }}</el-button>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button v-if="recipe && recipe.status !== 'released'" type="success" size="small" @click="onRelease">
        {{ t('recipe.release') }}
      </el-button>
    </template>

    <div v-loading="loading">
      <el-descriptions v-if="recipe" :column="3" border size="small" class="mb-4">
        <el-descriptions-item :label="t('recipe.code')">{{ recipe.code }}</el-descriptions-item>
        <el-descriptions-item :label="t('recipe.name')">{{ recipe.name }}</el-descriptions-item>
        <el-descriptions-item :label="t('recipe.version')">{{ recipe.version }}</el-descriptions-item>
        <el-descriptions-item :label="t('recipe.product')">{{ materialLabel(recipe.product_material_id) }}</el-descriptions-item>
        <el-descriptions-item :label="t('recipe.baseBatchQty')">
          {{ recipe.base_batch_qty }} {{ uomLabel(recipe.base_uom_id) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('recipe.yieldPct')">{{ recipe.yield_pct }}</el-descriptions-item>
        <el-descriptions-item :label="t('common.status')">
          <el-tag size="small" :type="tagType(recipe.status)">{{ label(recipe.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="t('common.remark')" :span="2">{{ recipe.note || '—' }}</el-descriptions-item>
      </el-descriptions>

      <div class="flex items-center justify-between mb-2">
        <span class="text-[14px] font-semibold text-[var(--el-text-color-primary)]">{{ t('recipe.components') }}</span>
        <div class="flex items-center gap-2">
          <el-input v-model="scaleQty" size="small" style="width: 140px" :placeholder="t('recipe.scaleQty')" />
          <el-button size="small" type="primary" :loading="scaling" @click="onScale">{{ t('recipe.scale') }}</el-button>
        </div>
      </div>

      <el-table :data="components" size="small" border>
        <el-table-column prop="seq" :label="t('recipe.seq')" width="80" />
        <el-table-column :label="t('recipe.material')" min-width="180">
          <template #default="{ row }">{{ materialLabel(row.material_id) }}</template>
        </el-table-column>
        <el-table-column :label="t('recipe.ratioPct')" width="110">
          <template #default="{ row }">{{ row.ratio_pct }}</template>
        </el-table-column>
        <el-table-column :label="t('recipe.uom')" width="90">
          <template #default="{ row }">{{ uomLabel(row.uom_id) }}</template>
        </el-table-column>
        <el-table-column :label="t('recipe.tolPct')" width="100">
          <template #default="{ row }">{{ row.tol_pct }}</template>
        </el-table-column>
        <el-table-column :label="t('recipe.plannedQty')" width="130">
          <template #default="{ row }">{{ scaledMap[row.id] ?? '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('recipe.isKey')" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_key" size="small" type="warning">{{ t('common.yes') }}</el-tag>
            <span v-else class="text-el-placeholder">—</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { masterApi, type MaterialOut, type UomOut } from '@/api/master'
import { recipeApi, type RecipeComponentOut, type RecipeDetailOut } from '@/api/recipe'
import { useStatus } from '@/composables/useStatus'

const { t } = useI18n()
const { label, tagType } = useStatus()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const scaling = ref(false)
const recipe = ref<RecipeDetailOut | null>(null)
const components = ref<RecipeComponentOut[]>([])
const uoms = ref<UomOut[]>([])
const materials = ref<MaterialOut[]>([])
const scaleQty = ref('')
const scaledMap = reactive<Record<number, string>>({})

function materialLabel(id: number) {
  const m = materials.value.find((x) => x.id === id)
  return m ? `${m.name} (${m.code})` : String(id)
}

function uomLabel(id: number) {
  const u = uoms.value.find((x) => x.id === id)
  return u ? u.code : String(id)
}

function goBack() {
  router.push('/recipes')
}

async function load() {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    const [detail, uomList, materialList] = await Promise.all([
      recipeApi.get(id),
      masterApi.listUoms(),
      masterApi.listMaterials(),
    ])
    recipe.value = detail
    components.value = detail.components || []
    uoms.value = uomList
    materials.value = materialList
    scaleQty.value = detail.base_batch_qty
  } finally {
    loading.value = false
  }
}

async function onScale() {
  if (!recipe.value || !scaleQty.value) return
  scaling.value = true
  try {
    const res = await recipeApi.scale(recipe.value.id, scaleQty.value)
    for (const k of Object.keys(scaledMap)) delete scaledMap[Number(k)]
    for (const c of res.components) scaledMap[c.component_id] = c.planned_qty
  } finally {
    scaling.value = false
  }
}

async function onRelease() {
  if (!recipe.value) return
  await recipeApi.release(recipe.value.id)
  ElMessage.success(t('recipe.releasedOk'))
  await load()
}

onMounted(load)
</script>