<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('home.title')" :description="t('home.description')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
    </template>

    <div v-loading="loading" class="space-y-5">
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <div class="stat-card tone-blue">
          <div class="stat-value">{{ stats.materials }}</div>
          <div class="stat-label">{{ t('home.statMaterials') }}</div>
        </div>
        <div class="stat-card tone-violet">
          <div class="stat-value">{{ stats.recipes }}</div>
          <div class="stat-label">{{ t('home.statRecipes') }}</div>
        </div>
        <div class="stat-card tone-green">
          <div class="stat-value">{{ stats.batches }}</div>
          <div class="stat-label">{{ t('home.statBatches') }}</div>
        </div>
        <div class="stat-card tone-mint">
          <div class="stat-value">{{ stats.lots }}</div>
          <div class="stat-label">{{ t('home.statLots') }}</div>
        </div>
        <div class="stat-card tone-rose">
          <div class="stat-value">{{ stats.alerts }}</div>
          <div class="stat-label">{{ t('home.statAlerts') }}</div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="lg:col-span-2">
          <div class="text-[14px] font-semibold mb-2 text-[var(--el-text-color-primary)]">
            {{ t('home.recentBatches') }}
          </div>
          <el-table :data="recentBatches" size="small" border>
            <el-table-column prop="batch_no" :label="t('batch.batchNo')" min-width="140" />
            <el-table-column prop="product_material_id" :label="t('batch.product')" width="100" />
            <el-table-column :label="t('batch.plannedQty')" width="110">
              <template #default="{ row }">{{ row.planned_qty }}</template>
            </el-table-column>
            <el-table-column :label="t('common.status')" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="tagType(row.status)">{{ label(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('common.actions')" width="90">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openBatch(row.id)">
                  {{ t('common.detail') }}
                </el-button>
              </template>
            </el-table-column>
            <template #empty>
              <div class="py-6 text-center text-[13px] text-el-placeholder">{{ t('home.noBatches') }}</div>
            </template>
          </el-table>
        </div>

        <div>
          <div class="text-[14px] font-semibold mb-2 text-[var(--el-text-color-primary)]">
            {{ t('home.quickActions') }}
          </div>
          <div class="flex flex-col gap-2">
            <el-button class="admin-shortcut-btn w-full !justify-start" @click="go('/recipes')">
              {{ t('home.openRecipes') }}
            </el-button>
            <el-button class="admin-shortcut-btn w-full !justify-start" @click="go('/batches')">
              {{ t('home.openBatches') }}
            </el-button>
            <el-button class="admin-shortcut-btn w-full !justify-start" @click="go('/stock/lots')">
              {{ t('home.openStock') }}
            </el-button>
            <el-button class="admin-shortcut-btn w-full !justify-start" @click="go('/compliance/alerts')">
              {{ t('home.openAlerts') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { masterApi } from '@/api/master'
import { recipeApi } from '@/api/recipe'
import { batchApi, type BatchOut } from '@/api/batch'
import { stockApi } from '@/api/stock'
import { complianceApi } from '@/api/compliance'
import { useStatus } from '@/composables/useStatus'

const { t } = useI18n()
const { label, tagType } = useStatus()
const router = useRouter()

const loading = ref(false)
const stats = reactive({ materials: 0, recipes: 0, batches: 0, lots: 0, alerts: 0 })
const recentBatches = ref<BatchOut[]>([])

function go(path: string) {
  router.push(path)
}

function openBatch(id: number) {
  router.push(`/batches/${id}`)
}

async function load() {
  loading.value = true
  const results = await Promise.allSettled([
    masterApi.listMaterials(),
    recipeApi.list(),
    batchApi.list(),
    stockApi.listLots(),
    complianceApi.alerts(),
  ])
  if (results[0].status === 'fulfilled') stats.materials = results[0].value.length
  if (results[1].status === 'fulfilled') stats.recipes = results[1].value.length
  if (results[2].status === 'fulfilled') {
    const list = results[2].value
    stats.batches = list.length
    recentBatches.value = list.slice(0, 8)
  }
  if (results[3].status === 'fulfilled') stats.lots = results[3].value.length
  if (results[4].status === 'fulfilled') stats.alerts = results[4].value.total
  loading.value = false
}

onMounted(load)
</script>