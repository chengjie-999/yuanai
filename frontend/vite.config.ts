import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // 部署基础路径：默认为 /，如有 CDN 或子路径可设环境变量 VITE_BASE
  base: process.env.VITE_BASE || '/',
  server: {
    port: 5173,
    proxy: {
      // 只代理 API 前缀——'/api' 会吞掉 SPA 路由 /api-docs（刷新时导航请求
      // 被转发到后端 → 401 {"detail":"未提供 token"}，2026-11-15 修复）
      '/api/v1': {
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
