import { reactive } from "vue";
import { fetchAdminOverview } from "../api";

export const adminState = reactive({
	overview: {
		crossings: [],
		schedules: [],
		incidents: [],
		articles: [],
		users: [],
		qualityAlerts: [],
		auditLogs: [],
		permissionMatrix: {},
		user: null,
	},
	loading: false,
	error: "",
});

export async function loadAdminOverview() {
	adminState.loading = true;
	adminState.error = "";
	try {
		const payload = await fetchAdminOverview();
		adminState.overview = {
			crossings: [],
			schedules: [],
			incidents: [],
			articles: [],
			users: [],
			qualityAlerts: [],
			auditLogs: [],
			permissionMatrix: {},
			user: null,
			...(payload || {}),
		};
	} catch (error) {
		adminState.error = error.message;
	} finally {
		adminState.loading = false;
	}
}
