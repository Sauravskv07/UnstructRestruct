import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/documents": "http://127.0.0.1:8000",
      "/patients": "http://127.0.0.1:8000",
      "/query": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
      "/me": "http://127.0.0.1:8000",
      "/clinician": "http://127.0.0.1:8000",
    },
  },
});
