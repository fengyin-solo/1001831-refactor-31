<template>
  <section class="page" data-module="maintenance-reminders">
    <header class="page-head">
      <div>
        <h2>保养提醒</h2>
        <p class="page-desc">只展示服务端机械台账按统一口径判为「待保养」的机械；状态结论以后台台账为准，页面不做任何临时判断，已报废机械不会出现在这里。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/equip">返回机械台账</RouterLink>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>机械编号</span>
        <input v-model="keyword" placeholder="按机械编号检索" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length" class="empty-state">当前没有需要保养的机械</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条保养提醒</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Row = Record<string, string | number | null>
type ReminderPayload = {
  items: Row[]
  total: number
  page: number
  size: number
  status_summary: Record<string, number>
}

const ENDPOINT = '/api/equip/maintenance-reminders'
const columns = ["机械编号", "机械名称", "机械型号", "停放场地", "上次保养日", "下次保养日", "责任人", "机械状态"]

// 卡片与列表都直接消费服务端台账的结论，界面不重算到期/可用/报废。
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const stats = ref([
  { label: "待保养机械", value: 0 },
  { label: "可用机械", value: 0 },
  { label: "保养中机械", value: 0 },
  { label: "已报废机械", value: 0 },
])

function resetFilters() {
  keyword.value = ''
  void reload()
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(keyword.value ? { keyword: keyword.value } : {}).toString()
  try {
    const payload = await fetchJson<ReminderPayload>(`${ENDPOINT}?${query}`)
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    const summary = payload.status_summary ?? {}
    stats.value = [
      { label: "待保养机械", value: summary["待保养"] ?? 0 },
      { label: "可用机械", value: summary["可用"] ?? 0 },
      { label: "保养中机械", value: summary["保养中"] ?? 0 },
      { label: "已报废机械", value: summary["已报废"] ?? 0 },
    ]
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '保养提醒读取失败'
  }
}

onMounted(reload)
</script>
