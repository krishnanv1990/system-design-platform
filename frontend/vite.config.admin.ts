import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Admin app build configuration
export default defineConfig({
  plugins: [react()],
  base: '/',
  define: {
    // Mark this as admin build for OAuth redirect handling
    'import.meta.env.VITE_IS_ADMIN': JSON.stringify('true'),
  },
  build: {
    sourcemap: true,
    outDir: 'dist-admin',
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'admin.html'),
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5174,
    host: true,
  },
})
