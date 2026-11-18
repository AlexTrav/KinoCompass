import { createRouter, createWebHistory } from 'vue-router'
import PickView from '../views/PickView.vue'

// главная грузится сразу, остальные страницы – отдельными кусками при первом переходе
export const ROUTES = [
  { path: '/', name: 'pick', component: PickView },
  { path: '/film/:id(\\d+)', name: 'film', component: () => import('../views/FilmView.vue'), props: true },
  { path: '/compare', name: 'compare', component: () => import('../views/CompareView.vue') },
  { path: '/map', name: 'map', component: () => import('../views/MapView.vue') },
  { path: '/research', name: 'research', component: () => import('../views/ResearchView.vue') },
  { path: '/perf', name: 'perf', component: () => import('../views/PerfView.vue') },
  { path: '/about', name: 'about', component: () => import('../views/AboutView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export default createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: ROUTES,
  scrollBehavior: (to, _from, saved) => saved ?? (to.hash ? { el: to.hash } : { top: 0 }),
})
