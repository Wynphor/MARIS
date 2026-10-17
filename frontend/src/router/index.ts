import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('../pages/Dashboard.vue') },
  { path: '/workspace', name: 'Workspace', component: () => import('../pages/Workspace.vue') },
  { path: '/pipeline', name: 'Pipeline', component: () => import('../pages/Pipeline.vue') },
  { path: '/editor', name: 'Editor', component: () => import('../pages/Editor.vue') },
  { path: '/chat', name: 'Chat', component: () => import('../pages/Chat.vue') },
  { path: '/data', name: 'Data', component: () => import('../pages/DataExplorer.vue') },
  { path: '/settings', name: 'Settings', component: () => import('../pages/Settings.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
