import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    port: 5173,
    // /api/* va a Django: el navegador ve un solo origen, igual que en Render con la
    // regla de reescritura del sitio estático. Eso permite la cookie de sesión SameSite=Strict.
    proxy: { "/api": process.env.VITE_PROXY_API ?? "http://localhost:8000" },
  },
  // Un solo archivo JS: jsPDF trae importaciones dinámicas opcionales que no usamos
  build: { rollupOptions: { output: { inlineDynamicImports: true } }, chunkSizeWarningLimit: 2500 },
});
