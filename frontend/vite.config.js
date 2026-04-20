import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  base: './', // Ensures assets are loaded correctly on Android
  server: {
    host: true, // Listen on all addresses
    port: 5173,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  }
})
