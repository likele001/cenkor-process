<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('master.warehousesTitle')" :description="t('master.warehousesDesc')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button type="primary" size="small" @click="openCreate">{{ t('master.createWarehouse') }}</el-button>
    </template>

    <AdminDataTable :loading="loading" :empty="!loading && !rows.length" :show-pagination="false">
      <template #table>
        <el-table :data="rows" size="small" border>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="code" :label="t('master.warehouseCode')" min-width="130" />
          <el-table-column prop="name" :label="t('master.warehouseName')" min-width="140" />
          <el-table-column :label="t('master.isActive')" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.is_active" size="small" type="success">{{ t('common.yes') }}</el-tag>
              <span v-else class="text-el-placeholder">{{ t('common.no') }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </AdminDataTable>

    <el-dialog v-model="dialogVisible" :title="t('master.createWarehouse')" width="420px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="110px">
        <el-form-item :label="t('master.warehouseCode')" prop="code">
          <el-input v-model="form.code" placeholder="WH-RM" />
        </el-form-item>
        <el-form-item :label="t('master.warehouseName')" prop="name">
          <el-input v-model="form.name" placeholder="原料仓" />
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
import { masterApi, type WarehouseOut } from '@/api/master'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const rows = ref<WarehouseOut[]>([])
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({ code: '', name: '' })

const rules: FormRules = {
  code: [{ required: true, message: t('common.required'), trigger: 'blur' }],
  name: [{ required: true, message: t('common.required'), trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    rows.value = await masterApi.listWarehouses()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.code = ''
  form.name = ''
  dialogVisible.value = true
}

async function onSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await masterApi.createWarehouse({ code: form.code.trim(), name: form.name.trim() })
    ElMessage.success(t('common.success'))
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>