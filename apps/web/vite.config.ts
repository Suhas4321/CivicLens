import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      // Repository-level policy configuration, shared with the API. The category
      // table, its Kannada labels and its SLA days are defined once, in
      // config/categories/, and read by both sides. Importing it here rather than
      // restating it in TypeScript means the two cannot drift, and a moved or
      // renamed config file fails the build instead of silently going stale.
      "@config": path.resolve(__dirname, "../../config"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
  },
});
