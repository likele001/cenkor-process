<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('master.conversionsTitle')" :description="t('master.conversionsDesc')">
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <el-card shadow="never">
        <div class="text-[14px] font-semibold mb-3 text-[var(--el-text-color-primary)]">
          {{ t('master.convert') }}
        </div>
        <el-form label-width="120px">
          <el-form-item :label="t('master.pickMaterial')">
            <el-select v-model="convertForm.material_id" clearable class="w-full">
              <el-option v-for="m in materials" :key="m.id" :label="`${m.name} (${m.code})`" :value="m.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('master.fromUom')">
            <el-select v-model="convertForm.from_uom_id" class="w-full">
              <el-option v-for="u in uoms" :key="u.id" :label="`${u.name} (${u.code})`" :value="u.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('master.toUom')">
            <el-select v-model="convertForm.to_uom_id" class="w-full">
              <el-option v-for="u in uoms" :key="u.id" :label="`${u.name} (${u.code})`" :value="u.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('master.convertQty')">
            <el-input v-model="convertForm.qty" placeholder="100" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="converting" @click="onConvert">{{ t('master.convert') }}</el-button>
          </el-form-item>
        </el-form>

        <el-alert v-if="convertResult" type="success" :closable="false" class="mt-1">
          <div class="text-[13px]">
            <div>{{ t('master.convertResult') }}：<b>{{ convertResult.result }}</b></div>
            <div class="mt-1 text-el-placeholder">
              {{ t('master.convertMode') }}：{{ convertResult.mode }}
              <span v-if="convertResult.density_kg_l"> · 密度 {{ convertResult.density_kg_l }}</span>
            </div>
          </div>
        </el-alert>
      </el-card>

      <el-card shadow="never">
        <div class="text-[14px] font-semibold mb-3 text-[var(--el-text-color-primary)]">
          {{ t('master.newConversion') }}
        </div>
        <el-form label-width="120px">
          <el-form-item :label="t('master.fromUom')">
            <el-select v-model="newForm.from_uom_id" class="w-full">
              <el-option v-for="u in uoms" :key="u.id" :label="`${u.name} (${u.code})`" :value="u.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('master.toUom')">
            <el-select v-model="newForm.to_uom_id" class="w-full">
              <el-option v-for="u in uoms" :key="u.id" :label="`${u.name} (${u.code})`" :value="u.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('master.pickMaterial')">
            <el-select v-model="newForm.material_id" clearable class="w-full">
              <el-option v-for="m in materials" :key="m.id" :label="`${m.name} (${m.code})`" :value="m.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('master.factor')">
            <el-input v-model="newForm.factor" placeholder="1000" />
          </el-form-item>
          <el-form-item :label="t('master.density')">
            <el-input v-model="newForm.density_kg_l" placeholder="1.00000000" />
          </el-form-item>
          <el-form-item :label="t('master.conversionNote')">
            <el-input v-model="newForm.note" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="onSaveConversion">
              {{ t('master.saveConversion') }}
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { masterApi, type MaterialOut, type UomConvertOut, type UomOut } from '@/api/master'

const { t } = useI18n()

const uoms = ref<UomOut[]>([])
const materials = ref<MaterialOut[]>([])

const converting = ref(false)
const saving = ref(false)
const convertResult = ref<UomConvertOut | null>(null)

const convertForm = reactive({
  qty: '100',
  from_uom_id: undefined as number | undefined,
  to_uom_id: undefined as number | undefined,
  material_id: undefined as number | undefined,
})

const newForm = reactive({
  from_uom_id: undefined as number | undefined,
  to_uom_id: undefined as number | undefined,
  material_id: undefined as number | undefined,
  factor: '',
  density_kg_l: '',
  note: '',
})

async function load() {
  const [uomList, materialList] = await Promise.all([masterApi.listUoms(), masterApi.listMaterials()])
  uoms.value = uomList
  materials.value = materialList
  if (!convertForm.from_uom_id && uomList[0]) convertForm.from_uom_id = uomList[0].id
  if (!convertForm.to_uom_id && uomList[1]) convertForm.to_uom_id = uomList[1].id
  if (!newForm.from_uom_id && uomList[0]) newForm.from_uom_id = uomList[0].id
  if (!newForm.to_uom_id && uomList[1]) newForm.to_uom_id = uomList[1].id
}

async function onConvert() {
  if (!convertForm.from_uom_id || !convertForm.to_uom_id || !convertForm.qty) {
    ElMessage.warning(t('common.required'))
    return
  }
  converting.value = true
  try {
    convertResult.value = await masterApi.convert({
      qty: convertForm.qty,
      from_uom_id: convertForm.from_uom_id,
      to_uom_id: convertForm.to_uom_id,
      material_id: convertForm.material_id ?? null,
    })
  } finally {
    converting.value = false
  }
}

async function onSaveConversion() {
  if (!newForm.from_uom_id || !newForm.to_uom_id) {
    ElMessage.warning(t('common.required'))
    return
  }
  saving.value = true
  try {
    await masterApi.createConversion({
      from_uom_id: newForm.from_uom_id,
      to_uom_id: newForm.to_uom_id,
      material_id: newForm.material_id ?? null,
      factor: newForm.factor.trim() || null,
      density_kg_l: newForm.density_kg_l.trim() || null,
      note: newForm.note.trim() || null,
    })
    ElMessage.success(t('master.conversionSaved'))
    newForm.factor = ''
    newForm.density_kg_l = ''
    newForm.note = ''
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>