import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI backend (uvicorn motif.api:app) runs on :8000; the dev server proxies /api to it.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
  test: { environment: "jsdom", globals: true },
});
