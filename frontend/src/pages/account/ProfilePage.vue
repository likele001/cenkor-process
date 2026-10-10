<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('account.profile')">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      <AdminPage class="!p-5">
        <template #title>
          <span class="text-[15px] font-semibold">{{ t('account.profileTitle') }}</span>
        </template>
        <el-descriptions :column="1" border class="mt-2">
          <el-descriptions-item :label="t('auth.login.username')">{{ me?.username }}</el-descriptions-item>
          <el-descriptions-item :label="t('account.fullName')">{{ me?.full_name || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('account.phone')">{{ me?.phone || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('account.email')">{{ me?.email || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('account.role')">
            {{ me?.is_superuser ? t('account.admin') : t('account.user') }}
          </el-descriptions-item>
        </el-descriptions>
      </AdminPage>

      <AdminPage class="!p-5">
        <template #title>
          <span class="text-[15px] font-semibold">{{ t('account.changePassword') }}</span>
        </template>
        <el-form :model="form" :rules="rules" ref="formRef" label-position="top" class="mt-2">
          <el-form-item :label="t('account.oldPassword')" prop="old_password">
            <el-input v-model="form.old_password" type="password" show-password autocomplete="off" />
          </el-form-item>
          <el-form-item :label="t('account.newPassword')" prop="new_password">
            <el-input v-model="form.new_password" type="password" show-password autocomplete="off" />
          </el-form-item>
          <el-button type="primary" :loading="submitting" @click="onSubmit">{{ t('common.save') }}</el-button>
        </el-form>
      </AdminPage>
    </div>
  </AdminPage>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { useAuthStore } from '@/stores/auth'
import { changePasswordApi } from '@/api/auth'

const { t } = useI18n()
const auth = useAuthStore()
const me = auth.me

const formRef = ref<FormInstance>()
const submitting = ref(false)
const form = reactive({ old_password: '', new_password: '' })

const rules: FormRules = {
  old_password: [{ required: true, message: t('account.required'), trigger: 'blur' }],
  new_password: [
    { required: true, message: t('account.required'), trigger: 'blur' },
    { min: 6, message: t('account.passwordMin'), trigger: 'blur' },
  ],
}

async function onSubmit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await changePasswordApi({ ...form })
    ElMessage.success(t('common.success'))
    form.old_password = ''
    form.new_password = ''
  } catch {
    /* http 已提示 */
  } finally {
    submitting.value = false
  }
}
</script>