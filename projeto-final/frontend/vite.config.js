import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O painel fala sempre com `/api`, nunca com um endereço absoluto. Em
// desenvolvimento é o balanceador (porta 8000) que está do outro lado, tal
// como no contentor e na nuvem: o painel nunca escolhe um nó.
export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_BALANCEADOR_URL || "http://localhost:8000",
        changeOrigin: true,
        rewrite: (caminho) => caminho.replace(/^\/api/, ""),
      },
    },
  },
  plugins: [react()],
});
