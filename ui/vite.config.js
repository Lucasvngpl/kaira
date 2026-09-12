import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The patient tablet's URL is typed in by hand, so a silent hop to 5174
    // would quietly point it at nothing. Fail loudly instead.
    strictPort: true,
    proxy: {
      // Vite hands /api straight to the local API, which keeps every request
      // same-origin: no CORS, and no laptop IP written down anywhere. 127.0.0.1
      // is correct here because Vite runs on the machine holding the API - it
      // would be wrong if the tablet called the API itself.
      '/api': {
        target: 'http://127.0.0.1:8300',
        // The API's routes sit at the root (/session/...), not under /api.
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
