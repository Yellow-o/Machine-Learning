<script setup lang="ts">
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { useAuthStore } from '@/stores/auth'
import { useEventsStore } from '@/stores/events'
import type { EventItem } from '@/types/api'

const authStore = useAuthStore()
const eventsStore = useEventsStore()

const detailVisible = ref(false)
const dateRange = ref<string[]>([])

const reviewOptions = [
  { label: '全部状态', value: '' },
  { label: '系统判定', value: 'auto' },
  { label: '待复核', value: 'pending' },
  { label: '复核确认', value: 'confirmed' },
  { label: '误报', value: 'false_positive' },
]

const isAdmin = computed(() => authStore.isAdmin)

function fmtNum(value: number, digits = 2) {
  return Number(value || 0).toFixed(digits)
}

function fmtTime(value: string) {
  const dt = dayjs(value)
  return dt.isValid() ? dt.format('YYYY-MM-DD HH:mm:ss') : '-'
}

function reviewTagType(status: string) {
  if (status === 'confirmed') return 'danger'
  if (status === 'pending') return 'warning'
  if (status === 'false_positive') return 'info'
  return 'primary'
}

function riskTagType(conf: number) {
  if (conf >= 0.85) return 'danger'
  if (conf >= 0.7) return 'warning'
  return 'success'
}

function syncRangeToFilters() {
  eventsStore.filters.start_date = dateRange.value?.[0] || ''
  eventsStore.filters.end_date = dateRange.value?.[1] || ''
}

async function onSearch() {
  syncRangeToFilters()
  try {
    await eventsStore.fetchList(true)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '查询失败')
  }
}

async function onReset() {
  eventsStore.resetFilters()
  dateRange.value = []
  try {
    await eventsStore.fetchList(true)
    ElMessage.success('筛选条件已重置')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '重置失败')
  }
}

async function onOpenDetail(row: EventItem) {
  try {
    await eventsStore.fetchDetail(row.id)
    detailVisible.value = true
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '详情加载失败')
  }
}

async function onReview(row: EventItem, status: 'confirmed' | 'false_positive') {
  const label = status === 'confirmed' ? '确认疲劳' : '判定误报'
  try {
    const result = await ElMessageBox.prompt(`请输入复核备注（${label}）`, '事件复核', {
      inputType: 'textarea',
      inputPlaceholder: '可为空，建议填写操作依据',
      cancelButtonText: '取消',
      confirmButtonText: '提交',
    })
    await eventsStore.review(row.id, status, result.value || '')
    ElMessage.success('复核状态已更新')
  } catch (err) {
    if (err === 'cancel' || err === 'close') return
    ElMessage.error(err instanceof Error ? err.message : '复核失败')
  }
}

async function onAppeal(row: EventItem) {
  try {
    const result = await ElMessageBox.prompt('请输入申诉理由', '发起复核', {
      inputType: 'textarea',
      inputPlaceholder: '请描述误判原因',
      cancelButtonText: '取消',
      confirmButtonText: '提交申诉',
      inputValidator: (value) => (value.trim() ? true : '申诉理由不能为空'),
    })
    await eventsStore.appeal(row.id, result.value)
    ElMessage.success('申诉已提交，状态已变为待复核')
  } catch (err) {
    if (err === 'cancel' || err === 'close') return
    ElMessage.error(err instanceof Error ? err.message : '申诉失败')
  }
}

async function onPageChange(page: number) {
  eventsStore.pagination.page = page
  await eventsStore.fetchList()
}

async function onPageSizeChange(size: number) {
  eventsStore.pagination.page_size = size
  eventsStore.pagination.page = 1
  await eventsStore.fetchList()
}

onMounted(() => {
  eventsStore.fetchList().catch(() => {})
})
</script>

<template>
  <section class="grid fade-up">
    <header class="page-head">
      <div>
        <h3>事件中心</h3>
        <p>支持筛选查询、详情查看与复核闭环操作</p>
      </div>
      <el-button :loading="eventsStore.loading" @click="eventsStore.fetchList()">刷新</el-button>
    </header>

    <el-card class="panel" shadow="never">
      <div class="filters">
        <el-input
          v-model="eventsStore.filters.q"
          class="filter-item"
          placeholder="账号 / 标签 / 会话ID"
          clearable
          @keyup.enter="onSearch"
        />
        <el-select v-model="eventsStore.filters.review_status" class="filter-item" placeholder="复核状态" clearable>
          <el-option v-for="item in reviewOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-input
          v-model="eventsStore.filters.min_conf"
          class="filter-item"
          placeholder="最小风险值 (0~1)"
          clearable
          @keyup.enter="onSearch"
        />
        <el-date-picker
          v-model="dateRange"
          class="filter-item date-filter"
          type="daterange"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          unlink-panels
        />
        <div class="actions">
          <el-button type="primary" @click="onSearch">查询</el-button>
          <el-button @click="onReset">重置</el-button>
        </div>
      </div>
    </el-card>

    <el-alert v-if="eventsStore.error" type="error" :title="eventsStore.error" :closable="false" show-icon />

    <div class="summary panel">
      <span>总数 {{ eventsStore.summary.total }}</span>
      <span>累计时长 {{ fmtNum(eventsStore.summary.total_duration_sec, 1) }}s</span>
      <span>平均风险 {{ fmtNum(eventsStore.summary.avg_conf, 3) }}</span>
      <span>最高风险 {{ fmtNum(eventsStore.summary.max_conf, 3) }}</span>
    </div>

    <el-card class="panel" shadow="never">
      <el-table :data="eventsStore.items" stripe v-loading="eventsStore.loading" table-layout="auto">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="driver_name" label="账号" min-width="120" />
        <el-table-column label="类型 / 标签" min-width="140">
          <template #default="{ row }">
            <div class="double">
              <strong>{{ row.event_type_display }}</strong>
              <small>{{ row.source_label || '-' }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="风险值" width="110">
          <template #default="{ row }">
            <el-tag :type="riskTagType(row.peak_risk_conf)">{{ fmtNum(row.peak_risk_conf, 3) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="复核状态" width="125">
          <template #default="{ row }">
            <el-tag :type="reviewTagType(row.review_status)">{{ row.review_status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" min-width="170">
          <template #default="{ row }">{{ fmtTime(row.start_time) }}</template>
        </el-table-column>
        <el-table-column label="截图" width="100">
          <template #default="{ row }">
            <el-link type="primary" @click="onOpenDetail(row)">查看</el-link>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="210" fixed="right">
          <template #default="{ row }">
            <el-space>
              <el-button size="small" @click="onOpenDetail(row)">详情</el-button>
              <template v-if="isAdmin && row.review_status === 'pending'">
                <el-button
                  size="small"
                  type="danger"
                  :loading="eventsStore.actionLoading"
                  @click="onReview(row, 'confirmed')"
                >
                  确认疲劳
                </el-button>
                <el-button
                  size="small"
                  type="info"
                  :loading="eventsStore.actionLoading"
                  @click="onReview(row, 'false_positive')"
                >
                  判定误报
                </el-button>
              </template>
              <el-button
                v-else-if="!isAdmin && row.review_status === 'auto'"
                size="small"
                type="warning"
                :loading="eventsStore.actionLoading"
                @click="onAppeal(row)"
              >
                申诉复核
              </el-button>
            </el-space>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager-wrap">
        <el-pagination
          layout="total, sizes, prev, pager, next"
          :total="eventsStore.pagination.total"
          :page-size="eventsStore.pagination.page_size"
          :current-page="eventsStore.pagination.page"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </el-card>

    <el-drawer v-model="detailVisible" title="事件详情" size="460px">
      <el-skeleton :loading="eventsStore.detailLoading" animated>
        <template #template>
          <el-skeleton-item variant="text" style="width: 100%; height: 24px; margin-bottom: 8px" />
          <el-skeleton-item variant="text" style="width: 96%; height: 24px; margin-bottom: 8px" />
          <el-skeleton-item variant="image" style="width: 100%; height: 200px" />
        </template>

        <template #default>
          <div v-if="eventsStore.selectedEvent" class="detail-grid">
            <div><span>ID</span><b>{{ eventsStore.selectedEvent.id }}</b></div>
            <div><span>账号</span><b>{{ eventsStore.selectedEvent.driver_name }}</b></div>
            <div><span>状态</span><b>{{ eventsStore.selectedEvent.review_status_display }}</b></div>
            <div><span>风险</span><b>{{ fmtNum(eventsStore.selectedEvent.peak_risk_conf, 3) }}</b></div>
            <div><span>开始时间</span><b>{{ fmtTime(eventsStore.selectedEvent.start_time) }}</b></div>
            <div><span>结束时间</span><b>{{ fmtTime(eventsStore.selectedEvent.end_time) }}</b></div>
            <div><span>会话ID</span><b>{{ eventsStore.selectedEvent.source_session_id || '-' }}</b></div>
            <div><span>标签</span><b>{{ eventsStore.selectedEvent.source_label || '-' }}</b></div>
            <div class="snap">
              <span>截图</span>
              <el-image
                v-if="eventsStore.selectedEvent.snapshot_path"
                :src="eventsStore.selectedEvent.snapshot_path"
                :preview-src-list="[eventsStore.selectedEvent.snapshot_path]"
                fit="cover"
                class="preview"
                preview-teleported
              />
              <p v-else>无截图</p>
            </div>
          </div>
        </template>
      </el-skeleton>
    </el-drawer>
  </section>
</template>

<style scoped>
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.filter-item {
  flex: 1 1 220px;
  min-width: 0;
}

.date-filter {
  flex: 1 1 360px;
  min-width: 260px;
  width: 100%;
}

.date-filter :deep(.el-date-editor) {
  width: 100%;
  max-width: 100%;
}

.actions {
  display: flex;
  gap: 8px;
  flex: 0 0 auto;
  margin-left: auto;
  justify-content: flex-end;
  white-space: nowrap;
}

.summary {
  padding: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  color: var(--ink-1);
}

.double {
  display: grid;
  gap: 2px;
}

.double small {
  color: var(--ink-2);
}

.pager-wrap {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.detail-grid {
  display: grid;
  gap: 10px;
}

.detail-grid > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px dashed var(--line-soft);
  padding-bottom: 6px;
}

.detail-grid span {
  color: var(--ink-2);
}

.detail-grid b {
  color: var(--ink-0);
  text-align: right;
}

.snap {
  display: grid !important;
  gap: 8px;
}

.preview {
  width: 100%;
  height: 220px;
  border-radius: 8px;
  border: 1px solid var(--line-soft);
}

@media (max-width: 1200px) {
  .actions {
    width: 100%;
    margin-left: 0;
    justify-content: flex-end;
  }
}

@media (max-width: 680px) {
  .filter-item,
  .date-filter {
    flex-basis: 100%;
    min-width: 0;
  }

  .actions {
    justify-content: flex-start;
  }
}
</style>
