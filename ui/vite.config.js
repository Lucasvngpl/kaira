import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The API's CORS allowlist is pinned to 5173; if the port were taken Vite
    // would silently hop to 5174 and every request would fail with an opaque
    // CORS error. Failing loudly here is kinder.
    strictPort: true,
  },
});
