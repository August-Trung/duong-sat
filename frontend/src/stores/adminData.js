import { reactive } from 'vue'
import { fetchAdminOverview } from '../api'

export const adminState = reactive({
  overview: {
    crossings: [],
    schedules: [],
    incidents: [],
    users: [],
    qualityAlerts: [],
    auditLogs: [],
    permissionMatrix: {},
    user: null,
  },
  loading: false,
  error: '',
})

export async function loadAdminOverview() {
  adminState.loading = true
  adminState.error = ''
  try {
    adminState.overview = await fetchAdminOverview()
  } catch (error) {
    adminState.error = error.message
  } finally {
    adminState.loading = false
  }
}
