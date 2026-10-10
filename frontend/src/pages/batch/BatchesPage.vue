<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('batch.title')" :description="t('batch.desc')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button type="primary" size="small" @click="openCreate">{{ t('batch.createBatch') }}</el-button>
    </template>

    <AdminDataTable :loading="loading" :empty="!loading && !rows.length" :show-pagination="false">
      <template #table>
        <el-table :data="rows" size="small" border>
          <el-table-column prop="batch_no" :label="t('batch.batchNo')" min-width="150" />
          <el-table-column :label="t('batch.recipe')" min-width="170">
            <template #default="{ row }">{{ recipeLabel(row.recipe_id) }}</template>
          </el-table-column>
          <el-table-column :label="t('batch.recipeVersion')" width="100">
            <template #default="{ row }">v{{ row.recipe_version }}</template>
          </el-table-column>
          <el-table-column :label="t('batch.product')" min-width="150">
            <template #default="{ row }">{{ materialLabel(row.product_material_id) }}</template>
          </el-table-column>
          <el-table-column :label="t('batch.plannedQty')" width="130">
            <template #default="{ row }">{{ row.planned_qty }} {{ uomLabel(row.uom_id) }}</template>
          </el-table-column>
          <el-table-column :label="t('batch.plannedDate')" width="120">
            <template #default="{ row }">{{ row.planned_date || '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('batch.producedQty')" width="120">
            <template #default="{ row }">{{ row.produced_qty ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('common.status')" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="tagType(row.status)">{{ label(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('common.actions')" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openDetail(row.id)">{{ t('common.detail') }}</el-button>
              <el-button
                v-if="row.status === 'draft'"
                link
                type="success"
                size="small"
                @click="onRelease(row.id)"
              >
                {{ t('batch.release') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </AdminDataTable>

    <el-dialog v-model="createVisible" :title="t('batch.createBatch')" width="640px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="110px">
        <el-form-item :label="t('batch.recipe')" prop="recipe_id">
          <el-select v-model="form.recipe_id" class="w-full" @change="onRecipeChange">
            <el-option
              v-for="r in releasedRecipes"
              :key="r.id"
              :label="`${r.name} (${r.code}) · v${r.version}`"
              :value="r.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('batch.plannedQty')" prop="planned_qty">
          <el-input v-model="form.planned_qty" placeholder="1000" />
        </el-form-item>
        <el-form-item :label="t('batch.uom')" prop="uom_id">
          <el-select v-model="form.uom_id" class="w-full">
            <el-option v-for="u in uoms" :key="u.id" :label="`${u.name} (${u.code})`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('batch.plannedDate')">
          <el-date-picker v-model="form.planned_date" type="date" value-format="YYYY-MM-DD" class="w-full" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import AdminDataTable from '@/components/admin/AdminDataTable.vue'
import { masterApi, type MaterialOut, type UomOut } from '@/api/master'
import { recipeApi, type RecipeOut } from '@/api/recipe'
import { batchApi, type BatchOut } from '@/api/batch'
import { useStatus } from '@/composables/useStatus'

const { t } = useI18n()
const { label, tagType } = useStatus()
const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const rows = ref<BatchOut[]>([])
const recipes = ref<RecipeOut[]>([])
const uoms = ref<UomOut[]>([])
const materials = ref<MaterialOut[]>([])

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  recipe_id: undefined as number | undefined,
  planned_qty: '',
  uom_id: undefined as number | undefined,
  planned_date: null as string | null,
})

const rules: FormRules = {
  recipe_id: [{ required: true, message: t('common.required'), trigger: 'change' }],
  planned_qty: [{ required: true, message: t('common.required'), trigger: 'blur' }],
  uom_id: [{ required: true, message: t('common.required'), trigger: 'change' }],
}

const releasedRecipes = computed(() => recipes.value.filter((r) => r.status === 'released'))

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

function onRecipeChange(id: number) {
  const r = recipes.value.find((x) => x.id === id)
  if (r) {
    form.uom_id = r.base_uom_id
    form.planned_qty = r.base_batch_qty
  }
}

async function load() {
  loading.value = true
  try {
    const [batchList, recipeList, uomList, materialList] = await Promise.all([
      batchApi.list(),
      recipeApi.list(),
      masterApi.listUoms(),
      masterApi.listMaterials(),
    ])
    rows.value = batchList
    recipes.value = recipeList
    uoms.value = uomList
    materials.value = materialList
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.recipe_id = releasedRecipes.value[0]?.id
  form.planned_qty = ''
  form.uom_id = undefined
  form.planned_date = null
  if (form.recipe_id) onRecipeChange(form.recipe_id)
  createVisible.value = true
}

async function onCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await batchApi.create({
      recipe_id: form.recipe_id as number,
      planned_qty: form.planned_qty,
      uom_id: form.uom_id ?? null,
      planned_date: form.planned_date,
    })
    ElMessage.success(t('common.success'))
    createVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function onRelease(id: number) {
  await batchApi.release(id)
  ElMessage.success(t('batch.releasedOk'))
  await load()
}

function openDetail(id: number) {
  router.push(`/batches/${id}`)
}

onMounted(load)
</script>