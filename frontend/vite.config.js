import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiTarget = process.env.API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
      '/media': { target: apiTarget, changeOrigin: true },
    },
  },
})
