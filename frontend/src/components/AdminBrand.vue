<!--
  Copyright (C) 2026 CenkorProcess Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <div class="flex items-center gap-2 min-w-0">
    <div
      class="admin-brand__mark w-8 h-8 rounded-lg flex items-center justify-center shrink-0 text-[15px] font-bold"
      style="
        background: var(--admin-brand-mark-bg);
        border: 1px solid var(--admin-brand-mark-border);
        color: var(--admin-brand-mark-text);
      "
    >
      C
    </div>
    <div v-if="!compact" class="admin-sider__brand-text min-w-0">
      <div class="text-[15px] font-semibold leading-tight truncate" style="color: var(--admin-brand-title)">
        CenkorProcess
      </div>
      <div class="text-[11px] leading-tight truncate" style="color: var(--admin-brand-subtitle)">
        流程制造引擎
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })
</script>