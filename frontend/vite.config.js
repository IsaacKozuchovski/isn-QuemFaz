import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Na AWS, o CloudFront manda /api/* para o API Gateway e o resto para o S3.
// Localmente, o Vite faz o mesmo papel: repassa /api/* para o `sam local`
// (porta 3000), tirando o prefixo, já que lá as rotas não têm /api.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.API_URL || "http://127.0.0.1:3000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
