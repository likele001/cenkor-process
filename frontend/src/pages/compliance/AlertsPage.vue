<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('compliance.alertsTitle')" :description="t('compliance.alertsDesc')">
    <template #actions>
      <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
    </template>

    <div v-loading="loading">
      <div class="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
        <el-card shadow="never" class="text-center">
          <div class="text-[12px] text-[var(--admin-brand-subtitle)]">{{ t('compliance.totalAlerts') }}</div>
          <div class="text-[22px] font-semibold" style="color: var(--el-color-danger)">{{ data.total }}</div>
        </el-card>
        <el-card shadow="never" class="text-center">
          <div class="text-[12px] text-[var(--admin-brand-subtitle)]">{{ t('compliance.ccpDeviations') }}</div>
          <div class="text-[22px] font-semibold">{{ data.ccp_deviations.length }}</div>
        </el-card>
        <el-card shadow="never" class="text-center">
          <div class="text-[12px] text-[var(--admin-brand-subtitle)]">{{ t('compliance.tempOutOfRange') }}</div>
          <div class="text-[22px] font-semibold">{{ data.temp_out_of_range.length }}</div>
        </el-card>
        <el-card shadow="never" class="text-center">
          <div class="text-[12px] text-[var(--admin-brand-subtitle)]">{{ t('compliance.cipFailed') }}</div>
          <div class="text-[22px] font-semibold">{{ data.cip_failed.length }}</div>
        </el-card>
        <el-card shadow="never" class="text-center">
          <div class="text-[12px] text-[var(--admin-brand-subtitle)]">{{ t('compliance.coaFailed') }}</div>
          <div class="text-[22px] font-semibold">{{ data.coa_failed.length }}</div>
        </el-card>
      </div>

      <AdminEmpty v-if="!loading && data.total === 0" :description="t('compliance.noAlerts')" />

      <div v-else class="space-y-4">
        <el-card v-if="data.ccp_deviations.length" shadow="never">
          <div class="text-[14px] font-semibold mb-3 text-[var(--el-text-color-primary)]">{{ t('compliance.ccpDeviations') }}</div>
          <el-table :data="data.ccp_deviations" size="small" border>
            <el-table-column v-for="key in columns(data.ccp_deviations)" :key="key" :prop="key" :label="key" min-width="120" />
          </el-table>
        </el-card>

        <el-card v-if="data.temp_out_of_range.length" shadow="never">
          <div class="text-[14px] font-semibold mb-3 text-[var(--el-text-color-primary)]">{{ t('compliance.tempOutOfRange') }}</div>
          <el-table :data="data.temp_out_of_range" size="small" border>
            <el-table-column v-for="key in columns(data.temp_out_of_range)" :key="key" :prop="key" :label="key" min-width="120" />
          </el-table>
        </el-card>

        <el-card v-if="data.cip_failed.length" shadow="never">
          <div class="text-[14px] font-semibold mb-3 text-[var(--el-text-color-primary)]">{{ t('compliance.cipFailed') }}</div>
          <el-table :data="data.cip_failed" size="small" border>
            <el-table-column v-for="key in columns(data.cip_failed)" :key="key" :prop="key" :label="key" min-width="120" />
          </el-table>
        </el-card>

        <el-card v-if="data.coa_failed.length" shadow="never">
          <div class="text-[14px] font-semibold mb-3 text-[var(--el-text-color-primary)]">{{ t('compliance.coaFailed') }}</div>
          <el-table :data="data.coa_failed" size="small" border>
            <el-table-column v-for="key in columns(data.coa_failed)" :key="key" :prop="key" :label="key" min-width="120" />
          </el-table>
        </el-card>
      </div>
    </div>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import AdminEmpty from '@/components/admin/AdminEmpty.vue'
import { complianceApi, type ComplianceAlertOut } from '@/api/compliance'

const { t } = useI18n()

const loading = ref(false)
const data = ref<ComplianceAlertOut>({
  ccp_deviations: [],
  temp_out_of_range: [],
  cip_failed: [],
  coa_failed: [],
  total: 0,
})

function columns(rows: Array<Record<string, unknown>>): string[] {
  return rows.length ? Object.keys(rows[0]) : []
}

async function load() {
  loading.value = true
  try {
    data.value = await complianceApi.alerts()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>