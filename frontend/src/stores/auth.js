import { reactive } from 'vue'
import { fetchMe, login as apiLogin, logout as apiLogout, setToken } from '../api'

export const authState = reactive({
  user: null,
  initialized: false,
})

export async function restoreAuth() {
  if (authState.initialized) return
  try {
    authState.user = await fetchMe()
  } catch {
    setToken('')
    authState.user = null
  } finally {
    authState.initialized = true
  }
}

export async function login(username, password) {
  const result = await apiLogin(username, password)
  setToken(result.token)
  authState.user = result.user
  authState.initialized = true
  return result.user
}

export async function logout() {
  try {
    await apiLogout()
  } finally {
    setToken('')
    authState.user = null
    authState.initialized = true
  }
}

export function hasPermission(permission) {
  return Boolean(authState.user?.permissions?.includes(permission))
}

export function isStaff() {
  return Boolean(authState.user?.role)
}
