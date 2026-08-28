<template>
  <div class="page">
    <el-header class="header">
      <span class="brand" @click="$router.push('/')">报表生成平台</span>
      <div class="right">
        <el-button :type="$route.path === '/datasources' ? 'primary' : ''" text @click="$router.push('/datasources')">数据源</el-button>
        <el-button :type="$route.path === '/metadata' ? 'primary' : ''" text @click="$router.push('/metadata')">元数据</el-button>
        <el-button :type="$route.path === '/workspace' ? 'primary' : ''" text @click="$router.push('/workspace')">工作台</el-button>
        <span class="user">{{ user.username }}</span>
        <el-button link type="danger" @click="handleLogout">退出登录</el-button>
      </div>
    </el-header>

    <el-main class="main">
      <!-- 选择数据 -->
      <el-card shadow="never" class="card">
        <el-form :inline="true">
          <el-form-item label="数据表">
            <el-select v-model="selectedTable" placeholder="选择要分析的数据表" style="width: 380px">
              <el-option
                v-for="t in allTables"
                :key="t.id"
                :label="`[${t.ds_name}] ${t.business_name || t.table_name}`"
                :value="t.id"
              />
            </el-select>
          </el-form-item>
        </el-form>

        <!-- 对话式输入 -->
        <div class="chat-input">
          <el-input
            v-model="question"
            size="large"
            placeholder="用一句话描述你的需求，例如：按区域统计销售额，只看2024年"
            :disabled="parsing"
            @keyup.enter="doParse"
          />
          <el-button type="primary" size="large" :loading="parsing" @click="doParse">解析</el-button>
        </div>
        <div class="examples">
          示例：
          <el-tag v-for="ex in examples" :key="ex" class="ex-tag" type="info" effect="plain" @click="question = ex">
            {{ ex }}
          </el-tag>
        </div>
      </el-card>

      <!-- 解析结果 -->
      <el-card v-if="parseResult" shadow="never" class="card">
        <template #header>
          <div class="result-header">
            <span>解析结果</span>
            <el-tag :type="parseResult.valid ? 'success' : 'danger'">
              {{ parseResult.valid ? '校验通过' : '校验失败' }}
            </el-tag>
          </div>
        </template>

        <template v-if="parseResult.valid">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="类型">
              {{ parseResult.result.intent === 'aggregate' ? '统计表' : '明细表（新增字段）' }}
            </el-descriptions-item>
            <el-descriptions-item label="来源表">{{ parseResult.result.source_table }}</el-descriptions-item>
            <el-descriptions-item v-if="parseResult.result.dimensions.length" label="分组维度">
              {{ parseResult.result.dimensions.join('、') }}
            </el-descriptions-item>
            <el-descriptions-item v-if="parseResult.result.measures.length" label="聚合度量">
              {{ parseResult.result.measures.map(m => `${m.agg}(${m.field})`).join('、') }}
            </el-descriptions-item>
            <el-descriptions-item v-if="parseResult.result.filters.length" label="筛选条件">
              {{ parseResult.result.filters.map(f => `${f.field} ${f.op} ${f.value}`).join('；') }}
            </el-descriptions-item>
            <el-descriptions-item v-if="parseResult.result.new_columns.length" label="新增字段">
              {{ parseResult.result.new_columns.map(c => `${c.name} = ${c.expression}`).join('；') }}
            </el-descriptions-item>
          </el-descriptions>

          <el-divider content-position="left">SQL 预览</el-divider>
          <pre class="sql">{{ parseResult.sql_preview }}</pre>

          <el-button
            type="success"
            size="large"
            :disabled="confirmed"
            :loading="jobRunning"
            @click="doRunJob"
          >
            {{ jobButton }}
          </el-button>
          <el-button v-if="jobDone" size="large" @click="$router.push('/results')">查看结果中心</el-button>
        </template>

        <template v-else>
          <el-alert type="error" :closable="false" title="解析结果未通过校验，请修改描述或联系管理员检查元数据">
            <div v-for="e in parseResult.errors" :key="e">- {{ e }}</div>
          </el-alert>
        </template>
      </el-card>
    </el-main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../api/request'
import { useUserStore } from '../stores/user'

const router = useRouter()
const user = useUserStore()

const examples = [
  '按区域统计销售额，只看2024年',
  '给明细表增加一列：销售金额乘以2',
  '统计每个区域的订单数量',
]

const datasources = ref([])
const allTables = ref([])
const selectedTable = ref(null)
const question = ref('')
const parsing = ref(false)
const parseResult = ref(null)
const confirmed = ref(false)
const jobRunning = ref(false)
const jobDone = ref(false)

const jobButton = computed(() => {
  if (jobDone.value) return '生成完成 ✓'
  if (jobRunning.value) return '正在生成…'
  if (confirmed.value) return '生成统计表'
  return '确认无误并生成统计表'
})

onMounted(loadDatasources)

async function loadDatasources() {
  datasources.value = await request.get('/datasources')
  const lists = await Promise.all(
    datasources.value.map((d) => request.get(`/datasources/${d.id}/tables`))
  )
  allTables.value = lists.flatMap((tables, i) =>
    tables.map((t) => ({ ...t, ds_name: datasources.value[i].name }))
  )
}

async function doParse() {
  if (!selectedTable.value) {
    ElMessage.warning('请先选择数据表')
    return
  }
  if (!question.value.trim()) {
    ElMessage.warning('请输入需求描述')
    return
  }
  parsing.value = true
  parseResult.value = null
  confirmed.value = false
  jobRunning.value = false
  jobDone.value = false
  try {
    parseResult.value = await request.post('/nl/parse', {
      table_id: selectedTable.value,
      question: question.value.trim(),
    })
  } finally {
    parsing.value = false
  }
}

async function doConfirm() {
  await request.post('/nl/confirm', { parse_id: parseResult.value.parse_id })
  confirmed.value = true
}

async function doRunJob() {
  // 未确认则先确认，再提交任务
  if (!confirmed.value) {
    await doConfirm()
  }
  jobRunning.value = true
  try {
    const job = await request.post('/jobs', { parse_id: parseResult.value.parse_id })
    // eager 模式同步完成；非 eager 轮询状态
    let status = job.status
    let jobId = job.job_id
    while (status === 'pending' || status === 'running') {
      await new Promise((r) => setTimeout(r, 1000))
      const detail = await request.get(`/jobs/${jobId}`)
      status = detail.status
      if (detail.status === 'failed') {
        ElMessage.error(`任务失败：${detail.error_msg}`)
        return
      }
    }
    if (status === 'success') {
      jobDone.value = true
      ElMessage.success('统计表生成成功')
    }
  } finally {
    jobRunning.value = false
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
.chat-input {
  display: flex;
  gap: 12px;
}
.examples {
  margin-top: 10px;
  color: #909399;
  font-size: 13px;
}
.ex-tag {
  cursor: pointer;
  margin-left: 6px;
}
.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.sql {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 14px;
  border-radius: 6px;
  font-family: Consolas, monospace;
  font-size: 13px;
  overflow-x: auto;
  margin-bottom: 16px;
}
</style>
