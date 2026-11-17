import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { port: 5173 },
  // Un solo archivo JS: jsPDF trae importaciones dinámicas opcionales que no usamos
  build: { rollupOptions: { output: { inlineDynamicImports: true } }, chunkSizeWarningLimit: 2500 },
});
