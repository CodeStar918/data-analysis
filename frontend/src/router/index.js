import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/datasources',
    name: 'Datasources',
    component: () => import('../views/Datasources.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/metadata',
    name: 'Metadata',
    component: () => import('../views/Metadata.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('../views/Workspace.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/results',
    name: 'Results',
    component: () => import('../views/Results.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/approvals',
    name: 'Approvals',
    component: () => import('../views/Approvals.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const user = useUserStore()
  if (to.meta.requiresAuth && !user.token) {
    return { name: 'Login' }
  }
  if (to.meta.requiresAdmin && !['admin', 'dept_admin'].includes(user.role)) {
    return { name: 'Home' }
  }
})

export default router
