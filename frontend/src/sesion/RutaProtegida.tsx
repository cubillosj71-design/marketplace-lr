import { Navigate, Outlet, useLocation } from "react-router-dom";
import type { Rol } from "../identidad/api";
import { useSesion } from "./SesionContext";

/**
 * Protege un grupo de rutas por rol (RF-D-USU-02.1, HU-05).
 *
 * Es una ayuda de usabilidad, no la seguridad: esconder una pantalla no impide
 * llamar a la API. Quien decide de verdad es el back-end (permisos de DRF),
 * que responde 401 o 403 aunque alguien escriba la dirección a mano.
 */
export function RutaProtegida({ roles }: { roles?: Rol[] }) {
  const { usuario, cargando } = useSesion();
  const ubicacion = useLocation();

  if (cargando) return <p className="cargando">Cargando…</p>;
  if (!usuario) {
    // CA-05.1: sin sesión, se pide iniciarla y luego se vuelve a donde iba.
    return <Navigate to="/iniciar-sesion" replace state={{ desde: ubicacion.pathname }} />;
  }
  if (roles && !roles.includes(usuario.rol)) return <Navigate to="/sin-permiso" replace />;
  return <Outlet />;
}

/** Para pantallas que solo tienen sentido sin sesión (registro, inicio de sesión). */
export function SoloVisitante() {
  const { usuario, cargando } = useSesion();
  if (cargando) return <p className="cargando">Cargando…</p>;
  return usuario ? <Navigate to="/" replace /> : <Outlet />;
}
