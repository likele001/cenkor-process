<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('recipe.title')" :description="t('recipe.desc')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button type="primary" size="small" @click="openCreate">{{ t('recipe.createRecipe') }}</el-button>
    </template>

    <AdminDataTable :loading="loading" :empty="!loading && !rows.length" :show-pagination="false">
      <template #table>
        <el-table :data="rows" size="small" border>
          <el-table-column prop="code" :label="t('recipe.code')" min-width="140" />
          <el-table-column prop="name" :label="t('recipe.name')" min-width="180" />
          <el-table-column :label="t('recipe.product')" width="130">
            <template #default="{ row }">{{ materialLabel(row.product_material_id) }}</template>
          </el-table-column>
          <el-table-column prop="version" :label="t('recipe.version')" width="80" />
          <el-table-column :label="t('recipe.baseBatchQty')" width="130">
            <template #default="{ row }">{{ row.base_batch_qty }} {{ uomLabel(row.base_uom_id) }}</template>
          </el-table-column>
          <el-table-column :label="t('recipe.yieldPct')" width="100">
            <template #default="{ row }">{{ row.yield_pct }}</template>
          </el-table-column>
          <el-table-column :label="t('common.status')" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="tagType(row.status)">{{ label(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('common.actions')" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openDetail(row.id)">{{ t('common.detail') }}</el-button>
              <el-button
                v-if="row.status !== 'released'"
                link
                type="success"
                size="small"
                @click="onRelease(row.id)"
              >
                {{ t('recipe.release') }}
              </el-button>
              <el-button link type="warning" size="small" @click="openScale(row)">{{ t('recipe.scale') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </AdminDataTable>

    <!-- 新建配方 -->
    <el-dialog v-model="createVisible" :title="t('recipe.createRecipe')" width="820px" top="6vh">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="110px">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
          <el-form-item :label="t('recipe.code')" prop="code">
            <el-input v-model="form.code" placeholder="RCP-001" />
          </el-form-item>
          <el-form-item :label="t('recipe.name')" prop="name">
            <el-input v-model="form.name" placeholder="含糖饮料配方" />
          </el-form-item>
          <el-form-item :label="t('recipe.product')" prop="product_material_id">
            <el-select v-model="form.product_material_id" class="w-full">
              <el-option v-for="m in materials" :key="m.id" :label="`${m.name} (${m.code})`" :value="m.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('recipe.version')">
            <el-input-number v-model="form.version" :min="1" :controls="false" class="w-full" />
          </el-form-item>
          <el-form-item :label="t('recipe.baseBatchQty')" prop="base_batch_qty">
            <el-input v-model="form.base_batch_qty" placeholder="1000" />
          </el-form-item>
          <el-form-item :label="t('recipe.baseUom')" prop="base_uom_id">
            <el-select v-model="form.base_uom_id" class="w-full">
              <el-option v-for="u in uoms" :key="u.id" :label="`${u.name} (${u.code})`" :value="u.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('recipe.yieldPct')">
            <el-input v-model="form.yield_pct" placeholder="98" />
          </el-form-item>
          <el-form-item :label="t('recipe.note')">
            <el-input v-model="form.note" />
          </el-form-item>
        </div>

        <div class="flex items-center justify-between mb-2">
          <span class="text-[13px] font-semibold text-[var(--el-text-color-primary)]">{{ t('recipe.components') }}</span>
          <el-button size="small" @click="addComponent">{{ t('recipe.addComponent') }}</el-button>
        </div>
        <el-table :data="form.components" size="small" border>
          <el-table-column :label="t('recipe.material')" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.material_id" class="w-full" size="small">
                <el-option v-for="m in materials" :key="m.id" :label="`${m.name} (${m.code})`" :value="m.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column :label="t('recipe.ratioPct')" width="120">
            <template #default="{ row }">
              <el-input v-model="row.ratio_pct" size="small" placeholder="8" />
            </template>
          </el-table-column>
          <el-table-column :label="t('recipe.uom')" width="150">
            <template #default="{ row }">
              <el-select v-model="row.uom_id" class="w-full" size="small">
                <el-option v-for="u in uoms" :key="u.id" :label="u.code" :value="u.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column :label="t('recipe.tolPct')" width="110">
            <template #default="{ row }">
              <el-input v-model="row.tol_pct" size="small" placeholder="0" />
            </template>
          </el-table-column>
          <el-table-column :label="t('recipe.isKey')" width="90" align="center">
            <template #default="{ row }">
              <el-checkbox v-model="row.is_key" />
            </template>
          </el-table-column>
          <el-table-column :label="t('common.actions')" width="80" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="form.components.splice($index, 1)">
                {{ t('common.delete') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 缩放 -->
    <el-dialog v-model="scaleVisible" :title="t('recipe.scale')" width="640px">
      <el-form label-width="110px">
        <el-form-item :label="t('recipe.scaleQty')">
          <el-input v-model="scaleQty" placeholder="2000" />
        </el-form-item>
      </el-form>
      <el-button type="primary" size="small" :loading="scaling" @click="onScale">{{ t('recipe.scale') }}</el-button>
      <el-table v-if="scaleResult" :data="scaleResult.components" size="small" border class="mt-3">
        <el-table-column :label="t('recipe.material')" min-width="150">
          <template #default="{ row }">{{ materialLabel(row.material_id) }}</template>
        </el-table-column>
        <el-table-column :label="t('recipe.ratioPct')" width="100">
          <template #default="{ row }">{{ row.ratio_pct }}</template>
        </el-table-column>
        <el-table-column :label="t('recipe.plannedQty')" width="130">
          <template #default="{ row }">{{ row.planned_qty }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import AdminDataTable from '@/components/admin/AdminDataTable.vue'
import { masterApi, type MaterialOut, type UomOut } from '@/api/master'
import { recipeApi, type RecipeOut, type RecipeScaleOut } from '@/api/recipe'
import { useStatus } from '@/composables/useStatus'

const { t } = useI18n()
const { label, tagType } = useStatus()
const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const rows = ref<RecipeOut[]>([])
const uoms = ref<UomOut[]>([])
const materials = ref<MaterialOut[]>([])

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  code: '',
  name: '',
  product_material_id: undefined as number | undefined,
  version: 1,
  base_batch_qty: '',
  base_uom_id: undefined as number | undefined,
  yield_pct: '100',
  note: '',
  components: [] as Array<{
    material_id: number | undefined
    ratio_pct: string
    uom_id: number | undefined
    seq: number
    tol_pct: string
    is_key: boolean
  }>,
})

const rules: FormRules = {
  code: [{ required: true, message: t('common.required'), trigger: 'blur' }],
  name: [{ required: true, message: t('common.required'), trigger: 'blur' }],
  product_material_id: [{ required: true, message: t('common.required'), trigger: 'change' }],
  base_batch_qty: [{ required: true, message: t('common.required'), trigger: 'blur' }],
  base_uom_id: [{ required: true, message: t('common.required'), trigger: 'change' }],
}

const scaleVisible = ref(false)
const scaling = ref(false)
const scaleQty = ref('')
const scaleResult = ref<RecipeScaleOut | null>(null)
const scaleRecipeId = ref<number | null>(null)

function materialLabel(id: number) {
  const m = materials.value.find((x) => x.id === id)
  return m ? `${m.name} (${m.code})` : String(id)
}

function uomLabel(id: number) {
  const u = uoms.value.find((x) => x.id === id)
  return u ? u.code : String(id)
}

async function load() {
  loading.value = true
  try {
    const [recipes, uomList, materialList] = await Promise.all([
      recipeApi.list(),
      masterApi.listUoms(),
      masterApi.listMaterials(),
    ])
    rows.value = recipes
    uoms.value = uomList
    materials.value = materialList
  } finally {
    loading.value = false
  }
}

function addComponent() {
  form.components.push({
    material_id: materials.value[0]?.id,
    ratio_pct: '',
    uom_id: uoms.value[0]?.id,
    seq: form.components.length + 1,
    tol_pct: '0',
    is_key: false,
  })
}

function openCreate() {
  form.code = ''
  form.name = ''
  form.product_material_id = materials.value[0]?.id
  form.version = 1
  form.base_batch_qty = ''
  form.base_uom_id = uoms.value[0]?.id
  form.yield_pct = '100'
  form.note = ''
  form.components = []
  addComponent()
  createVisible.value = true
}

async function onCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!form.components.length) {
    ElMessage.warning(t('recipe.componentRequired'))
    return
  }
  saving.value = true
  try {
    await recipeApi.create({
      code: form.code.trim(),
      name: form.name.trim(),
      product_material_id: form.product_material_id as number,
      version: form.version,
      base_batch_qty: form.base_batch_qty,
      base_uom_id: form.base_uom_id as number,
      yield_pct: form.yield_pct || '100',
      note: form.note.trim() || null,
      components: form.components.map((c, i) => ({
        material_id: c.material_id as number,
        ratio_pct: c.ratio_pct,
        uom_id: c.uom_id as number,
        seq: i + 1,
        tol_pct: c.tol_pct || '0',
        is_key: c.is_key,
      })),
    })
    ElMessage.success(t('common.success'))
    createVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function onRelease(id: number) {
  await ElMessageBox.confirm(t('batch.releaseHint'), t('recipe.release'), { type: 'warning' }).catch(() => 'cancel')
  await recipeApi.release(id)
  ElMessage.success(t('recipe.releasedOk'))
  await load()
}

function openDetail(id: number) {
  router.push(`/recipes/${id}`)
}

function openScale(row: RecipeOut) {
  scaleRecipeId.value = row.id
  scaleQty.value = row.base_batch_qty
  scaleResult.value = null
  scaleVisible.value = true
}

async function onScale() {
  if (!scaleRecipeId.value || !scaleQty.value) return
  scaling.value = true
  try {
    scaleResult.value = await recipeApi.scale(scaleRecipeId.value, scaleQty.value)
  } finally {
    scaling.value = false
  }
}

onMounted(load)
</script>