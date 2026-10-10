<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('stock.genealogyTitle')" :description="t('stock.desc')">
    <template #actions>
      <el-button size="small" @click="onQuery">{{ t('common.search') }}</el-button>
    </template>

    <AdminFilterBar>
      <el-input
        v-model="lotIdInput"
        size="small"
        :placeholder="t('stock.queryLot')"
        style="width: 240px"
        @keyup.enter="onQuery"
      />
      <template #extra>
        <el-button size="small" type="primary" :loading="loading" @click="onQuery">{{ t('common.search') }}</el-button>
      </template>
    </AdminFilterBar>

    <div v-loading="loading" class="mt-4">
      <el-descriptions v-if="result" :column="2" border size="small" class="mb-4">
        <el-descriptions-item :label="t('stock.lotNo')">{{ result.lot_id }}</el-descriptions-item>
        <el-descriptions-item :label="t('stock.genealogy')">
          {{ t('stock.parents') }}: {{ result.parents.length }} · {{ t('stock.children') }}: {{ result.children.length }}
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="result" class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <el-card shadow="never">
          <div class="text-[14px] font-semibold mb-3 text-[var(--el-text-color-primary)]">{{ t('stock.parents') }}</div>
          <el-table :data="result.parents" size="small" border>
            <el-table-column prop="lot_id" :label="t('stock.lotNo')" min-width="140" />
            <el-table-column prop="op_type" :label="t('stock.opType')" width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="tagType(row.op_type)">{{ label(row.op_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="amount" :label="t('stock.amount')" width="130" />
          </el-table>
          <AdminEmpty v-if="!result.parents.length" :description="t('common.noDataText')" />
        </el-card>

        <el-card shadow="never">
          <div class="text-[14px] font-semibold mb-3 text-[var(--el-text-color-primary)]">{{ t('stock.children') }}</div>
          <el-table :data="result.children" size="small" border>
            <el-table-column prop="lot_id" :label="t('stock.lotNo')" min-width="140" />
            <el-table-column prop="op_type" :label="t('stock.opType')" width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="tagType(row.op_type)">{{ label(row.op_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="amount" :label="t('stock.amount')" width="130" />
          </el-table>
          <AdminEmpty v-if="!result.children.length" :description="t('common.noDataText')" />
        </el-card>
      </div>

      <AdminEmpty v-else-if="!loading" :description="t('stock.queryLot')" />
    </div>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import AdminEmpty from '@/components/admin/AdminEmpty.vue'
import AdminFilterBar from '@/components/admin/AdminFilterBar.vue'
import { stockApi, type GenealogyOut } from '@/api/stock'
import { useStatus } from '@/composables/useStatus'

const { t } = useI18n()
const { label, tagType } = useStatus()
const route = useRoute()

const loading = ref(false)
const lotIdInput = ref('')
const result = ref<GenealogyOut | null>(null)

async function onQuery() {
  const id = Number(lotIdInput.value)
  if (!id) return
  loading.value = true
  try {
    result.value = await stockApi.genealogy(id)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const q = route.query.lot_id
  if (q) {
    lotIdInput.value = String(q)
    onQuery()
  }
})
</script>