import { createRouter, createWebHistory } from "vue-router";
import { authState, restoreAuth } from "./stores/auth";
import PublicLayout from "./layouts/PublicLayout.vue";
import AdminLayout from "./layouts/AdminLayout.vue";
import PublicMapPage from "./pages/PublicMapPage.vue";
import PublicDirectoryPage from "./pages/PublicDirectoryPage.vue";
import PublicInsightsPage from "./pages/PublicInsightsPage.vue";
import PublicCrossingDetailPage from "./pages/PublicCrossingDetailPage.vue";
import AdminLoginPage from "./pages/AdminLoginPage.vue";
import AdminDashboardPage from "./pages/AdminDashboardPage.vue";
import AdminCrossingsPage from "./pages/AdminCrossingsPage.vue";
import AdminSchedulesPage from "./pages/AdminSchedulesPage.vue";
import AdminIncidentsPage from "./pages/AdminIncidentsPage.vue";
import AdminArticlesPage from "./pages/AdminArticlesPage.vue";
import AdminUsersPage from "./pages/AdminUsersPage.vue";

const router = createRouter({
	history: createWebHistory(),
	routes: [
		{
			path: "/",
			component: PublicLayout,
			children: [
				{ path: "", name: "public-map", component: PublicMapPage },
				{
					path: "scene-3d",
					name: "public-scene-3d",
					component: () => import("./pages/PublicThreeScenePage.vue"),
				},
				{
					path: "directory",
					name: "public-directory",
					component: PublicDirectoryPage,
				},
				{
					path: "insights",
					name: "public-insights",
					component: PublicInsightsPage,
				},
				{
					path: "crossings/:id",
					name: "public-crossing-detail",
					component: PublicCrossingDetailPage,
				},
			],
		},
		{
			path: "/admin/login",
			name: "admin-login",
			component: AdminLoginPage,
			meta: { guestOnly: true },
		},
		{
			path: "/admin",
			component: AdminLayout,
			meta: { requiresStaff: true },
			children: [
				{
					path: "",
					name: "admin-dashboard",
					component: AdminDashboardPage,
				},
				{
					path: "crossings",
					name: "admin-crossings",
					component: AdminCrossingsPage,
				},
				{
					path: "schedules",
					name: "admin-schedules",
					component: AdminSchedulesPage,
				},
				{
					path: "incidents",
					name: "admin-incidents",
					component: AdminIncidentsPage,
				},
				{
					path: "articles",
					name: "admin-articles",
					component: AdminArticlesPage,
				},
				{
					path: "users",
					name: "admin-users",
					component: AdminUsersPage,
				},
			],
		},
	],
});

router.beforeEach(async (to) => {
	await restoreAuth();

	if (to.meta.requiresStaff && !authState.user?.role) {
		return { name: "admin-login", query: { next: to.fullPath } };
	}

	if (to.meta.guestOnly && authState.user?.role) {
		return { name: "admin-dashboard" };
	}

	return true;
});

export default router;
