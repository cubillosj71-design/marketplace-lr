import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter, MemoryRouter } from "react-router-dom";
import App from "./App";
import { StoreProvider, ToastProvider } from "./store";
import "./styles.css";

// HashRouter: el prototipo funciona como página estática, sin configurar el servidor.
// En la vista publicada (VITE_ROUTER=memory) las rutas viven en memoria.
const Router = import.meta.env.VITE_ROUTER === "memory" ? MemoryRouter : HashRouter;
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Router>
      <StoreProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </StoreProvider>
    </Router>
  </React.StrictMode>,
);
