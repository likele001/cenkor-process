<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('stock.title')" :description="t('stock.desc')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button size="small" @click="openFefo">{{ t('stock.fefo') }}</el-button>
      <el-button size="small" @click="openMerge">{{ t('stock.merge') }}</el-button>
      <el-button type="primary" size="small" @click="openReceive">{{ t('stock.receive') }}</el-button>
    </template>

    <AdminFilterBar show-reset @reset="onReset">
      <el-select v-model="filters.warehouse_id" size="small" clearable :placeholder="t('stock.warehouse')" style="width: 170px">
        <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
      </el-select>
      <el-select v-model="filters.material_id" size="small" clearable :placeholder="t('stock.material')" style="width: 190px">
        <el-option v-for="m in materials" :key="m.id" :label="`${m.name} (${m.code})`" :value="m.id" />
      </el-select>
      <el-select v-model="filters.status" size="small" clearable :placeholder="t('common.status')" style="width: 140px">
        <el-option v-for="s in statusOptions" :key="s" :label="label(s)" :value="s" />
      </el-select>
      <template #extra>
        <el-button size="small" type="primary" @click="load">{{ t('common.search') }}</el-button>
      </template>
    </AdminFilterBar>

    <AdminDataTable :loading="loading" :empty="!loading && !rows.length" :show-pagination="false" class="mt-3">
      <template #table>
        <el-table :data="rows" size="small" border>
          <el-table-column prop="lot_no" :label="t('stock.lotNo')" min-width="150" />
          <el-table-column :label="t('stock.material')" min-width="170">
            <template #default="{ row }">{{ materialLabel(row.material_id) }}</template>
          </el-table-column>
          <el-table-column :label="t('stock.warehouse')" min-width="140">
            <template #default="{ row }">{{ warehouseLabel(row.warehouse_id) }}</template>
          </el-table-column>
          <el-table-column :label="t('stock.qty')" width="130">
            <template #default="{ row }">{{ row.qty }} {{ uomLabel(row.uom_id) }}</template>
          </el-table-column>
          <el-table-column :label="t('stock.producedAt')" width="120">
            <template #default="{ row }">{{ row.produced_at || '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('stock.expiryAt')" width="120">
            <template #default="{ row }">{{ row.expiry_at || '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('common.status')" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="tagType(row.status)">{{ label(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('common.actions')" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openSplit(row)">{{ t('stock.split') }}</el-button>
              <el-button link type="primary" size="small" @click="goGenealogy(row.id)">{{ t('stock.genealogy') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </AdminDataTable>

    <!-- 收货入库 -->
    <el-dialog v-model="receiveVisible" :title="t('stock.receiveTitle')" width="620px">
      <el-form :model="receiveForm" :rules="receiveRules" ref="receiveRef" label-width="120px">
        <el-form-item :label="t('stock.warehouse')" prop="warehouse_id">
          <el-select v-model="receiveForm.warehouse_id" class="w-full">
            <el-option v-for="w in warehouses" :key="w.id" :label="`${w.name} (${w.code})`" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('stock.material')" prop="material_id">
          <el-select v-model="receiveForm.material_id" class="w-full">
            <el-option v-for="m in materials" :key="m.id" :label="`${m.name} (${m.code})`" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('stock.lotNo')" prop="lot_no">
          <el-input v-model="receiveForm.lot_no" placeholder="LOT-0001" />
        </el-form-item>
        <el-form-item :label="t('stock.supplierLot')">
          <el-input v-model="receiveForm.supplier_lot_no" />
        </el-form-item>
        <el-form-item :label="t('stock.qty')" prop="qty">
          <el-input v-model="receiveForm.qty" placeholder="500" />
        </el-form-item>
        <el-form-item :label="t('stock.uom')" prop="uom_id">
          <el-select v-model="receiveForm.uom_id" class="w-full">
            <el-option v-for="u in uoms" :key="u.id" :label="`${u.name} (${u.code})`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('stock.producedAt')">
          <el-date-picker v-model="receiveForm.produced_at" type="date" value-format="YYYY-MM-DD" class="w-full" />
        </el-form-item>
        <el-form-item :label="t('stock.expiryAt')">
          <el-date-picker v-model="receiveForm.expiry_at" type="date" value-format="YYYY-MM-DD" class="w-full" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="receiveVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="onReceive">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- FEFO 预演 -->
    <el-dialog v-model="fefoVisible" :title="t('stock.fefoTitle')" width="640px">
      <el-form label-width="120px">
        <el-form-item :label="t('stock.warehouse')">
          <el-select v-model="fefoForm.warehouse_id" class="w-full">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('stock.material')">
          <el-select v-model="fefoForm.material_id" class="w-full">
            <el-option v-for="m in materials" :key="m.id" :label="`${m.name} (${m.code})`" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('stock.needQty')">
          <el-input v-model="fefoForm.qty" placeholder="100" />
        </el-form-item>
      </el-form>
      <el-button type="primary" size="small" :loading="fefoLoading" @click="onFefo">{{ t('stock.fefo') }}</el-button>
      <div v-if="fefoResult" class="mt-3">
        <el-tag size="small" :type="fefoResult.enough ? 'success' : 'danger'" class="mb-2">
          {{ fefoResult.enough ? t('stock.enough') : t('stock.notEnough') }}
        </el-tag>
        <el-table :data="fefoResult.plan" size="small" border>
          <el-table-column prop="lot_no" :label="t('stock.lotNo')" min-width="150" />
          <el-table-column :label="t('stock.expiryAt')" width="130">
            <template #default="{ row }">{{ row.expiry_at || '—' }}</template>
          </el-table-column>
          <el-table-column prop="take_qty" :label="t('stock.takeQty')" width="120" />
        </el-table>
      </div>
    </el-dialog>

    <!-- 合批 -->
    <el-dialog v-model="mergeVisible" :title="t('stock.mergeTitle')" width="640px">
      <el-form label-width="120px">
        <el-form-item :label="t('stock.mergeSelect')">
          <el-select v-model="mergeForm.lot_ids" multiple class="w-full" :placeholder="t('stock.mergeSelect')">
            <el-option v-for="l in rows" :key="l.id" :label="`${l.lot_no} · ${materialLabel(l.material_id)}`" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('stock.newLotNo')">
          <el-input v-model="mergeForm.lot_no" :placeholder="t('common.optional')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mergeVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="onMerge">{{ t('stock.merge') }}</el-button>
      </template>
    </el-dialog>

    <!-- 拆批 -->
    <el-dialog v-model="splitVisible" :title="t('stock.splitTitle')" width="720px">
      <p class="text-[13px] text-[var(--admin-brand-subtitle)] mb-3">
        {{ t('stock.lotNo') }}: {{ splitLotRow?.lot_no }}
      </p>
      <div class="flex items-center justify-between mb-2">
        <span class="text-[13px] font-semibold text-[var(--el-text-color-primary)]">{{ t('stock.splitParts') }}</span>
        <el-button size="small" @click="addSplitPart">{{ t('stock.addPart') }}</el-button>
      </div>
      <el-table :data="splitForm.parts" size="small" border>
        <el-table-column :label="t('stock.qty')" width="160">
          <template #default="{ row }">
            <el-input v-model="row.qty" size="small" />
          </template>
        </el-table-column>
        <el-table-column :label="t('stock.newLotNo')" min-width="180">
          <template #default="{ row }">
            <el-input v-model="row.lot_no" size="small" :placeholder="t('common.optional')" />
          </template>
        </el-table-column>
        <el-table-column :label="t('stock.expiryAt')" width="170">
          <template #default="{ row }">
            <el-date-picker v-model="row.expiry_at" type="date" value-format="YYYY-MM-DD" size="small" class="w-full" />
          </template>
        </el-table-column>
        <el-table-column :label="t('common.actions')" width="80" align="center">
          <template #default="{ $index }">
            <el-button link type="danger" size="small" @click="splitForm.parts.splice($index, 1)">
              {{ t('common.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="splitVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="onSplit">{{ t('stock.split') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import AdminDataTable from '@/components/admin/AdminDataTable.vue'
import AdminFilterBar from '@/components/admin/AdminFilterBar.vue'
import { masterApi, type MaterialOut, type UomOut, type WarehouseOut } from '@/api/master'
import {
  stockApi,
  type FefoPlanOut,
  type StockLotOut,
} from '@/api/stock'
import { useStatus } from '@/composables/useStatus'

const { t } = useI18n()
const { label, tagType } = useStatus()
const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const rows = ref<StockLotOut[]>([])
const uoms = ref<UomOut[]>([])
const materials = ref<MaterialOut[]>([])
const warehouses = ref<WarehouseOut[]>([])

const filters = reactive({
  warehouse_id: undefined as number | undefined,
  material_id: undefined as number | undefined,
  status: undefined as string | undefined,
})
const statusOptions = ['received', 'frozen', 'consumed', 'expired', 'quarantined', 'rejected']

function materialLabel(id: number) {
  const m = materials.value.find((x) => x.id === id)
  return m ? `${m.name} (${m.code})` : String(id)
}
function warehouseLabel(id: number) {
  const w = warehouses.value.find((x) => x.id === id)
  return w ? `${w.name} (${w.code})` : String(id)
}
function uomLabel(id: number) {
  const u = uoms.value.find((x) => x.id === id)
  return u ? u.code : String(id)
}

async function load() {
  loading.value = true
  try {
    const [lots, uomList, materialList, warehouseList] = await Promise.all([
      stockApi.listLots({
        warehouse_id: filters.warehouse_id,
        material_id: filters.material_id,
        status: filters.status,
      }),
      masterApi.listUoms(),
      masterApi.listMaterials(),
      masterApi.listWarehouses(),
    ])
    rows.value = lots
    uoms.value = uomList
    materials.value = materialList
    warehouses.value = warehouseList
  } finally {
    loading.value = false
  }
}

function onReset() {
  filters.warehouse_id = undefined
  filters.material_id = undefined
  filters.status = undefined
  load()
}

function goGenealogy(lotId: number) {
  router.push({ path: '/stock/genealogy', query: { lot_id: lotId } })
}

// 收货入库
const receiveVisible = ref(false)
const receiveRef = ref<FormInstance>()
const receiveForm = reactive({
  warehouse_id: undefined as number | undefined,
  material_id: undefined as number | undefined,
  lot_no: '',
  supplier_lot_no: '',
  qty: '',
  uom_id: undefined as number | undefined,
  produced_at: null as string | null,
  expiry_at: null as string | null,
})
const receiveRules: FormRules = {
  warehouse_id: [{ required: true, message: t('common.required'), trigger: 'change' }],
  material_id: [{ required: true, message: t('common.required'), trigger: 'change' }],
  lot_no: [{ required: true, message: t('common.required'), trigger: 'blur' }],
  qty: [{ required: true, message: t('common.required'), trigger: 'blur' }],
  uom_id: [{ required: true, message: t('common.required'), trigger: 'change' }],
}

function openReceive() {
  receiveForm.warehouse_id = warehouses.value[0]?.id
  receiveForm.material_id = materials.value[0]?.id
  receiveForm.lot_no = ''
  receiveForm.supplier_lot_no = ''
  receiveForm.qty = ''
  receiveForm.uom_id = uoms.value[0]?.id
  receiveForm.produced_at = null
  receiveForm.expiry_at = null
  receiveVisible.value = true
}

async function onReceive() {
  const valid = await receiveRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await stockApi.receiveLot({
      warehouse_id: receiveForm.warehouse_id as number,
      material_id: receiveForm.material_id as number,
      lot_no: receiveForm.lot_no.trim(),
      qty: receiveForm.qty,
      uom_id: receiveForm.uom_id as number,
      produced_at: receiveForm.produced_at,
      expiry_at: receiveForm.expiry_at,
      supplier_lot_no: receiveForm.supplier_lot_no.trim() || null,
    })
    ElMessage.success(t('stock.receiveOk'))
    receiveVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

// FEFO
const fefoVisible = ref(false)
const fefoLoading = ref(false)
const fefoResult = ref<FefoPlanOut | null>(null)
const fefoForm = reactive({
  warehouse_id: undefined as number | undefined,
  material_id: undefined as number | undefined,
  qty: '',
})

function openFefo() {
  fefoForm.warehouse_id = warehouses.value[0]?.id
  fefoForm.material_id = materials.value[0]?.id
  fefoForm.qty = ''
  fefoResult.value = null
  fefoVisible.value = true
}

async function onFefo() {
  if (!fefoForm.warehouse_id || !fefoForm.material_id || !fefoForm.qty) return
  fefoLoading.value = true
  try {
    fefoResult.value = await stockApi.fefoPreview({
      warehouse_id: fefoForm.warehouse_id,
      material_id: fefoForm.material_id,
      qty: fefoForm.qty,
    })
  } finally {
    fefoLoading.value = false
  }
}

// 合批
const mergeVisible = ref(false)
const mergeForm = reactive({
  lot_ids: [] as number[],
  lot_no: '',
})

function openMerge() {
  mergeForm.lot_ids = []
  mergeForm.lot_no = ''
  mergeVisible.value = true
}

async function onMerge() {
  if (mergeForm.lot_ids.length < 2) {
    ElMessage.warning(t('stock.mergeSelect'))
    return
  }
  saving.value = true
  try {
    await stockApi.mergeLots({
      lot_ids: mergeForm.lot_ids,
      lot_no: mergeForm.lot_no.trim() || null,
    })
    ElMessage.success(t('stock.mergeOk'))
    mergeVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

// 拆批
const splitVisible = ref(false)
const splitLotRow = ref<StockLotOut | null>(null)
const splitForm = reactive({
  parts: [] as Array<{ qty: string; lot_no: string; expiry_at: string | null }>,
})

function openSplit(row: StockLotOut) {
  splitLotRow.value = row
  splitForm.parts = [{ qty: '', lot_no: '', expiry_at: null }]
  splitVisible.value = true
}

function addSplitPart() {
  splitForm.parts.push({ qty: '', lot_no: '', expiry_at: null })
}

async function onSplit() {
  if (!splitLotRow.value) return
  const parts = splitForm.parts.filter((p) => p.qty)
  if (!parts.length) {
    ElMessage.warning(t('common.required'))
    return
  }
  saving.value = true
  try {
    await stockApi.splitLot(splitLotRow.value.id, {
      parts: parts.map((p) => ({
        qty: p.qty,
        lot_no: p.lot_no.trim() || null,
        expiry_at: p.expiry_at,
      })),
    })
    ElMessage.success(t('stock.splitOk'))
    splitVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>