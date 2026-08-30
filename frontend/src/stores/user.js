import {defineStore} from 'pinia'
import request from '../api/request'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    username: localStorage.getItem('username') || '',
    role: localStorage.getItem('role') || '',
  }),
  actions: {
    async login(username, password) {
      const data = await request.post('/auth/login', { username, password })
      this.token = data.access_token
      this.username = data.username
      this.role = data.role
      localStorage.setItem('token', this.token)
      localStorage.setItem('username', this.username)
      localStorage.setItem('role', this.role)
    },
    logout() {
      this.token = ''
      this.username = ''
      this.role = ''
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      localStorage.removeItem('role')
    },
  },
})
