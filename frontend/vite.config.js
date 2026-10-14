import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // listen on 0.0.0.0 -- required so Docker's port mapping can reach it
    port: 3000,
    strictPort: true,
    watch: {
      usePolling: true, // needed for reliable hot-reload through a Docker bind mount
    },
  },
})
