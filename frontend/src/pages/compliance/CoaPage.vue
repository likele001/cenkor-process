<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('compliance.coaTitle')" :description="t('compliance.coaDesc')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button type="primary" size="small" @click="openCreate">{{ t('compliance.createCoa') }}</el-button>
    </template>

    <AdminFilterBar show-reset @reset="onReset">
      <el-select v-model="filters.material_id" size="small" clearable :placeholder="t('stock.material')" style="width: 200px">
        <el-option v-for="m in materials" :key="m.id" :label="`${m.name} (${m.code})`" :value="m.id" />
      </el-select>
      <el-select v-model="filters.result" size="small" clearable :placeholder="t('compliance.result')" style="width: 150px">
        <el-option v-for="s in ['pending', 'pass', 'fail', 'hold']" :key="s" :label="label(s)" :value="s" />
      </el-select>
      <template #extra>
        <el-button size="small" type="primary" @click="load">{{ t('common.search') }}</el-button>
      </template>
    </AdminFilterBar>

    <AdminDataTable :loading="loading" :empty="!loading && !rows.length" :show-pagination="false" class="mt-3">
      <template #table>
        <el-table :data="rows" size="small" border>
          <el-table-column prop="coa_no" :label="t('compliance.coaNo')" min-width="150" />
          <el-table-column :label="t('stock.material')" min-width="160">
            <template #default="{ row }">{{ materialLabel(row.material_id) }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.direction')" width="100">
            <template #default="{ row }">
              {{ row.direction === 'incoming' ? t('compliance.directionIncoming') : t('compliance.directionOutgoing') }}
            </template>
          </el-table-column>
          <el-table-column :label="t('stock.lotNo')" width="110">
            <template #default="{ row }">{{ row.lot_id ?? '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.testedAt')" width="170">
            <template #default="{ row }">{{ row.tested_at || '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('compliance.result')" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="tagType(row.result)">{{ label(row.result) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('compliance.locked')" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.locked" size="small" type="danger">{{ t('common.yes') }}</el-tag>
              <span v-else class="text-el-placeholder">—</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('common.actions')" width="120" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                size="small"
                :disabled="row.locked"
                @click="openDecide(row)"
              >
                {{ t('compliance.decide') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </AdminDataTable>

    <!-- 新建检验单 -->
    <el-dialog v-model="createVisible" :title="t('compliance.createCoa')" width="780px" top="6vh">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
          <el-form-item :label="t('stock.material')" prop="material_id">
            <el-select v-model="form.material_id" class="w-full">
              <el-option v-for="m in materials" :key="m.id" :label="`${m.name} (${m.code})`" :value="m.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('compliance.coaNo')">
            <el-input v-model="form.coa_no" :placeholder="t('common.optional')" />
          </el-form-item>
          <el-form-item :label="t('compliance.direction')">
            <el-select v-model="form.direction" class="w-full">
              <el-option :label="t('compliance.directionIncoming')" value="incoming" />
              <el-option :label="t('compliance.directionOutgoing')" value="outgoing" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('stock.lotNo')">
            <el-input v-model="form.lot_id" :placeholder="t('common.optional')" />
          </el-form-item>
          <el-form-item :label="t('compliance.sampleAt')">
            <el-date-picker v-model="form.sample_at" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" class="w-full" />
          </el-form-item>
          <el-form-item :label="t('compliance.testedAt')">
            <el-date-picker v-model="form.tested_at" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" class="w-full" />
          </el-form-item>
        </div>

        <div class="flex items-center justify-between mb-2">
          <span class="text-[13px] font-semibold text-[var(--el-text-color-primary)]">{{ t('compliance.items') }}</span>
          <el-button size="small" @click="addItem">{{ t('compliance.addItem') }}</el-button>
        </div>
        <el-table :data="form.items" size="small" border>
          <el-table-column :label="t('compliance.itemName')" min-width="160">
            <template #default="{ row }">
              <el-input v-model="row.name" size="small" />
            </template>
          </el-table-column>
          <el-table-column :label="t('compliance.itemValue')" width="150">
            <template #default="{ row }">
              <el-input v-model="row.value" size="small" />
            </template>
          </el-table-column>
          <el-table-column :label="t('compliance.itemSpec')" width="150">
            <template #default="{ row }">
              <el-input v-model="row.spec" size="small" />
            </template>
          </el-table-column>
          <el-table-column :label="t('common.actions')" width="80" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="form.items.splice($index, 1)">
                {{ t('common.delete') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-form-item :label="t('common.remark')" class="mt-3">
          <el-input v-model="form.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 判定放行 -->
    <el-dialog v-model="decideVisible" :title="t('compliance.decideTitle')" width="520px">
      <el-form label-width="110px">
        <el-form-item :label="t('compliance.coaNo')">
          <span>{{ decideRow?.coa_no }}</span>
        </el-form-item>
        <el-form-item :label="t('compliance.decideResult')">
          <el-radio-group v-model="decideForm.result">
            <el-radio label="pass">{{ t('status.pass') }}</el-radio>
            <el-radio label="fail">{{ t('status.fail') }}</el-radio>
            <el-radio label="hold">{{ t('status.hold') }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="t('common.remark')">
          <el-input v-model="decideForm.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="decideVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="onDecide">{{ t('compliance.decide') }}</el-button>
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
import { masterApi, type MaterialOut } from '@/api/master'
import { complianceApi, type CoaOut } from '@/api/compliance'
import { useStatus } from '@/composables/useStatus'

const { t } = useI18n()
const { label, tagType } = useStatus()

const loading = ref(false)
const saving = ref(false)
const rows = ref<CoaOut[]>([])
const materials = ref<MaterialOut[]>([])

const filters = reactive({
  material_id: undefined as number | undefined,
  result: undefined as string | undefined,
})

function materialLabel(id: number) {
  const m = materials.value.find((x) => x.id === id)
  return m ? `${m.name} (${m.code})` : String(id)
}

async function load() {
  loading.value = true
  try {
    const [coaList, materialList] = await Promise.all([
      complianceApi.listCoa({ material_id: filters.material_id, result: filters.result }),
      masterApi.listMaterials(),
    ])
    rows.value = coaList
    materials.value = materialList
  } finally {
    loading.value = false
  }
}

function onReset() {
  filters.material_id = undefined
  filters.result = undefined
  load()
}

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  material_id: undefined as number | undefined,
  coa_no: '',
  direction: 'incoming',
  lot_id: '',
  sample_at: null as string | null,
  tested_at: null as string | null,
  note: '',
  items: [] as Array<{ name: string; value: string; spec: string }>,
})

const rules: FormRules = {
  material_id: [{ required: true, message: t('common.required'), trigger: 'change' }],
}

function addItem() {
  form.items.push({ name: '', value: '', spec: '' })
}

function openCreate() {
  form.material_id = materials.value[0]?.id
  form.coa_no = ''
  form.direction = 'incoming'
  form.lot_id = ''
  form.sample_at = null
  form.tested_at = null
  form.note = ''
  form.items = []
  addItem()
  createVisible.value = true
}

async function onCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await complianceApi.createCoa({
      material_id: form.material_id as number,
      coa_no: form.coa_no.trim() || null,
      lot_id: form.lot_id ? Number(form.lot_id) : null,
      direction: form.direction,
      sample_at: form.sample_at,
      tested_at: form.tested_at,
      note: form.note.trim() || null,
      items: form.items
        .filter((i) => i.name)
        .map((i) => ({ name: i.name, value: i.value, spec: i.spec })),
    })
    ElMessage.success(t('common.success'))
    createVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

const decideVisible = ref(false)
const decideRow = ref<CoaOut | null>(null)
const decideForm = reactive({
  result: 'pass' as 'pass' | 'fail' | 'hold',
  note: '',
})

function openDecide(row: CoaOut) {
  decideRow.value = row
  decideForm.result = 'pass'
  decideForm.note = ''
  decideVisible.value = true
}

async function onDecide() {
  if (!decideRow.value) return
  saving.value = true
  try {
    await complianceApi.decideCoa(decideRow.value.id, {
      result: decideForm.result,
      note: decideForm.note.trim() || null,
    })
    ElMessage.success(t('compliance.decideOk'))
    decideVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>