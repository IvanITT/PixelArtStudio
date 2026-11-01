import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The app is served from FastAPI on 127.0.0.1:8765 in production and from Vite
// on 127.0.0.1:5173 during development. Both proxy to the local API only.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8765",
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
  },
});
