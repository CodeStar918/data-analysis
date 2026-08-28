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
        <template #header>数据字典管理（管理员）</template>
        <el-form :inline="true">
          <el-form-item label="数据源">
            <el-select v-model="selectedDs" placeholder="选择数据源" style="width: 260px" @change="loadTables">
              <el-option v-for="d in datasources" :key="d.id" :label="`[${d.type}] ${d.name}`" :value="d.id" />
            </el-select>
          </el-form-item>
        </el-form>

        <el-empty v-if="!tables.length" description="请选择数据源" />

        <div v-for="t in tables" :key="t.id" class="table-block">
          <div class="table-title">
            <span class="phys">{{ t.table_name }}</span>
            <el-input v-model="t.business_name" size="small" style="width: 220px" />
            <el-button size="small" type="primary" link @click="saveTable(t)">保存表名</el-button>
            <span class="rows">{{ t.row_count || '-' }} 行</span>
          </div>
          <el-table :data="t.columns" size="small" border>
            <el-table-column prop="name" label="字段名" min-width="140" />
            <el-table-column prop="data_type" label="类型" width="130" />
            <el-table-column label="业务名称" min-width="160">
              <template #default="{ row }">
                <el-input v-model="row.business_name" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="维度/度量" width="120">
              <template #default="{ row }">
                <el-select v-model="row.role" size="small" @change="row.default_agg = row.role === 'dim' ? '' : (row.default_agg || 'SUM')">
                  <el-option label="维度" value="dim" />
                  <el-option label="度量" value="measure" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="默认聚合" width="110">
              <template #default="{ row }">
                <el-select v-model="row.default_agg" size="small" :disabled="row.role !== 'measure'">
                  <el-option label="-" value="" />
                  <el-option v-for="a in aggs" :key="a" :label="a" :value="a" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="saveColumn(row)">保存</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>
    </el-main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../api/request'
import { useUserStore } from '../stores/user'

const router = useRouter()
const user = useUserStore()

const aggs = ['SUM', 'COUNT', 'AVG', 'MAX', 'MIN']
const datasources = ref([])
const selectedDs = ref(null)
const tables = ref([])

onMounted(async () => {
  datasources.value = await request.get('/datasources')
})

async function loadTables(dsId) {
  tables.value = await request.get(`/datasources/${dsId}/tables`)
}

async function saveTable(t) {
  await request.patch(`/metadata/tables/${t.id}`, { business_name: t.business_name })
  ElMessage.success('表名已保存')
}

async function saveColumn(c) {
  await request.patch(`/metadata/columns/${c.id}`, {
    business_name: c.business_name,
    role: c.role,
    default_agg: c.default_agg,
  })
  ElMessage.success('字段已保存')
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
.table-block {
  margin-bottom: 24px;
}
.table-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.phys {
  color: #909399;
  font-family: monospace;
}
.rows {
  color: #909399;
  font-size: 12px;
}
</style>
