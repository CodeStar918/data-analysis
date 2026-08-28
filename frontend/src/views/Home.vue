<template>
  <el-container class="home">
    <el-header class="header">
      <span class="brand">报表生成平台</span>
      <div class="right">
        <el-button type="primary" @click="$router.push('/workspace')">进入工作台</el-button>
        <el-button text @click="$router.push('/datasources')">数据源管理</el-button>
        <span class="user">{{ user.username }}</span>
        <el-button link type="danger" @click="handleLogout">退出登录</el-button>
      </div>
    </el-header>
    <el-main>
      <el-empty description="用一句话，从数据生成报表（阶段 5 开放任务执行与结果导出）" />
    </el-main>
  </el-container>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'

const router = useRouter()
const user = useUserStore()

function handleLogout() {
  user.logout()
  router.push('/login')
}
</script>

<style scoped>
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
}
.right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user {
  color: #606266;
}
</style>
