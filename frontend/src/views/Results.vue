<template>
  <div class="page">
    <el-header class="header">
      <span class="brand" @click="$router.push('/')">报表生成平台</span>
      <div class="right">
        <el-button :type="$route.path === '/datasources' ? 'primary' : ''" text @click="$router.push('/datasources')">数据源</el-button>
        <el-button :type="$route.path === '/metadata' ? 'primary' : ''" text @click="$router.push('/metadata')">元数据</el-button>
        <el-button :type="$route.path === '/workspace' ? 'primary' : ''" text @click="$router.push('/workspace')">工作台</el-button>
        <el-button :type="$route.path === '/results' ? 'primary' : ''" text @click="$router.push('/results')">结果中心</el-button>
        <el-button v-if="['admin', 'dept_admin'].includes(user.role)" :type="$route.path === '/approvals' ? 'primary' : ''" text @click="$router.push('/approvals')">审批</el-button>
        <span class="user">{{ user.username }}</span>
        <el-button link type="danger" @click="handleLogout">退出登录</el-button>
      </div>
    </el-header>

    <el-main class="main">
      <el-card shadow="never">
        <template #header>结果中心（统计表）</template>
        <el-table :data="results" v-loading="loading" empty-text="暂无结果，请到工作台生成统计表">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="business_name" label="需求描述" min-width="220" show-overflow-tooltip />
          <el-table-column prop="table_name" label="结果表名" min-width="180" />
          <el-table-column prop="row_count" label="行数" width="90" />
          <el-table-column label="生成时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="row.result_type === 'aggregate' ? 'primary' : 'warning'" effect="plain">
                {{ row.result_type === 'aggregate' ? '统计' : '明细' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260">
            <template #default="{ row }">
              <el-button link type="primary" @click="openPreview(row)">预览</el-button>
              <el-button link type="success" @click="exportResult(row, 'xlsx')">导出 Excel</el-button>
              <el-button link @click="exportResult(row, 'csv')">导出 CSV</el-button>
              <el-button
                v-if="row.result_type === 'add_column' && !row.applied_to_source"
                link
                type="warning"
                @click="openApply(row)"
              >申请写回</el-button>
              <el-tag v-else-if="row.result_type === 'add_column'" type="success" size="small" effect="plain">已写回</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 写回申请弹窗 -->
      <el-dialog v-model="applyVisible" title="申请写回原表" width="480">
        <el-alert type="warning" :closable="false" class="apply-tip">
          写回将修改原始数据表，需管理员审批通过后执行
        </el-alert>
        <el-input v-model="applyReason" type="textarea" :rows="3" placeholder="请填写写回理由" />
        <template #footer>
          <el-button @click="applyVisible = false">取消</el-button>
          <el-button type="primary" :loading="applyLoading" @click="submitApply">提交申请</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="previewVisible" :title="`结果预览：${current?.table_name || ''}`" width="80%">
        <el-table :data="previewData.rows" max-height="450" size="small" border v-loading="previewLoading">
          <el-table-column
            v-for="(c, i) in previewData.columns"
            :key="c.name"
            :label="c.name"
            :prop="String(i)"
            min-width="130"
          />
        </el-table>
      </el-dialog>
    </el-main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../api/request'
import { useUserStore } from '../stores/user'

const router = useRouter()
const user = useUserStore()

const results = ref([])
const loading = ref(false)
const previewVisible = ref(false)
const previewLoading = ref(false)
const current = ref(null)
const previewData = ref({ columns: [], rows: [] })
const applyVisible = ref(false)
const applyReason = ref('')
const applyLoading = ref(false)
const applyTarget = ref(null)

onMounted(load)

async function load() {
  loading.value = true
  try {
    results.value = await request.get('/results')
  } finally {
    loading.value = false
  }
}

async function openPreview(row) {
  current.value = row
  previewVisible.value = true
  previewLoading.value = true
  try {
    previewData.value = await request.get(`/results/${row.id}/preview?limit=100`)
  } finally {
    previewLoading.value = false
  }
}

async function exportResult(row, format) {
  const resp = await request.get(`/results/${row.id}/export?format=${format}`, { responseType: 'blob' })
  const url = URL.createObjectURL(resp)
  const a = document.createElement('a')
  a.href = url
  a.download = `${row.table_name}.${format}`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('已开始下载')
}

function openApply(row) {
  applyTarget.value = row
  applyReason.value = ''
  applyVisible.value = true
}

async function submitApply() {
  if (!applyReason.value.trim()) {
    ElMessage.warning('请填写写回理由')
    return
  }
  applyLoading.value = true
  try {
    await request.post('/approvals', {
      job_id: applyTarget.value.job_id,
      reason: applyReason.value.trim(),
    })
    applyVisible.value = false
    ElMessage.success('申请已提交，等待管理员审批')
  } finally {
    applyLoading.value = false
  }
}

function formatTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN') : '-'
}

function handleLogout() {
  ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' })
    .then(() => {
      user.logout()
      router.push('/login')
    })
    .catch(() => {})
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f7fa;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}
.brand {
  font-weight: 600;
  font-size: 18px;
  cursor: pointer;
}
.right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user {
  color: #606266;
}
.main {
  max-width: 1200px;
  margin: 0 auto;
}
</style>
