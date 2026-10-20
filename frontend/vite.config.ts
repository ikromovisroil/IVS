import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Django (127.0.0.1:8000) shu manzillarni beradi. Proxy Host sarlavhasini o'zgartirmaydi,
// shuning uchun sessiya cookie'si va CSRF tekshiruvi localhost:5173 uchun ishlaydi.
const DJANGO = 'http://127.0.0.1:8000'
const backendPaths = ['/api', '/sso', '/media', '/static', '/ivc_service_admin_panel', '/swagger', '/ws']

export default defineConfig(({ command }) => ({
  plugins: [react()],
  // Productionda: build → ../static/spa/ (Django STATICFILES_DIRS, WhiteNoise), sahifa /app/ ostida (config/spa.py).
  // Dev serverda fayllar ildizdan beriladi, sahifalar baribir /app/... manzilida (router basename).
  base: command === 'build' ? '/static/spa/' : '/',
  build: {
    outDir: '../static/spa',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Kam o'zgaradigan kutubxonalar alohida fayllarda — ilova yangilanganda brauzer keshidan olinadi
        manualChunks(id) {
          if (id.includes('/src/ds/')) return 'alignui'
          if (/node_modules\/(react|react-dom|scheduler|react-router|@tanstack)\//.test(id)) return 'vendor'
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(backendPaths.map((p) => [p, { target: DJANGO, ws: p === '/ws' }])),
  },
}))
