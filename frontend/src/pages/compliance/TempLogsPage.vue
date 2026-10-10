<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('compliance.tempTitle')" :description="t('compliance.tempDesc')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button type="primary" size="small" @click="openCreate">{{ t('compliance.createTemp') }}</el-button>
    </template>

    <AdminFilterBar show-reset @reset="onReset">
      <el-select v-model="filters.batch_id" size="small" clearable :placeholder="t('compliance.batch')" style="width: 180px">
        <el-option v-for="b in batches" :key="b.id" :label="b.batch_no" :value="b.id" />
      </el-select>
      <el-select v-model="filters.ccp_id" size="small" clearable :placeholder="t('compliance.ccp')" style="width: 200px">
        <el-option v-for="c in ccps" :key="c.id" :label="`${c.name} (${c.code})`" :value="c.id" />
      </el-select>
      <template #extra>
        <el-button size="small" type="primary" @click="load">{{ t('common.search') }}</el-button>
      </template>
    </AdminFilterBar>

    <AdminDataTable :loading="loading" :empty="!loading && !rows.length" :show-pagination="false" class="mt-3">
      <template #table>
        <el-table :data="rows" size="small" border>
          <el-table-column :label="t('compliance.batch')" width="120">
            <template #default="{ row }">{{ row.batch_id ?? '—' }}</template>
          </el-table-column>
          <el-table-column prop="stage" :label="t('compliance.stage')" width="130" />
          <el-table-column prop="station" :label="t('compliance.station')" min-width="130">
            <template #default="{ row }">{{ row.station || '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.recordedAt')" width="170">
            <template #default="{ row }">{{ row.recorded_at }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.tempC')" width="110">
            <template #default="{ row }">{{ row.temp_c }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.durationMin')" width="120">
            <template #default="{ row }">{{ row.duration_min ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.inRange')" width="110" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.in_range ? 'success' : 'danger'">
                {{ row.in_range ? t('compliance.inRange') : t('compliance.outOfRange') }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </AdminDataTable>

    <el-dialog v-model="createVisible" :title="t('compliance.createTemp')" width="620px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item :label="t('compliance.tempC')" prop="temp_c">
          <el-input v-model="form.temp_c" placeholder="86.5" />
        </el-form-item>
        <el-form-item :label="t('compliance.stage')">
          <el-input v-model="form.stage" placeholder="pasteurize" />
        </el-form-item>
        <el-form-item :label="t('compliance.station')">
          <el-input v-model="form.station" />
        </el-form-item>
        <el-form-item :label="t('compliance.batch')">
          <el-select v-model="form.batch_id" clearable class="w-full">
            <el-option v-for="b in batches" :key="b.id" :label="b.batch_no" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('compliance.ccp')">
          <el-select v-model="form.ccp_id" clearable class="w-full">
            <el-option v-for="c in ccps" :key="c.id" :label="`${c.name} (${c.code})`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('compliance.recordedAt')">
          <el-date-picker v-model="form.recorded_at" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" class="w-full" />
        </el-form-item>
        <el-form-item :label="t('compliance.durationMin')">
          <el-input-number v-model="form.duration_min" :min="0" :controls="false" class="w-full" />
        </el-form-item>
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
import { complianceApi, type CcpOut, type TempLogOut } from '@/api/compliance'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const rows = ref<TempLogOut[]>([])
const batches = ref<BatchOut[]>([])
const ccps = ref<CcpOut[]>([])

const filters = reactive({
  batch_id: undefined as number | undefined,
  ccp_id: undefined as number | undefined,
})

async function load() {
  loading.value = true
  try {
    const [logs, batchList, ccpList] = await Promise.all([
      complianceApi.listTempLogs({ batch_id: filters.batch_id, ccp_id: filters.ccp_id }),
      batchApi.list(),
      complianceApi.listCcps(),
    ])
    rows.value = logs
    batches.value = batchList
    ccps.value = ccpList
  } finally {
    loading.value = false
  }
}

function onReset() {
  filters.batch_id = undefined
  filters.ccp_id = undefined
  load()
}

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  temp_c: '',
  stage: 'pasteurize',
  station: '',
  batch_id: undefined as number | undefined,
  ccp_id: undefined as number | undefined,
  recorded_at: null as string | null,
  duration_min: undefined as number | undefined,
  note: '',
})

const rules: FormRules = {
  temp_c: [{ required: true, message: t('common.required'), trigger: 'blur' }],
}

function openCreate() {
  form.temp_c = ''
  form.stage = 'pasteurize'
  form.station = ''
  form.batch_id = undefined
  form.ccp_id = undefined
  form.recorded_at = null
  form.duration_min = undefined
  form.note = ''
  createVisible.value = true
}

async function onCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const res = await complianceApi.createTempLog({
      temp_c: form.temp_c,
      stage: form.stage.trim() || 'pasteurize',
      station: form.station.trim() || null,
      batch_id: form.batch_id ?? null,
      ccp_id: form.ccp_id ?? null,
      recorded_at: form.recorded_at,
      duration_min: form.duration_min ?? null,
      note: form.note.trim() || null,
    })
    if (!res.in_range) {
      ElMessage.warning(t('compliance.alertRaised'))
    } else {
      ElMessage.success(t('common.success'))
    }
    createVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>