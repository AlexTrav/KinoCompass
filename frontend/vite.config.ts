/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Vue и Tailwind CSS 4 – плагинами Vite, тесты – Vitest
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    host: true,
    // dev-сервер работает в Docker с примонтированной папкой Windows – изменения файлов видны только опросом
    watch: { usePolling: process.env.VITE_USE_POLLING === '1' },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
