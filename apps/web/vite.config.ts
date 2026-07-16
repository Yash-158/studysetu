import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// Dev proxy: /api + /config.json -> FastAPI on :8000
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000', '/config.json': 'http://localhost:8000', '/healthz': 'http://localhost:8000' } },
})
