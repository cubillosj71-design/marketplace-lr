import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout, ConPermiso } from "./layout";
import { AdminPublicaciones, RegistroAcciones, RevisarPublicacion, Tablero, TarifaServicioPage, UsuariosAdmin } from "./pages/admin";
import { Inicio, Login, Recuperar, Registro, Restablecer } from "./pages/auth";
import { Calendario } from "./pages/calendario";
import { Explorar, ExplorarDetalle, ExplorarPublico, ExplorarPublicoDetalle } from "./pages/explorar";
import { DetallePublicacion, FormPublicacionRuta, MisPublicaciones } from "./pages/publicaciones";
import { Reportes } from "./pages/reportes";
import { CotizacionPage } from "./pages/reservar";
import { Avisos, MisReservas, ReservasDeMisAlojamientos, ReservasEnRevision } from "./pages/reservas";
import { CambiarContrasena, Perfil, Roles } from "./pages/usuarios";
import { useStore } from "./store";

/** Cada ruta con sesión declara el permiso que necesita (mismo nombre que en apps/comun/rbac.py). */
const RUTAS: { path: string; permiso: string | string[] | null; el: ReactNode }[] = [
  { path: "/perfil", permiso: "perfil.gestionar", el: <Perfil /> },
  { path: "/perfil/contrasena", permiso: "perfil.gestionar", el: <CambiarContrasena /> },
  { path: "/roles", permiso: null, el: <Roles /> },  // solo muestra la matriz pública (GET /identidad/roles)
  { path: "/avisos", permiso: "notificaciones.ver", el: <Avisos /> },

  { path: "/explorar", permiso: "busqueda.ver", el: <Explorar /> },
  { path: "/explorar/:id", permiso: "busqueda.ver", el: <ExplorarDetalle /> },
  { path: "/cotizacion/:id", permiso: "reservas.cotizar", el: <CotizacionPage /> },
  { path: "/reservas", permiso: "reservas.ver_propias", el: <MisReservas /> },

  { path: "/publicaciones", permiso: "publicaciones.gestionar_propias", el: <MisPublicaciones /> },
  { path: "/publicaciones/nueva", permiso: "publicaciones.gestionar_propias", el: <FormPublicacionRuta /> },
  { path: "/publicaciones/:id", permiso: "publicaciones.gestionar_propias", el: <DetallePublicacion /> },
  // El Administrador modifica cualquier publicación (RF-D-ALO-02.1): misma regla que PATCH en el backend
  { path: "/publicaciones/:id/editar", permiso: ["publicaciones.gestionar_propias", "publicaciones.moderar"], el: <FormPublicacionRuta /> },
  { path: "/calendario", permiso: "calendario.gestionar", el: <Calendario /> },
  { path: "/reservas-alojamientos", permiso: "reservas.ver_de_mis_alojamientos", el: <ReservasDeMisAlojamientos /> },

  { path: "/admin/tablero", permiso: "tablero.ver", el: <Tablero /> },
  { path: "/admin/publicaciones", permiso: "publicaciones.moderar", el: <AdminPublicaciones /> },
  { path: "/admin/revision", permiso: "publicaciones.moderar", el: <AdminPublicaciones soloPendientes key="pend" /> },
  { path: "/admin/revision/:id", permiso: "publicaciones.moderar", el: <RevisarPublicacion /> },
  { path: "/admin/publicaciones/:id", permiso: "publicaciones.moderar", el: <RevisarPublicacion /> },
  { path: "/admin/reservas", permiso: "reservas.resolver", el: <ReservasEnRevision /> },
  { path: "/admin/usuarios", permiso: "usuarios.ver", el: <UsuariosAdmin /> },
  { path: "/admin/tarifa", permiso: "tarifa.configurar", el: <TarifaServicioPage /> },
  { path: "/admin/registro", permiso: "auditoria.consultar", el: <RegistroAcciones /> },
  { path: "/admin/reportes", permiso: "reportes.descargar", el: <Reportes /> },
];

export default function App() {
  const { usuario } = useStore();
  return (
    <Routes>
      {/* Acceso (Visitante) */}
      <Route path="/" element={<Navigate to={usuario ? "/inicio" : "/ingresar"} replace />} />
      <Route path="/ingresar" element={usuario ? <Navigate to="/inicio" replace /> : <Login />} />
      {/* Registrarse y recuperar la contraseña son funciones del Visitante: con sesión iniciada se vuelve al panel */}
      <Route path="/registro" element={usuario ? <Navigate to="/inicio" replace /> : <Registro />} />
      <Route path="/recuperar" element={usuario ? <Navigate to="/inicio" replace /> : <Recuperar />} />
      <Route path="/restablecer/:token" element={usuario ? <Navigate to="/inicio" replace /> : <Restablecer />} />
      <Route path="/inicio" element={<Inicio />} />
      {/* Búsqueda pública: solo sin sesión. Con sesión, cada usuario entra a su inicio (RF-D-USU-02.1). */}
      <Route path="/explorar-publico" element={usuario ? <Navigate to="/inicio" replace /> : <ExplorarPublico />} />
      <Route path="/explorar-publico/:id" element={usuario ? <Navigate to="/inicio" replace /> : <ExplorarPublicoDetalle />} />

      {/* Con sesión: el layout lleva a "Ingresar" si no la hay; cada ruta exige su permiso */}
      <Route element={<AppLayout />}>
        {RUTAS.map((r) => (
          <Route key={r.path} path={r.path} element={r.permiso ? <ConPermiso permiso={r.permiso}>{r.el}</ConPermiso> : r.el} />
        ))}
        <Route path="/admin/reportes/usuarios" element={<Navigate to="/admin/reportes?tipo=usuarios" replace />} />
        <Route path="/admin/reportes/publicaciones" element={<Navigate to="/admin/reportes?tipo=publicaciones" replace />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
