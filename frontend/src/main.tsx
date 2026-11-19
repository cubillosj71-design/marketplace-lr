import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter, MemoryRouter } from "react-router-dom";
import App from "./App";
import { LimiteDeError } from "./LimiteDeError";
import { StoreProvider, ToastProvider } from "./store";
import "./styles.css";

// HashRouter: la aplicación se sirve como sitio estático, sin reglas de reescritura para cada ruta.
// En la vista publicada (VITE_ROUTER=memory) las rutas viven en memoria.
// Las versiones anteriores guardaban datos de ejemplo en el navegador; ya no se usan y se borran.
try { localStorage.removeItem("alojamientos-lr-prototipo-v4"); } catch { /* sin almacenamiento */ }

const Router = import.meta.env.VITE_ROUTER === "memory" ? MemoryRouter : HashRouter;
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Router>
      <StoreProvider>
        <ToastProvider>
          <LimiteDeError completo>
            <App />
          </LimiteDeError>
        </ToastProvider>
      </StoreProvider>
    </Router>
  </React.StrictMode>,
);
