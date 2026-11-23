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
import { Avisos, DetalleReserva, MisReservas, ReservasDeMisAlojamientos, ReservasEnRevision } from "./pages/reservas";
import { CambiarContrasena, Perfil, Roles } from "./pages/usuarios";
import { useStore } from "./store";

/** Cada ruta con sesión declara el permiso que necesita (mismo nombre que en apps/comun/rbac.py) y su ruta principal
 *  de la API. Sin el permiso, la pantalla "No tienes permiso" hace un GET a esa ruta para que el backend responda 403
 *  y deje el intento en la auditoría con la ruta y el permiso que faltó (CA-05.2). ":id" toma el de la pantalla. */
export const RUTAS: { path: string; permiso: string | string[] | null; api?: string; el: ReactNode }[] = [
  { path: "/perfil", permiso: "perfil.gestionar", api: "/identidad/perfil", el: <Perfil /> },
  { path: "/perfil/contrasena", permiso: "perfil.gestionar", api: "/identidad/perfil", el: <CambiarContrasena /> },
  { path: "/roles", permiso: "usuarios.ver", api: "/identidad/roles", el: <Roles /> },  // solo el Administrador
  { path: "/avisos", permiso: "notificaciones.ver", api: "/notificaciones", el: <Avisos /> },

  { path: "/explorar", permiso: "busqueda.ver", api: "/busqueda/publicaciones", el: <Explorar /> },
  { path: "/explorar/:id", permiso: "busqueda.ver", api: "/busqueda/publicaciones/:id", el: <ExplorarDetalle /> },
  { path: "/cotizacion/:id", permiso: "reservas.cotizar", api: "/reservas/cotizaciones/:id", el: <CotizacionPage /> },
  { path: "/reservas", permiso: "reservas.ver_propias", api: "/reservas/mias", el: <MisReservas /> },
  // El huésped dueño, el anfitrión de la publicación o el Administrador: mismos permisos que GET /reservas/{id}
  { path: "/reservas/:id", permiso: ["reservas.ver_propias", "reservas.ver_de_mis_alojamientos", "reservas.resolver"], api: "/reservas/:id", el: <DetalleReserva /> },

  { path: "/publicaciones", permiso: "publicaciones.gestionar_propias", api: "/catalogo/mis-publicaciones", el: <MisPublicaciones /> },
  { path: "/publicaciones/nueva", permiso: "publicaciones.gestionar_propias", api: "/catalogo/mis-publicaciones", el: <FormPublicacionRuta /> },
  { path: "/publicaciones/:id", permiso: "publicaciones.gestionar_propias", api: "/catalogo/mis-publicaciones", el: <DetallePublicacion /> },
  // El Administrador modifica cualquier publicación (RF-D-ALO-02.1): misma regla que PATCH en el backend
  { path: "/publicaciones/:id/editar", permiso: ["publicaciones.gestionar_propias", "publicaciones.moderar"], api: "/catalogo/publicaciones/:id", el: <FormPublicacionRuta /> },
  { path: "/calendario", permiso: "calendario.gestionar", api: "/catalogo/publicaciones/0/calendario", el: <Calendario /> },
  { path: "/reservas-alojamientos", permiso: "reservas.ver_de_mis_alojamientos", api: "/reservas/de-mis-alojamientos", el: <ReservasDeMisAlojamientos /> },
  // El mismo detalle de /reservas/:id, dentro de la sección del anfitrión (menú y miga de pan)
  { path: "/reservas-alojamientos/:id", permiso: ["reservas.ver_propias", "reservas.ver_de_mis_alojamientos", "reservas.resolver"], api: "/reservas/:id", el: <DetalleReserva /> },

  { path: "/admin/tablero", permiso: "tablero.ver", api: "/admin/tablero", el: <Tablero /> },
  { path: "/admin/publicaciones", permiso: "publicaciones.moderar", api: "/admin/publicaciones", el: <AdminPublicaciones /> },
  { path: "/admin/revision", permiso: "publicaciones.moderar", api: "/admin/publicaciones", el: <AdminPublicaciones soloPendientes key="pend" /> },
  { path: "/admin/revision/:id", permiso: "publicaciones.moderar", api: "/admin/publicaciones", el: <RevisarPublicacion /> },
  { path: "/admin/publicaciones/:id", permiso: "publicaciones.moderar", api: "/admin/publicaciones", el: <RevisarPublicacion /> },
  { path: "/admin/reservas", permiso: "reservas.resolver", api: "/admin/reservas", el: <ReservasEnRevision /> },
  { path: "/admin/usuarios", permiso: "usuarios.ver", api: "/admin/usuarios", el: <UsuariosAdmin /> },
  { path: "/admin/tarifa", permiso: "tarifa.configurar", api: "/admin/tarifa-servicio", el: <TarifaServicioPage /> },
  { path: "/admin/registro", permiso: "auditoria.consultar", api: "/admin/auditoria", el: <RegistroAcciones /> },
  { path: "/admin/reportes", permiso: "reportes.descargar", api: "/admin/reportes/usuarios", el: <Reportes /> },
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
          <Route key={r.path} path={r.path} element={r.permiso ? <ConPermiso permiso={r.permiso} api={r.api}>{r.el}</ConPermiso> : r.el} />
        ))}
        <Route path="/admin/reportes/usuarios" element={<Navigate to="/admin/reportes?tipo=usuarios" replace />} />
        <Route path="/admin/reportes/publicaciones" element={<Navigate to="/admin/reportes?tipo=publicaciones" replace />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
