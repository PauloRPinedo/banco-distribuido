import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El frontend habla siempre con el balanceador (nunca con un nodo directo)
// — ver docs/entregables/03-arquitectura/diagrama-de-componentes.md.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_BALANCEADOR_URL || "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
