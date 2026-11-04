import { useEffect, useState } from "react";
import { api } from "./api";

export default function App() {
  const [estadoApi, setEstadoApi] = useState("consultando...");

  useEffect(() => {
    api
      .get("/salud")
      .then((r) => setEstadoApi(r.data.estado))
      .catch(() => setEstadoApi("sin conexión"));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: 24 }}>
      <h1>Marketplace de Alojamientos · Inversiones LR</h1>
      <p>Estado de la API: {estadoApi}</p>
    </main>
  );
}
