import { createRouter, createWebHistory } from '@ionic/vue-router';
import type { RouteRecordRaw } from 'vue-router';
import TabsPage from '../views/TabsPage.vue';
import LoginPage from '../views/LoginPage.vue'

const routes: RouteRecordRaw[] = [
    {
	path: '/',
	redirect: '/login',
    },
    {
	path: '/login',
	component: LoginPage,
    },
    {
	path: '/login/driver-options',
	component: () => import('@/views/DriverPage.vue'),
    },
    {
	path: '/tabs/',
	component: TabsPage,
	children: [
	    {
		path: '',
		redirect: '/tabs/map',
	    },
	    {
		path: 'map',
		component: () => import('@/views/Tab1Page.vue'),
	    },
	    {
		path: 'tab2',
		name: 'horarios',
		component: () => import('@/views/Tab2Page.vue'),
	    },
	],
    },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;
