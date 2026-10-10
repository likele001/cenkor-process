// Copyright (C) 2026 CenkorProcess Project
// SPDX-License-Identifier: AGPL-3.0
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { i18n } from '@/locales'
import { tryRecoverStaleChunk } from '@/utils/chunk-reload'
import { ensureExtensionsLoaded, hasExtensionRoute } from '@/utils/extensionLoader'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { public: true, title: () => i18n.global.t('menu.login') },
  },
  {
    path: '/',
    name: 'app-layout',
    component: () => import('@/layouts/AppLayout.vue'),
    redirect: '/home',
    children: [
      { path: '', redirect: 'home' },
      {
        path: 'home',
        name: 'home',
        component: () => import('@/pages/HomePage.vue'),
        meta: { title: () => i18n.global.t('menu.home') },
      },
      {
        path: 'account/profile',
        name: 'account-profile',
        component: () => import('@/pages/account/ProfilePage.vue'),
        meta: { title: () => i18n.global.t('account.profile') },
      },

      // 主数据
      {
        path: 'master/uoms',
        name: 'master-uoms',
        component: () => import('@/pages/master/UomsPage.vue'),
        meta: { title: () => i18n.global.t('menu.uoms') },
      },
      {
        path: 'master/materials',
        name: 'master-materials',
        component: () => import('@/pages/master/MaterialsPage.vue'),
        meta: { title: () => i18n.global.t('menu.materials') },
      },
      {
        path: 'master/warehouses',
        name: 'master-warehouses',
        component: () => import('@/pages/master/WarehousesPage.vue'),
        meta: { title: () => i18n.global.t('menu.warehouses') },
      },
      {
        path: 'master/uom-conversions',
        name: 'master-uom-conversions',
        component: () => import('@/pages/master/UomConversionsPage.vue'),
        meta: { title: () => i18n.global.t('menu.uomConversions') },
      },

      // 配方
      {
        path: 'recipes',
        name: 'recipes',
        component: () => import('@/pages/recipe/RecipesPage.vue'),
        meta: { title: () => i18n.global.t('menu.recipes') },
      },
      {
        path: 'recipes/:id',
        name: 'recipe-detail',
        component: () => import('@/pages/recipe/RecipeDetailPage.vue'),
        meta: { title: () => i18n.global.t('recipe.detailTitle') },
      },

      // 批次
      {
        path: 'batches',
        name: 'batches',
        component: () => import('@/pages/batch/BatchesPage.vue'),
        meta: { title: () => i18n.global.t('menu.batches') },
      },
      {
        path: 'batches/:id',
        name: 'batch-detail',
        component: () => import('@/pages/batch/BatchDetailPage.vue'),
        meta: { title: () => i18n.global.t('batch.detailTitle') },
      },

      // 库存
      {
        path: 'stock/lots',
        name: 'stock-lots',
        component: () => import('@/pages/stock/StockLotsPage.vue'),
        meta: { title: () => i18n.global.t('menu.stockLots') },
      },
      {
        path: 'stock/genealogy',
        name: 'stock-genealogy',
        component: () => import('@/pages/stock/GenealogyPage.vue'),
        meta: { title: () => i18n.global.t('menu.genealogy') },
      },

      // 合规与质量
      {
        path: 'compliance/ccps',
        name: 'compliance-ccps',
        component: () => import('@/pages/compliance/CcpsPage.vue'),
        meta: { title: () => i18n.global.t('menu.ccps') },
      },
      {
        path: 'compliance/ccp-records',
        name: 'compliance-ccp-records',
        component: () => import('@/pages/compliance/CcpRecordsPage.vue'),
        meta: { title: () => i18n.global.t('menu.ccpRecords') },
      },
      {
        path: 'compliance/cip-logs',
        name: 'compliance-cip-logs',
        component: () => import('@/pages/compliance/CipLogsPage.vue'),
        meta: { title: () => i18n.global.t('menu.cipLogs') },
      },
      {
        path: 'compliance/coa',
        name: 'compliance-coa',
        component: () => import('@/pages/compliance/CoaPage.vue'),
        meta: { title: () => i18n.global.t('menu.coa') },
      },
      {
        path: 'compliance/temp-logs',
        name: 'compliance-temp-logs',
        component: () => import('@/pages/compliance/TempLogsPage.vue'),
        meta: { title: () => i18n.global.t('menu.tempLogs') },
      },
      {
        path: 'compliance/alerts',
        name: 'compliance-alerts',
        component: () => import('@/pages/compliance/AlertsPage.vue'),
        meta: { title: () => i18n.global.t('menu.alerts') },
      },

      { path: ':pathMatch(.*)*', name: 'adminNotFound', redirect: '/home' },
    ],
  },
  { path: '/:pathMatch(.*)*', name: 'notFound', redirect: '/home' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public) return true
  if (!auth.hasKey) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (!auth.me) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
  // 首次进入时加载扩展前端（注册动态路由/菜单/多语言）；
  // deep-link 命中扩展路由时，解析早于注册会被兜底重定向，需按原路径重试一次
  if (await ensureExtensionsLoaded()) {
    const orig = to.redirectedFrom
    if (orig && hasExtensionRoute(orig.path)) {
      return { path: orig.fullPath, replace: true }
    }
  }
  return true
})

router.onError((error) => {
  tryRecoverStaleChunk(error)
})

export default router