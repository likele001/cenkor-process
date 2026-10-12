<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <div class="min-h-screen p-6">
    <!-- 顶部标题与操作 -->
    <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-bold">{{ t('market.title') }}</h1>
        <p class="mt-1 text-sm opacity-70">{{ t('market.subtitle') }}</p>
      </div>
      <div class="flex items-center gap-3">
        <el-tag v-if="status.bound" type="success" size="large">
          {{ t('market.connected', { account: status.account || t('market.portalAccount') }) }}
        </el-tag>
        <el-tag v-else type="info" size="large">{{ t('market.notConnectedTag') }}</el-tag>
        <el-button v-if="status.bound" @click="showConnect = true">{{ t('market.portalSettings') }}</el-button>
        <el-button v-else type="primary" @click="showConnect = true">
          <el-icon class="mr-1"><Link /></el-icon>
          {{ t('market.connectPortal') }}
        </el-button>
        <el-button v-if="status.bound" type="primary" :loading="loading" @click="fetchApps">
          <el-icon class="mr-1"><Refresh /></el-icon>
          {{ t('market.refresh') }}
        </el-button>
      </div>
    </div>

    <!-- 未连接提示 -->
    <el-alert
      v-if="!status.bound"
      :title="t('market.notConnectedTitle')"
      :description="t('market.notConnectedDesc')"
      type="warning"
      show-icon
      :closable="false"
      class="mb-6"
    >
      <template #default>
        <el-button type="primary" class="mt-2" @click="showConnect = true">{{ t('market.connectNow') }}</el-button>
      </template>
    </el-alert>

    <!-- 已购概况：数字来自实例本地的授权快照，不是实时查 hub -->
    <div v-if="status.bound" class="mb-6">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div class="text-xs opacity-60">{{ t('market.statPurchased') }}</div>
          <div class="mt-1 text-2xl font-bold">{{ status.purchased_count ?? 0 }}</div>
        </div>
        <div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div class="text-xs opacity-60">{{ t('market.statUpdatable') }}</div>
          <div
            class="mt-1 text-2xl font-bold"
            :class="(status.updatable_count ?? 0) > 0 ? 'text-blue-600' : ''"
          >
            {{ status.updatable_count ?? 0 }}
          </div>
        </div>
        <div class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div class="text-xs opacity-60">{{ t('market.statNearestExpiry') }}</div>
          <div class="mt-1 text-2xl font-bold" :class="expirySoon ? 'text-red-600' : ''">
            {{ expiryText }}
          </div>
        </div>
      </div>
      <p class="mt-2 text-xs opacity-50">
        <span v-if="status.hub_reachable === false">{{ t('market.statHintStale') }}</span>
        <span v-else-if="status.hub_reachable === null && !status.snapshot_synced_at">
          {{ t('market.statHintPending') }}
        </span>
        <span v-else-if="status.snapshot_synced_at">
          {{ t('market.statHintSynced', { t: snapshotText }) }}
        </span>
      </p>
    </div>

    <!-- 应用列表 -->
    <div
      v-if="status.bound && apps.length > 0"
      class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
    >
      <div
        v-for="app in apps"
        :key="app.key"
        class="group relative overflow-hidden rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-all hover:shadow-md dark:border-gray-700 dark:bg-gray-800"
      >
        <div class="mb-3 flex items-start gap-3">
          <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 text-xl font-bold text-white">
            {{ app.icon || app.name.charAt(0).toUpperCase() }}
          </div>
          <div class="min-w-0 flex-1">
            <h3 class="truncate text-base font-semibold">{{ app.name }}</h3>
            <p class="text-xs opacity-60">{{ app.key }}</p>
          </div>
        </div>

        <p class="mb-4 line-clamp-2 text-sm opacity-75">{{ app.description || t('market.noDesc') }}</p>

        <div class="mb-4 flex flex-wrap gap-2">
          <el-tag v-if="app.installed" type="success" size="small">{{ t('market.installed', { v: app.installed_version }) }}</el-tag>
          <el-tag v-else type="info" size="small">{{ t('market.notInstalled') }}</el-tag>

          <el-tag v-if="app.licensed" type="success" size="small">{{ t('market.licensed') }}</el-tag>
          <el-tag v-else type="warning" size="small">{{ app.price ? t('market.needPurchase') : t('market.needClaim') }}</el-tag>

          <el-tag v-if="app.category" size="small">{{ app.category }}</el-tag>

          <el-tag v-if="app.license_expires_at" type="info" size="small">
            {{ t('market.expiresAt', { d: formatDate(app.license_expires_at) }) }}
          </el-tag>
        </div>

        <div class="flex flex-wrap gap-2">
          <el-button
            v-if="!app.installed"
            type="primary"
            size="small"
            class="flex-1"
            :disabled="!app.licensed"
            :loading="installingKey === app.key"
            @click="handleInstall(app)"
          >
            {{ app.licensed ? t('market.install') : t('market.noLicense') }}
          </el-button>
          <template v-else>
            <el-button
              v-if="hasUpdate(app)"
              type="warning"
              size="small"
              :loading="installingKey === app.key"
              @click="handleInstall(app)"
            >
              {{ t('market.updateTo', { v: app.latest_version }) }}
            </el-button>
            <el-button v-else type="success" size="small" disabled>
              {{ t('market.installed', { v: app.installed_version }) }}
            </el-button>
            <el-button
              size="small"
              :type="app.enabled ? 'info' : 'primary'"
              plain
              :loading="togglingKey === app.key"
              @click="handleToggle(app)"
            >
              {{ app.enabled ? t('market.disable') : t('market.enable') }}
            </el-button>
            <el-button
              type="danger"
              size="small"
              plain
              :loading="uninstallingKey === app.key"
              @click="handleUninstall(app)"
            >
              {{ t('market.uninstall') }}
            </el-button>
          </template>
          <el-button v-if="!app.licensed" size="small" plain @click="openPortal(app.key)">
            {{ t('market.goPortal') }}
          </el-button>
        </div>

        <div v-if="app.latest_version" class="mt-3 text-xs opacity-50">{{ t('market.latestVersion', { v: app.latest_version }) }}</div>
      </div>
    </div>

    <el-empty v-else-if="!loading && status.bound" :description="t('market.empty')">
      <el-button type="primary" plain @click="openPortal()">{{ t('market.browsePortal') }}</el-button>
    </el-empty>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <el-icon class="is-loading mr-2 text-2xl"><Loading /></el-icon>
      <span class="opacity-60">{{ t('market.loading') }}</span>
    </div>

    <!-- 门户连接向导 -->
    <el-dialog v-model="showConnect" :title="t('market.dialogTitle')" width="560px" :close-on-click-modal="false" @closed="onDialogClosed">
      <!-- 步骤 1：hub 地址 -->
      <div class="mb-5">
        <div class="mb-2 flex items-center gap-2">
          <el-tag size="small" :type="status.hub_url ? 'success' : 'warning'">1</el-tag>
          <span class="font-medium">{{ t('market.stepHub') }}</span>
        </div>
        <div class="flex gap-2">
          <el-input v-model="hubUrl" :placeholder="t('market.hubPlaceholder')" clearable @keyup.enter="saveHub" />
          <el-button type="primary" :loading="savingHub" @click="saveHub">{{ t('market.save') }}</el-button>
        </div>
        <p class="mt-1 text-xs opacity-50">{{ t('market.hubHint') }}</p>
      </div>

      <!-- 步骤 2：设备码绑定 -->
      <div>
        <div class="mb-2 flex items-center gap-2">
          <el-tag size="small" :type="status.bound ? 'success' : (bind.active ? 'warning' : 'info')">2</el-tag>
          <span class="font-medium">{{ t('market.stepBind') }}</span>
          <el-tag v-if="status.bound" type="success" size="small" class="ml-2">{{ t('market.bound') }}</el-tag>
        </div>

        <!-- 已绑定：展示账号 + 解绑 -->
        <div v-if="status.bound" class="rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-900/20">
          <p class="text-sm">{{ t('market.boundAccount', { account: status.account || '-' }) }}</p>
          <el-button type="danger" plain size="small" class="mt-3" :loading="unbinding" @click="handleUnbind">
            {{ t('market.unbind') }}
          </el-button>
        </div>

        <!-- 未绑定 -->
        <div v-else>
          <div v-if="!bind.active">
            <el-button type="primary" :disabled="!status.hub_url" :loading="startingBind" @click="startBind">
              {{ t('market.startConnect') }}
            </el-button>
            <p v-if="!status.hub_url" class="mt-2 text-xs opacity-50">{{ t('market.saveHubFirst') }}</p>
          </div>

          <div v-else class="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-900/20">
            <p class="text-sm">{{ t('market.bindInstruction') }}</p>
            <div class="my-3 flex items-center justify-center gap-3">
              <span class="font-mono text-3xl font-bold tracking-widest text-blue-700 dark:text-blue-300">{{ bind.user_code }}</span>
              <el-button size="small" text @click="copyCode">{{ t('market.copy') }}</el-button>
            </div>
            <div class="text-center">
              <el-link type="primary" :href="bind.verification_uri" target="_blank">
                {{ t('market.openPortalConfirm') }}
              </el-link>
              <span class="ml-3 text-xs opacity-50">{{ bind.countdown > 0 ? t('market.expires', { n: bind.countdown }) : t('market.expired') }}</span>
            </div>
            <div class="mt-4 flex items-center justify-center gap-2">
              <el-icon v-if="polling" class="is-loading text-blue-500"><Loading /></el-icon>
              <span class="text-sm">{{ polling ? t('market.waiting') : t('market.pollingStopped') }}</span>
            </div>
            <div class="mt-3 text-center">
              <el-button size="small" @click="cancelBind">{{ t('market.cancel') }}</el-button>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Link, Refresh, Loading } from '@element-plus/icons-vue'
import {
  getMarketStatus,
  saveMarketHub,
  bindStart,
  bindPoll,
  bindCancel,
  bindUnbind,
  getMarketApps,
  installMarketApp,
  uninstallMarketApp,
  enableExtension,
  disableExtension,
  type MarketApp,
  type MarketStatus,
} from '@/api/market'
import { reloadExtensions } from '@/utils/extensionLoader'

const { t } = useI18n()

const loading = ref(false)
const apps = ref<MarketApp[]>([])
const status = reactive<MarketStatus>({
  hub_url: '',
  product: '',
  bound: false,
  account: '',
  instance_uid: '',
  hub_reachable: null,
  purchased_count: 0,
  updatable_count: 0,
  nearest_expiry: null,
  snapshot_synced_at: '',
})

// 概况口径：后端只读进程内授权快照，缺值按 0 /「无」显示，不做乐观推断。
function _date(raw?: string | null): Date | null {
  if (!raw) return null
  const d = new Date(raw)
  return Number.isNaN(d.getTime()) ? null : d
}
const expiryDate = computed(() => _date(status.nearest_expiry))
const expiryText = computed(() => {
  if (!status.nearest_expiry) return t('market.noExpiry')
  const d = expiryDate.value
  return d ? d.toLocaleDateString() : String(status.nearest_expiry)
})
// 30 天内到期标红，与列表里「到期 {d}」的提醒口径一致
const expirySoon = computed(() => {
  const d = expiryDate.value
  return !!d && d.getTime() - Date.now() < 30 * 86400000
})
const snapshotText = computed(() => {
  const d = _date(status.snapshot_synced_at)
  return d ? d.toLocaleString() : String(status.snapshot_synced_at || '')
})

const installingKey = ref('')
const uninstallingKey = ref('')
const togglingKey = ref('')

// 连接向导
const showConnect = ref(false)
const hubUrl = ref('')
const savingHub = ref(false)
const startingBind = ref(false)
const unbinding = ref(false)
const polling = ref(false)

const bind = reactive({
  active: false,
  user_code: '',
  verification_uri: '',
  countdown: 0,
})

let pollTimer: ReturnType<typeof setInterval> | null = null
let countdownTimer: ReturnType<typeof setInterval> | null = null

function clearTimers() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  polling.value = false
}

function formatDate(s: string | null): string {
  if (!s) return ''
  const d = new Date(s)
  return isNaN(d.getTime()) ? s : d.toLocaleDateString()
}

function verCmp(a: string, b: string): number {
  const pa = String(a || '').split('.').map((x) => parseInt(x, 10) || 0)
  const pb = String(b || '').split('.').map((x) => parseInt(x, 10) || 0)
  const n = Math.max(pa.length, pb.length)
  for (let i = 0; i < n; i++) {
    const d = (pa[i] || 0) - (pb[i] || 0)
    if (d) return d > 0 ? 1 : -1
  }
  return 0
}

function hasUpdate(app: MarketApp): boolean {
  // 仅当 hub 发布版本 > 本地已装版本时才提示更新，避免把降级当更新
  return app.installed && !!app.latest_version && !!app.installed_version && verCmp(app.latest_version, app.installed_version) > 0
}

function openPortal(appKey?: string) {
  const base = (status.hub_url || '').replace(/\/+$/, '')
  if (!base) return
  const url = appKey ? `${base}/apps/${appKey}` : `${base}/apps`
  window.open(url, '_blank')
}

async function fetchStatus() {
  try {
    const res = await getMarketStatus()
    Object.assign(status, res)
    hubUrl.value = res.hub_url
  } catch (e) {
    console.error('fetchStatus error:', e)
  }
}

async function fetchApps() {
  loading.value = true
  try {
    const res = await getMarketApps()
    apps.value = res.items
    status.bound = res.bound
    status.account = res.account
    status.hub_url = res.hub_url
    // /apps 在后端会顺手刷新授权快照，所以紧接着再取一次概况：
    // 点「刷新」后列表与卡片同源，不会出现列表新、数字旧。
    await fetchStatus()
  } catch (e) {
    console.error('fetchApps error:', e)
  } finally {
    loading.value = false
  }
}

async function saveHub() {
  const url = hubUrl.value.trim().replace(/\/+$/, '')
  if (!url) {
    ElMessage.warning(t('market.msgEnterHub'))
    return
  }
  savingHub.value = true
  try {
    await saveMarketHub(url)
    status.hub_url = url
    ElMessage.success(t('market.msgHubSaved'))
  } catch (e) {
    console.error('saveHub error:', e)
  } finally {
    savingHub.value = false
  }
}

async function startBind() {
  startingBind.value = true
  try {
    const res = await bindStart()
    bind.active = true
    bind.user_code = res.user_code
    bind.verification_uri = res.verification_uri_complete || res.verification_uri
    bind.countdown = res.expires_in || 600
    startPolling(Math.max(2, res.interval || 5))
    startCountdown()
  } catch (e) {
    console.error('startBind error:', e)
  } finally {
    startingBind.value = false
  }
}

function startPolling(intervalSec: number) {
  clearTimers()
  polling.value = true
  pollTimer = setInterval(pollOnce, intervalSec * 1000)
}

function startCountdown() {
  if (countdownTimer) clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    if (bind.countdown > 0) bind.countdown -= 1
    else stopBindWaiting()
  }, 1000)
}

async function pollOnce() {
  try {
    const res = await bindPoll()
    if (res.status === 'approved') {
      stopBindWaiting()
      bind.active = false
      await fetchStatus()
      await fetchApps()
      await reloadExtensions()
      ElMessage.success(t('market.msgConnected', { account: status.account || '' }))
    } else if (['expired', 'denied', 'consumed'].includes(res.status)) {
      stopBindWaiting()
      bind.active = false
      ElMessage.warning(t('market.msgCodeExpired'))
    }
  } catch (e) {
    console.error('pollOnce error:', e)
  }
}

function stopBindWaiting() {
  clearTimers()
}

async function cancelBind() {
  try {
    await bindCancel()
  } catch (e) {
    console.error('cancelBind error:', e)
  }
  stopBindWaiting()
  bind.active = false
  bind.user_code = ''
  bind.countdown = 0
}

async function handleUnbind() {
  try {
    await ElMessageBox.confirm(t('market.unbindConfirm'), t('market.unbindConfirmTitle'), {
      confirmButtonText: t('market.unbindOk'),
      cancelButtonText: t('market.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  unbinding.value = true
  try {
    await bindUnbind()
    await fetchStatus()
    apps.value = []
    ElMessage.success(t('market.msgUnbound'))
  } catch (e) {
    console.error('unbind error:', e)
  } finally {
    unbinding.value = false
  }
}

async function copyCode() {
  try {
    await navigator.clipboard.writeText(bind.user_code)
    ElMessage.success(t('market.msgCopied'))
  } catch {
    ElMessage.warning(t('market.msgCopyFailed'))
  }
}

function onDialogClosed() {
  if (!status.bound && !bind.active) clearTimers()
}

async function handleInstall(app: MarketApp) {
  try {
    await ElMessageBox.confirm(t('market.installConfirm', { name: app.name }), t('market.installConfirmTitle'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'info',
    })
  } catch {
    return
  }
  installingKey.value = app.key
  try {
    const res = await installMarketApp(app.key)
    await fetchApps()
    await reloadExtensions()
    ElMessage.success(res.message || t('market.msgInstalled'))
  } catch (e) {
    console.error('install error:', e)
  } finally {
    installingKey.value = ''
  }
}

async function handleToggle(app: MarketApp) {
  togglingKey.value = app.key
  try {
    if (app.enabled) {
      await disableExtension(app.key)
      ElMessage.success(t('market.msgDisabled'))
    } else {
      await enableExtension(app.key)
      ElMessage.success(t('market.msgEnabled'))
    }
    await fetchApps()
    await reloadExtensions()
  } catch (e) {
    console.error('toggle error:', e)
  } finally {
    togglingKey.value = ''
  }
}

async function handleUninstall(app: MarketApp) {
  try {
    await ElMessageBox.confirm(t('market.uninstallConfirm', { name: app.name }), t('market.uninstallConfirmTitle'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }
  uninstallingKey.value = app.key
  try {
    const res = await uninstallMarketApp(app.key)
    await fetchApps()
    await reloadExtensions()
    ElMessage.success(res.message || t('market.msgUninstalled'))
  } catch (e) {
    console.error('uninstall error:', e)
  } finally {
    uninstallingKey.value = ''
  }
}

onMounted(async () => {
  await fetchStatus()
  if (status.bound) await fetchApps()
})

onBeforeUnmount(() => clearTimers())
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
