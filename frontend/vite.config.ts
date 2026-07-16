import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // 部署基础路径：默认为 /，如有 CDN 或子路径可设环境变量 VITE_BASE
  base: process.env.VITE_BASE || '/',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    // 生产构建时注入 API 基础路径（通过 import.meta.env.VITE_API_BASE）
    // 前端代码中使用相对路径 /api/v1，Nginx 反向代理处理路由
    outDir: 'dist',
    sourcemap: false,
  },
})
