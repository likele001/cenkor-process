<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <el-menu
    class="admin-sider-menu border-0"
    :class="menuRootClass"
    :default-active="active"
    :collapse="layout === 'sider' && collapse"
    router
  >
    <el-menu-item index="/home">
      <el-icon><House /></el-icon>
      <span>{{ t('menu.home') }}</span>
    </el-menu-item>

    <el-menu-item v-if="showMarket" index="/system/market">
      <el-icon><Shop /></el-icon>
      <span>{{ t('menu.market') }}</span>
    </el-menu-item>

    <el-sub-menu v-for="g in groups" :key="g.key" :index="g.key">
      <template #title>
        <el-icon><component :is="g.icon" /></el-icon>
        <span>{{ t(g.i18nKey) }}</span>
      </template>
      <el-menu-item v-for="it in g.items" :key="it.path" :index="it.path">
        <el-icon><component :is="it.icon" /></el-icon>
        <span>{{ t(it.i18nKey) }}</span>
      </el-menu-item>
    </el-sub-menu>

    <el-sub-menu v-if="extMenuItems.length" index="ext-apps">
      <template #title>
        <el-icon><Grid /></el-icon>
        <span>{{ t('menu.extensions') }}</span>
      </template>
      <el-menu-item v-for="it in extMenuItems" :key="it.path" :index="it.path">
        <el-icon><component :is="iconOf(it.icon)" /></el-icon>
        <span>{{ extMenuLabel(it) }}</span>
      </el-menu-item>
    </el-sub-menu>
  </el-menu>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  Aim,
  Box,
  Brush,
  Coin,
  DocumentChecked,
  Files,
  Grid,
  House,
  Notebook,
  Odometer,
  OfficeBuilding,
  Share,
  Shop,
  Stamp,
  Switch,
  Tickets,
  WarningFilled,
} from '@element-plus/icons-vue'

import * as ElIcons from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { extensionMenus, type ExtensionMenu } from '@/utils/extensionLoader'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    layout?: 'sider' | 'drawer'
    collapse?: boolean
  }>(),
  { layout: 'sider', collapse: false }
)

const menuRootClass = computed(() =>
  props.layout === 'sider' ? 'h-full min-h-0 overflow-y-auto' : 'pb-2'
)

type Leaf = { path: string; i18nKey: string; icon: Component }
type Group = { key: string; i18nKey: string; icon: Component; items: Leaf[] }

const route = useRoute()
const active = computed(() => route.path)

const auth = useAuthStore()

/** 已加载扩展的菜单项（按当前用户权限过滤） */
const extMenuItems = computed(() =>
  extensionMenus.value.filter((m) => auth.hasAnyPermission(m.permission ? [m.permission] : undefined))
)

/** 应用中心入口（market.view 门控；超管即刻可见） */
const showMarket = computed(() => auth.hasAnyPermission(['market.view']))

/** 插件菜单图标名 → Element Plus 图标组件（未命中时回退 Grid） */
function iconOf(name?: string): Component {
  if (!name) return Grid
  const mod = ElIcons as unknown as Record<string, Component>
  return mod[name] || Grid
}

function extMenuLabel(m: ExtensionMenu & { key: string }): string {
  return m.i18nKey ? t(m.i18nKey) : m.title
}

const groups: Group[] = [
  {
    key: 'master',
    i18nKey: 'menu.master',
    icon: Files,
    items: [
      { path: '/master/uoms', i18nKey: 'menu.uoms', icon: Coin },
      { path: '/master/materials', i18nKey: 'menu.materials', icon: Box },
      { path: '/master/warehouses', i18nKey: 'menu.warehouses', icon: OfficeBuilding },
      { path: '/master/uom-conversions', i18nKey: 'menu.uomConversions', icon: Switch },
    ],
  },
  {
    key: 'recipe',
    i18nKey: 'menu.recipe',
    icon: Notebook,
    items: [{ path: '/recipes', i18nKey: 'menu.recipes', icon: Notebook }],
  },
  {
    key: 'batch',
    i18nKey: 'menu.batch',
    icon: Tickets,
    items: [{ path: '/batches', i18nKey: 'menu.batches', icon: Tickets }],
  },
  {
    key: 'stock',
    i18nKey: 'menu.stock',
    icon: Box,
    items: [
      { path: '/stock/lots', i18nKey: 'menu.stockLots', icon: Box },
      { path: '/stock/genealogy', i18nKey: 'menu.genealogy', icon: Share },
    ],
  },
  {
    key: 'compliance',
    i18nKey: 'menu.compliance',
    icon: Aim,
    items: [
      { path: '/compliance/ccps', i18nKey: 'menu.ccps', icon: Aim },
      { path: '/compliance/ccp-records', i18nKey: 'menu.ccpRecords', icon: DocumentChecked },
      { path: '/compliance/cip-logs', i18nKey: 'menu.cipLogs', icon: Brush },
      { path: '/compliance/coa', i18nKey: 'menu.coa', icon: Stamp },
      { path: '/compliance/temp-logs', i18nKey: 'menu.tempLogs', icon: Odometer },
      { path: '/compliance/alerts', i18nKey: 'menu.alerts', icon: WarningFilled },
    ],
  },
]
</script>