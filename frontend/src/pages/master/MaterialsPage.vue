<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('master.materialsTitle')" :description="t('master.materialsDesc')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button type="primary" size="small" @click="openCreate">{{ t('master.createMaterial') }}</el-button>
    </template>

    <AdminDataTable :loading="loading" :empty="!loading && !rows.length" :show-pagination="false">
      <template #table>
        <el-table :data="rows" size="small" border>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="code" :label="t('master.materialCode')" min-width="130" />
          <el-table-column prop="name" :label="t('master.materialName')" min-width="140" />
          <el-table-column :label="t('master.baseUom')" width="120">
            <template #default="{ row }">{{ uomLabel(row.base_uom_id) }}</template>
          </el-table-column>
          <el-table-column :label="t('master.density')" width="130">
            <template #default="{ row }">{{ row.density_kg_l ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('master.shelfLifeDays')" width="130">
            <template #default="{ row }">{{ row.shelf_life_days ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('master.isActive')" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.is_active" size="small" type="success">{{ t('common.yes') }}</el-tag>
              <span v-else class="text-el-placeholder">{{ t('common.no') }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </AdminDataTable>

    <el-dialog v-model="dialogVisible" :title="t('master.createMaterial')" width="460px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item :label="t('master.materialCode')" prop="code">
          <el-input v-model="form.code" placeholder="RM-SUGAR" />
        </el-form-item>
        <el-form-item :label="t('master.materialName')" prop="name">
          <el-input v-model="form.name" placeholder="白砂糖" />
        </el-form-item>
        <el-form-item :label="t('master.baseUom')" prop="base_uom_id">
          <el-select v-model="form.base_uom_id" class="w-full" :placeholder="t('common.optional')">
            <el-option v-for="u in uoms" :key="u.id" :label="`${u.name} (${u.code})`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('master.density')">
          <el-input v-model="form.density_kg_l" placeholder="1.00000000" />
        </el-form-item>
        <el-form-item :label="t('master.shelfLifeDays')">
          <el-input-number v-model="form.shelf_life_days" :min="0" :controls="false" class="w-full" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import AdminDataTable from '@/components/admin/AdminDataTable.vue'
import { masterApi, type MaterialOut, type UomOut } from '@/api/master'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const rows = ref<MaterialOut[]>([])
const uoms = ref<UomOut[]>([])
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  code: '',
  name: '',
  base_uom_id: undefined as number | undefined,
  density_kg_l: '',
  shelf_life_days: undefined as number | undefined,
})

const rules: FormRules = {
  code: [{ required: true, message: t('common.required'), trigger: 'blur' }],
  name: [{ required: true, message: t('common.required'), trigger: 'blur' }],
  base_uom_id: [{ required: true, message: t('common.required'), trigger: 'change' }],
}

function uomLabel(id: number) {
  const u = uoms.value.find((x) => x.id === id)
  return u ? `${u.name} (${u.code})` : String(id)
}

async function load() {
  loading.value = true
  try {
    const [materials, uomList] = await Promise.all([masterApi.listMaterials(), masterApi.listUoms()])
    rows.value = materials
    uoms.value = uomList
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.code = ''
  form.name = ''
  form.base_uom_id = uoms.value[0]?.id
  form.density_kg_l = ''
  form.shelf_life_days = undefined
  dialogVisible.value = true
}

async function onSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await masterApi.createMaterial({
      code: form.code.trim(),
      name: form.name.trim(),
      base_uom_id: form.base_uom_id as number,
      density_kg_l: form.density_kg_l.trim() || null,
      shelf_life_days: form.shelf_life_days ?? null,
    })
    ElMessage.success(t('common.success'))
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>