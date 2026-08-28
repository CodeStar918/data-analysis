<template>
  <div class="page">
    <el-header class="header">
      <span class="brand" @click="$router.push('/')">报表生成平台</span>
      <div class="right">
        <el-button :type="$route.path === '/datasources' ? 'primary' : ''" text @click="$router.push('/datasources')">数据源</el-button>
        <el-button :type="$route.path === '/metadata' ? 'primary' : ''" text @click="$router.push('/metadata')">元数据</el-button>
        <el-button :type="$route.path === '/workspace' ? 'primary' : ''" text @click="$router.push('/workspace')">工作台</el-button>
        <el-button :type="$route.path === '/results' ? 'primary' : ''" text @click="$router.push('/results')">结果中心</el-button>
        <el-button :type="$route.path === '/approvals' ? 'primary' : ''" text @click="$router.push('/approvals')">审批</el-button>
        <span class="user">{{ user.username }}</span>
        <el-button link type="danger" @click="handleLogout">退出登录</el-button>
      </div>
    </el-header>

    <el-main class="main">
      <el-card shadow="never">
        <template #header>写回原表审批（管理员）</template>
        <el-table :data="approvals" v-loading="loading" empty-text="暂无审批记录">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="question" label="需求描述" min-width="200" show-overflow-tooltip />
          <el-table-column prop="reason" label="写回理由" min-width="180" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" effect="plain">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="comment" label="审批意见" min-width="140" show-overflow-tooltip />
          <el-table-column label="申请时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <template v-if="row.status === 'pending'">
                <el-button link type="success" @click="decide(row, 'approve')">通过</el-button>
                <el-button link type="danger" @click="decide(row, 'reject')">驳回</el-button>
              </template>
              <span v-else class="done-text">已处理</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
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

const approvals = ref([])
const loading = ref(false)

onMounted(load)

async function load() {
  loading.value = true
  try {
    approvals.value = await request.get('/approvals')
  } finally {
    loading.value = false
  }
}

async function decide(row, action) {
  const tip = action === 'approve'
    ? '通过后将写回原表并新增字段，确认执行？'
    : '确认驳回该写回申请？'
  const { value: comment } = await ElMessageBox.prompt(tip, action === 'approve' ? '通过审批' : '驳回', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPlaceholder: '审批意见（可选）',
    inputValue: '',
  }).catch(() => ({ value: undefined }))
  if (comment === undefined) return

  await request.post(`/approvals/${row.id}/decide`, { action, comment })
  ElMessage.success(action === 'approve' ? '已通过并写回原表' : '已驳回')
  await load()
}

function statusLabel(s) {
  return { pending: '待审批', approved: '已通过', rejected: '已驳回' }[s] || s
}
function statusType(s) {
  return { pending: 'warning', approved: 'success', rejected: 'danger' }[s] || 'info'
}
function formatTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN') : '-'
}
function handleLogout() {
  user.logout()
  router.push('/login')
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
.done-text {
  color: #909399;
  font-size: 12px;
}
</style>
