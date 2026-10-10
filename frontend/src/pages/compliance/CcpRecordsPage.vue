<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('compliance.ccpRecordsTitle')" :description="t('compliance.ccpRecordsDesc')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button type="primary" size="small" @click="openCreate">{{ t('compliance.createCcpRecord') }}</el-button>
    </template>

    <AdminFilterBar show-reset @reset="onReset">
      <el-select v-model="filters.ccp_id" size="small" clearable :placeholder="t('compliance.ccp')" style="width: 200px">
        <el-option v-for="c in ccps" :key="c.id" :label="`${c.name} (${c.code})`" :value="c.id" />
      </el-select>
      <el-select v-model="filters.status" size="small" clearable :placeholder="t('compliance.result')" style="width: 150px">
        <el-option v-for="s in ['pass', 'deviation']" :key="s" :label="label(s)" :value="s" />
      </el-select>
      <template #extra>
        <el-button size="small" type="primary" @click="load">{{ t('common.search') }}</el-button>
      </template>
    </AdminFilterBar>

    <AdminDataTable :loading="loading" :empty="!loading && !rows.length" :show-pagination="false" class="mt-3">
      <template #table>
        <el-table :data="rows" size="small" border>
          <el-table-column :label="t('compliance.ccp')" min-width="170">
            <template #default="{ row }">{{ ccpLabel(row.ccp_id) }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.batch')" width="110">
            <template #default="{ row }">{{ row.batch_id ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.measuredValue')" width="130">
            <template #default="{ row }">{{ row.measured_value }} {{ row.uom_id ? uomLabel(row.uom_id) : '' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.measuredAt')" width="170">
            <template #default="{ row }">{{ row.measured_at }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.result')" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="tagType(row.status)">{{ label(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('compliance.deviationNote')" min-width="160">
            <template #default="{ row }">{{ row.deviation_note || '—' }}</template>
          </el-table-column>
        </el-table>
      </template>
    </AdminDataTable>

    <el-dialog v-model="createVisible" :title="t('compliance.createCcpRecord')" width="620px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item :label="t('compliance.ccp')" prop="ccp_id">
          <el-select v-model="form.ccp_id" class="w-full">
            <el-option v-for="c in ccps" :key="c.id" :label="`${c.name} (${c.code})`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('compliance.batch')">
          <el-select v-model="form.batch_id" clearable class="w-full">
            <el-option v-for="b in batches" :key="b.id" :label="b.batch_no" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('compliance.measuredValue')" prop="measured_value">
          <el-input v-model="form.measured_value" placeholder="86.5" />
        </el-form-item>
        <el-form-item :label="t('compliance.measuredAt')">
          <el-date-picker
            v-model="form.measured_at"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            class="w-full"
          />
        </el-form-item>
        <el-form-item :label="t('compliance.deviationNote')">
          <el-input v-model="form.deviation_note" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item :label="t('compliance.correctiveAction')">
          <el-input v-model="form.corrective_action" type="textarea" :rows="2" />
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
import { masterApi, type UomOut } from '@/api/master'
import { batchApi, type BatchOut } from '@/api/batch'
import { complianceApi, type CcpOut, type CcpRecordOut } from '@/api/compliance'
import { useStatus } from '@/composables/useStatus'

const { t } = useI18n()
const { label, tagType } = useStatus()

const loading = ref(false)
const saving = ref(false)
const rows = ref<CcpRecordOut[]>([])
const ccps = ref<CcpOut[]>([])
const batches = ref<BatchOut[]>([])
const uoms = ref<UomOut[]>([])

const filters = reactive({
  ccp_id: undefined as number | undefined,
  status: undefined as string | undefined,
})

function ccpLabel(id: number) {
  const c = ccps.value.find((x) => x.id === id)
  return c ? `${c.name} (${c.code})` : String(id)
}
function uomLabel(id: number) {
  const u = uoms.value.find((x) => x.id === id)
  return u ? u.code : String(id)
}

async function load() {
  loading.value = true
  try {
    const [records, ccpList, batchList, uomList] = await Promise.all([
      complianceApi.listCcpRecords({ ccp_id: filters.ccp_id, status: filters.status }),
      complianceApi.listCcps(),
      batchApi.list(),
      masterApi.listUoms(),
    ])
    rows.value = records
    ccps.value = ccpList
    batches.value = batchList
    uoms.value = uomList
  } finally {
    loading.value = false
  }
}

function onReset() {
  filters.ccp_id = undefined
  filters.status = undefined
  load()
}

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  ccp_id: undefined as number | undefined,
  batch_id: undefined as number | undefined,
  measured_value: '',
  measured_at: null as string | null,
  deviation_note: '',
  corrective_action: '',
})

const rules: FormRules = {
  ccp_id: [{ required: true, message: t('common.required'), trigger: 'change' }],
  measured_value: [{ required: true, message: t('common.required'), trigger: 'blur' }],
}

function openCreate() {
  form.ccp_id = ccps.value[0]?.id
  form.batch_id = undefined
  form.measured_value = ''
  form.measured_at = null
  form.deviation_note = ''
  form.corrective_action = ''
  createVisible.value = true
}

async function onCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await complianceApi.createCcpRecord({
      ccp_id: form.ccp_id as number,
      batch_id: form.batch_id ?? null,
      measured_value: form.measured_value,
      measured_at: form.measured_at,
      deviation_note: form.deviation_note.trim() || null,
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