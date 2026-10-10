<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('compliance.cipTitle')" :description="t('compliance.cipDesc')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button type="primary" size="small" @click="openCreate">{{ t('compliance.createCip') }}</el-button>
    </template>

    <AdminFilterBar show-reset @reset="onReset">
      <el-input v-model="filters.station" size="small" clearable :placeholder="t('compliance.station')" style="width: 180px" />
      <el-select v-model="filters.result" size="small" clearable :placeholder="t('compliance.result')" style="width: 150px">
        <el-option v-for="s in ['pass', 'fail']" :key="s" :label="label(s)" :value="s" />
      </el-select>
      <template #extra>
        <el-button size="small" type="primary" @click="load">{{ t('common.search') }}</el-button>
      </template>
    </AdminFilterBar>

    <AdminDataTable :loading="loading" :empty="!loading && !rows.length" :show-pagination="false" class="mt-3">
      <template #table>
        <el-table :data="rows" size="small" border>
          <el-table-column prop="station" :label="t('compliance.station')" min-width="130" />
          <el-table-column prop="cip_type" :label="t('compliance.cipType')" width="110" />
          <el-table-column :label="t('compliance.batch')" width="110">
            <template #default="{ row }">{{ row.batch_id ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.startAt')" width="170">
            <template #default="{ row }">{{ row.start_at }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.durationMin')" width="120">
            <template #default="{ row }">{{ row.duration_min ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.causticConc')" width="120">
            <template #default="{ row }">{{ row.caustic_conc_pct ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.finalRinsePh')" width="130">
            <template #default="{ row }">{{ row.final_rinse_ph ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.result')" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="tagType(row.result)">{{ label(row.result) }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </AdminDataTable>

    <el-dialog v-model="createVisible" :title="t('compliance.createCip')" width="760px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="140px">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
          <el-form-item :label="t('compliance.station')" prop="station">
            <el-input v-model="form.station" placeholder="CIP-01" />
          </el-form-item>
          <el-form-item :label="t('compliance.cipType')">
            <el-input v-model="form.cip_type" placeholder="full" />
          </el-form-item>
          <el-form-item :label="t('compliance.batch')">
            <el-select v-model="form.batch_id" clearable class="w-full">
              <el-option v-for="b in batches" :key="b.id" :label="b.batch_no" :value="b.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('compliance.startAt')" prop="start_at">
            <el-date-picker v-model="form.start_at" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" class="w-full" />
          </el-form-item>
          <el-form-item :label="t('compliance.endAt')">
            <el-date-picker v-model="form.end_at" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" class="w-full" />
          </el-form-item>
          <el-form-item :label="t('compliance.durationMin')">
            <el-input-number v-model="form.duration_min" :min="0" :controls="false" class="w-full" />
          </el-form-item>
          <el-form-item :label="t('compliance.causticConc')">
            <el-input v-model="form.caustic_conc_pct" />
          </el-form-item>
          <el-form-item :label="t('compliance.causticTemp')">
            <el-input v-model="form.caustic_temp_c" />
          </el-form-item>
          <el-form-item :label="t('compliance.acidConc')">
            <el-input v-model="form.acid_conc_pct" />
          </el-form-item>
          <el-form-item :label="t('compliance.acidTemp')">
            <el-input v-model="form.acid_temp_c" />
          </el-form-item>
          <el-form-item :label="t('compliance.rinseConductivity')">
            <el-input v-model="form.rinse_conductivity" />
          </el-form-item>
          <el-form-item :label="t('compliance.finalRinsePh')">
            <el-input v-model="form.final_rinse_ph" />
          </el-form-item>
        </div>
        <el-form-item :label="t('common.remark')">
          <el-input v-model="form.note" type="textarea" :rows="2" />
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
import AdminFilterBar from '@/components/admin/AdminFilterBar.vue'
import { batchApi, type BatchOut } from '@/api/batch'
import { complianceApi, type CipLogOut } from '@/api/compliance'
import { useStatus } from '@/composables/useStatus'

const { t } = useI18n()
const { label, tagType } = useStatus()

const loading = ref(false)
const saving = ref(false)
const rows = ref<CipLogOut[]>([])
const batches = ref<BatchOut[]>([])

const filters = reactive({
  station: '',
  result: undefined as string | undefined,
})

async function load() {
  loading.value = true
  try {
    const [logs, batchList] = await Promise.all([
      complianceApi.listCipLogs({
        station: filters.station.trim() || undefined,
        result: filters.result,
      }),
      batchApi.list(),
    ])
    rows.value = logs
    batches.value = batchList
  } finally {
    loading.value = false
  }
}

function onReset() {
  filters.station = ''
  filters.result = undefined
  load()
}

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  station: '',
  cip_type: 'full',
  batch_id: undefined as number | undefined,
  start_at: null as string | null,
  end_at: null as string | null,
  duration_min: undefined as number | undefined,
  caustic_conc_pct: '',
  caustic_temp_c: '',
  acid_conc_pct: '',
  acid_temp_c: '',
  rinse_conductivity: '',
  final_rinse_ph: '',
  note: '',
})

const rules: FormRules = {
  station: [{ required: true, message: t('common.required'), trigger: 'blur' }],
  start_at: [{ required: true, message: t('common.required'), trigger: 'change' }],
}

function openCreate() {
  form.station = ''
  form.cip_type = 'full'
  form.batch_id = undefined
  form.start_at = null
  form.end_at = null
  form.duration_min = undefined
  form.caustic_conc_pct = ''
  form.caustic_temp_c = ''
  form.acid_conc_pct = ''
  form.acid_temp_c = ''
  form.rinse_conductivity = ''
  form.final_rinse_ph = ''
  form.note = ''
  createVisible.value = true
}

async function onCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await complianceApi.createCipLog({
      station: form.station.trim(),
      cip_type: form.cip_type.trim() || 'full',
      batch_id: form.batch_id ?? null,
      start_at: form.start_at as string,
      end_at: form.end_at,
      duration_min: form.duration_min ?? null,
      caustic_conc_pct: form.caustic_conc_pct || null,
      caustic_temp_c: form.caustic_temp_c || null,
      acid_conc_pct: form.acid_conc_pct || null,
      acid_temp_c: form.acid_temp_c || null,
      rinse_conductivity: form.rinse_conductivity || null,
      final_rinse_ph: form.final_rinse_ph || null,
      note: form.note.trim() || null,
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