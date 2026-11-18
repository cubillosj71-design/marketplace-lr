import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, Vite reenvía /api/* a Django. Así el navegador ve un solo origen
// (http://localhost:5173), igual que en Render con la regla de reescritura del
// sitio estático (diagrama de despliegue). Un solo origen es lo que permite usar
// la cookie de renovación con SameSite=Strict sin configurar CORS con credenciales.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: process.env.VITE_PROXY_API ?? "http://localhost:8000", changeOrigin: false },
    },
  },
});
