<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <el-config-provider :locale="epLocale">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import { useAppConfigStore } from '@/stores/app-config'
import { getStoredLocale } from '@/locales'

// Element Plus 内置文案语言（启动时确定，无运行时切换）
function resolveElementPlusLocale(locale: string) {
  return locale === 'en-US' ? en : zhCn
}
const epLocale = resolveElementPlusLocale(getStoredLocale())

const appConfig = useAppConfigStore()

onMounted(() => appConfig.load())

watch(() => appConfig.browserTitle, (title) => {
  document.title = title
})
</script>