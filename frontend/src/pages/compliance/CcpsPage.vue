<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('compliance.ccpsTitle')" :description="t('compliance.ccpsDesc')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button type="primary" size="small" @click="openCreate">{{ t('compliance.createCcp') }}</el-button>
    </template>

    <AdminDataTable :loading="loading" :empty="!loading && !rows.length" :show-pagination="false">
      <template #table>
        <el-table :data="rows" size="small" border>
          <el-table-column prop="code" :label="t('compliance.ccpCode')" width="120" />
          <el-table-column prop="name" :label="t('compliance.ccpName')" min-width="160" />
          <el-table-column prop="process_step" :label="t('compliance.processStep')" min-width="130">
            <template #default="{ row }">{{ row.process_step || '—' }}</template>
          </el-table-column>
          <el-table-column prop="param_key" :label="t('compliance.paramKey')" width="120" />
          <el-table-column :label="t('compliance.limitMin')" width="90">
            <template #default="{ row }">{{ row.limit_min ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.limitMax')" width="90">
            <template #default="{ row }">{{ row.limit_max ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.targetValue')" width="100">
            <template #default="{ row }">{{ row.target_value ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.critical')" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.critical" size="small" type="danger">{{ t('common.yes') }}</el-tag>
              <span v-else class="text-el-placeholder">—</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('compliance.isActive')" width="90" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? t('common.yes') : t('common.no') }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </AdminDataTable>

    <el-dialog v-model="createVisible" :title="t('compliance.createCcp')" width="720px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
          <el-form-item :label="t('compliance.ccpCode')" prop="code">
            <el-input v-model="form.code" placeholder="CCP-01" />
          </el-form-item>
          <el-form-item :label="t('compliance.ccpName')" prop="name">
            <el-input v-model="form.name" placeholder="杀菌温度" />
          </el-form-item>
          <el-form-item :label="t('compliance.processStep')">
            <el-input v-model="form.process_step" placeholder="杀菌" />
          </el-form-item>
          <el-form-item :label="t('compliance.paramKey')">
            <el-input v-model="form.param_key" placeholder="temp_c" />
          </el-form-item>
          <el-form-item :label="t('compliance.limitMin')">
            <el-input v-model="form.limit_min" placeholder="80" />
          </el-form-item>
          <el-form-item :label="t('compliance.limitMax')">
            <el-input v-model="form.limit_max" placeholder="95" />
          </el-form-item>
          <el-form-item :label="t('compliance.targetValue')">
            <el-input v-model="form.target_value" placeholder="85" />
          </el-form-item>
          <el-form-item :label="t('compliance.monitorFreq')">
            <el-input v-model="form.monitor_freq" placeholder="每批" />
          </el-form-item>
        </div>
        <el-form-item :label="t('compliance.correctiveAction')">
          <el-input v-model="form.corrective_action" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="form.critical">{{ t('compliance.critical') }}</el-checkbox>
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
import { onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import AdminDataTable from '@/components/admin/AdminDataTable.vue'
import { complianceApi, type CcpOut } from '@/api/compliance'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const rows = ref<CcpOut[]>([])

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  code: '',
  name: '',
  process_step: '',
  param_key: 'temp_c',
  limit_min: '',
  limit_max: '',
  target_value: '',
  monitor_freq: '',
  corrective_action: '',
  critical: true,
})

const rules: FormRules = {
  code: [{ required: true, message: t('common.required'), trigger: 'blur' }],
  name: [{ required: true, message: t('common.required'), trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    rows.value = await complianceApi.listCcps()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.code = ''
  form.name = ''
  form.process_step = ''
  form.param_key = 'temp_c'
  form.limit_min = ''
  form.limit_max = ''
  form.target_value = ''
  form.monitor_freq = ''
  form.corrective_action = ''
  form.critical = true
  createVisible.value = true
}

async function onCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await complianceApi.createCcp({
      code: form.code.trim(),
      name: form.name.trim(),
      process_step: form.process_step.trim() || null,
      param_key: form.param_key.trim() || 'temp_c',
      limit_min: form.limit_min || null,
      limit_max: form.limit_max || null,
      target_value: form.target_value || null,
      critical: form.critical,
      monitor_freq: form.monitor_freq.trim() || null,
      corrective_action: form.corrective_action.trim() || null,
    })
    ElMessage.success(t('common.success'))
    createVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>