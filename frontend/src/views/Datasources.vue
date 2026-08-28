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
      <!-- 上传 -->
      <el-card shadow="never" class="card">
        <template #header>上传 Excel</template>
        <el-upload
          drag
          accept=".xlsx"
          :show-file-list="false"
          :http-request="handleUpload"
          :disabled="uploading"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽 .xlsx 文件到此处，或 <em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">仅支持 .xlsx，单文件不超过 {{ maxMb }}MB，多 sheet 自动拆分为多张表</div>
          </template>
        </el-upload>
        <el-alert v-if="uploadResult" type="success" :closable="false" class="result-tip">
          上传成功：{{ uploadResult.name }}，共 {{ uploadResult.tables.length }} 张表
        </el-alert>
      </el-card>

      <!-- 接入数据库（管理员） -->
      <el-card v-if="user.role === 'admin' || user.role === 'dept_admin'" shadow="never" class="card">
        <template #header>接入业务数据库（只读）</template>
        <el-form :inline="true">
          <el-form-item label="名称">
            <el-input v-model="dbForm.name" placeholder="如：业务主库" style="width: 160px" />
          </el-form-item>
          <el-form-item label="连接串">
            <el-input
              v-model="dbForm.url"
              placeholder="postgresql+psycopg://user:pwd@host:5432/db"
              style="width: 380px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="dbLoading" @click="registerDb">接入并拉取表结构</el-button>
          </el-form-item>
        </el-form>
        <div class="tip">支持 PostgreSQL / MySQL / SQL Server 等 SQLAlchemy 兼容数据库，请使用只读账号</div>
      </el-card>

      <!-- 数据源列表 -->
      <el-card shadow="never" class="card">
        <template #header>数据源列表</template>
        <el-table :data="datasources" v-loading="loading" empty-text="暂无数据源，请先上传 Excel 或接入数据库">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="名称" min-width="200" />
          <el-table-column prop="type" label="类型" width="90" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'ready' ? 'success' : 'danger'">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDatasource(row)">查看表</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 表列表 -->
      <el-card v-if="tables.length" shadow="never" class="card">
        <template #header>数据表（{{ tables.length }}）</template>
        <el-table :data="tables">
          <el-table-column prop="sheet_name" label="表名" min-width="120" />
          <el-table-column prop="table_name" label="物理表名" min-width="140" />
          <el-table-column prop="row_count" label="行数" width="90" />
          <el-table-column label="字段数" width="90">
            <template #default="{ row }">{{ row.columns.length }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button link type="primary" @click="openPreview(row)">预览数据</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 预览弹窗 -->
      <el-dialog v-model="previewVisible" :title="`数据预览：${previewTable?.sheet_name || ''}`" width="80%">
        <el-descriptions :column="3" size="small" border class="fields">
          <el-descriptions-item v-for="c in previewData.columns" :key="c.name" :label="c.business_name">
            {{ c.name }}（{{ c.data_type }}）
          </el-descriptions-item>
        </el-descriptions>
        <el-table :data="previewData.rows" max-height="400" size="small" border v-loading="previewLoading">
          <el-table-column
            v-for="(c, i) in previewData.columns"
            :key="c.name"
            :label="c.business_name || c.name"
            :prop="String(i)"
            min-width="120"
          />
        </el-table>
      </el-dialog>
    </el-main>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import request from '../api/request'
import { useUserStore } from '../stores/user'

const router = useRouter()
const user = useUserStore()

const maxMb = 20
const uploading = ref(false)
const uploadResult = ref(null)
const datasources = ref([])
const tables = ref([])
const loading = ref(false)

const dbForm = reactive({ name: '', url: '' })
const dbLoading = ref(false)

const previewVisible = ref(false)
const previewLoading = ref(false)
const previewTable = ref(null)
const previewData = ref({ columns: [], rows: [] })

onMounted(loadDatasources)

async function loadDatasources() {
  loading.value = true
  try {
    datasources.value = await request.get('/datasources')
  } finally {
    loading.value = false
  }
}

async function handleUpload({ file }) {
  if (file.size > maxMb * 1024 * 1024) {
    ElMessage.error(`文件超过 ${maxMb}MB 限制`)
    return
  }
  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    uploadResult.value = await request.post('/upload', form)
    await loadDatasources()
    await openDatasource({ id: uploadResult.value.datasource_id })
  } finally {
    uploading.value = false
  }
}

async function registerDb() {
  if (!dbForm.name || !dbForm.url) {
    ElMessage.warning('请填写数据源名称和连接串')
    return
  }
  dbLoading.value = true
  try {
    const result = await request.post('/datasources/db', dbForm)
    ElMessage.success(`接入成功：${result.table_count} 张表`)
    dbForm.name = ''
    dbForm.url = ''
    await loadDatasources()
  } finally {
    dbLoading.value = false
  }
}

async function openDatasource(ds) {
  tables.value = await request.get(`/datasources/${ds.id}/tables`)
}

async function openPreview(table) {
  previewTable.value = table
  previewVisible.value = true
  previewLoading.value = true
  try {
    previewData.value = await request.get(`/tables/${table.id}/preview?limit=100`)
  } finally {
    previewLoading.value = false
  }
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
  max-width: 1100px;
  margin: 0 auto;
}
.card {
  margin-bottom: 16px;
}
.result-tip {
  margin-top: 12px;
}
.fields {
  margin-bottom: 12px;
}
.tip {
  color: #909399;
  font-size: 12px;
}
</style>
