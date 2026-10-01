<template>
  <section class="page" data-module="equip">
    <header class="page-head">
      <div>
        <h2>养护机械管理</h2>
        <p class="page-desc">维护养护机械，围绕机械编号、机械名称、机械型号、停放场地做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记养护机械</button>
        <button class="btn" type="button" @click="exportRows">导出养护机械清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <section class="reminder-box">
      <h3>保养提醒</h3>
      <p class="page-desc">名单由服务端按统一口径给出，已报废与保养中的机械不会出现。</p>
      <ul class="reminder-list">
        <li v-for="row in reminderRows" :key="String(row.id)">
          <span>{{ row['机械编号'] }} · {{ row['机械名称'] }}</span>
          <span class="muted">下次保养日：{{ row['下次保养日'] ?? '—' }} · 停放场地：{{ row['停放场地'] ?? '—' }}</span>
        </li>
        <li v-if="!reminderRows.length" class="muted">暂无到期机械</li>
      </ul>
    </section>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>机械状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无养护机械数据，可先登记养护机械</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条养护机械记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string | number | null>
type Stat = { label: string; value: number }
type PagePayload = { items?: Row[]; total?: number }

const ENDPOINT = '/api/equip'
const columns = ["机械编号", "机械名称", "机械型号", "停放场地", "上次保养日", "下次保养日", "责任人", "机械状态"]
const actions = ["安排保养", "确认可用", "报废机械"]
// 状态筛选枚举只用于渲染下拉项，到期/可用/报废的结论一律以服务端返回为准。
const statuses = ["待保养", "可用", "保养中", "已报废"]

const rows = ref<Row[]>([])
const reminderRows = ref<Row[]>([])
const stats = ref<Stat[]>([
  { label: "在册机械", value: 0 },
  { label: "待保养机械", value: 0 },
  { label: "保养中机械", value: 0 },
  { label: "已报废机械", value: 0 },
])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export/data`, '_blank')
}

function openCreate() {
  errorMessage.value = '养护机械登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('养护机械动作未生效，请稍后重试')
    }
    await Promise.all([reload(), reloadReminders(), reloadStats()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护机械操作失败'
  }
}

async function reloadStats() {
  try {
    const payload = await fetchJson<{ items: Stat[] }>(`${ENDPOINT}/stats`)
    stats.value = payload.items ?? stats.value
  } catch {
    // 统计读不出来时保留上一次结果，页面其他区块不受影响。
  }
}

async function reloadReminders() {
  try {
    const payload = await fetchJson<PagePayload>(`${ENDPOINT}/reminders`)
    // 保养提醒直接展示服务端名单，界面不再按保养日自行判断。
    reminderRows.value = payload.items ?? []
  } catch {
    reminderRows.value = []
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const payload = await fetchJson<PagePayload>(`${ENDPOINT}?${query}`)
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护机械列表读取失败'
  }
}

onMounted(() => {
  void reload()
  void reloadReminders()
  void reloadStats()
})
</script>

<style scoped>
.reminder-box {
  margin: 12px 0;
  padding: 12px 16px;
  border: 1px solid var(--border-color, #d9d9d9);
  border-radius: 8px;
  background: #fafafa;
}

.reminder-box h3 {
  margin: 0 0 4px;
  font-size: 15px;
}

.reminder-list {
  margin: 8px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 4px;
}

.muted {
  color: #888;
}
</style>
