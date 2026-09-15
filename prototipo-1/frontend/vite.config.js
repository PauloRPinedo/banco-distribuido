import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O painel fala sempre com `/api`, nunca com um endereço absoluto. Quem
// reescreve `/api` muda com o sítio onde isto corre — aqui em
// desenvolvimento, o nginx.conf quando está em contentor — e assim o código
// do painel é o mesmo nos dois casos.
export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_BANCO_URL || "http://localhost:8001",
        changeOrigin: true,
        rewrite: (caminho) => caminho.replace(/^\/api/, ""),
      },
    },
  },
  plugins: [react()],
});
