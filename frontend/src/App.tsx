import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout, SoloRol } from "./layout";
import { AdminPublicaciones, RegistroAcciones, RevisarPublicacion, TarifaServicioPage } from "./pages/admin";
import { Inicio, Login, Recuperar, Registro, Restablecer } from "./pages/auth";
import { Calendario } from "./pages/calendario";
import { Explorar, ExplorarDetalle, ExplorarPublico, ExplorarPublicoDetalle } from "./pages/explorar";
import { DetallePublicacion, FormPublicacionRuta, MisPublicaciones } from "./pages/publicaciones";
import { ReportePublicaciones, ReporteUsuarios } from "./pages/reportes";
import { CotizacionPage } from "./pages/reservar";
import { Avisos, MisReservas, ReservasDeMisAlojamientos, ReservasEnRevision } from "./pages/reservas";
import { CambiarContrasena, Perfil, Roles } from "./pages/usuarios";
import { useStore } from "./store";

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
      <Route path="/explorar-publico" element={<ExplorarPublico />} />
      <Route path="/explorar-publico/:id" element={<ExplorarPublicoDetalle />} />

      {/* Con sesión */}
      <Route element={<AppLayout />}>
        <Route path="/perfil" element={<Perfil />} />
        <Route path="/perfil/contrasena" element={<CambiarContrasena />} />
        <Route path="/roles" element={<Roles />} />

        <Route path="/explorar" element={<SoloRol roles={["HUESPED"]}><Explorar /></SoloRol>} />
        <Route path="/explorar/:id" element={<SoloRol roles={["HUESPED"]}><ExplorarDetalle /></SoloRol>} />
        <Route path="/cotizacion/:id" element={<SoloRol roles={["HUESPED"]}><CotizacionPage /></SoloRol>} />
        <Route path="/reservas" element={<SoloRol roles={["HUESPED"]}><MisReservas /></SoloRol>} />
        <Route path="/reservas-alojamientos" element={<SoloRol roles={["ANFITRION"]}><ReservasDeMisAlojamientos /></SoloRol>} />
        <Route path="/admin/reservas" element={<SoloRol roles={["ADMINISTRADOR"]}><ReservasEnRevision /></SoloRol>} />
        <Route path="/avisos" element={<Avisos />} />

        <Route path="/publicaciones" element={<SoloRol roles={["ANFITRION"]}><MisPublicaciones /></SoloRol>} />
        <Route path="/publicaciones/nueva" element={<SoloRol roles={["ANFITRION"]}><FormPublicacionRuta /></SoloRol>} />
        <Route path="/publicaciones/:id" element={<SoloRol roles={["ANFITRION", "ADMINISTRADOR"]}><DetallePublicacion /></SoloRol>} />
        <Route path="/publicaciones/:id/editar" element={<SoloRol roles={["ANFITRION", "ADMINISTRADOR"]}><FormPublicacionRuta /></SoloRol>} />
        <Route path="/calendario" element={<SoloRol roles={["ANFITRION"]}><Calendario /></SoloRol>} />

        <Route path="/admin/publicaciones" element={<SoloRol roles={["ADMINISTRADOR"]}><AdminPublicaciones /></SoloRol>} />
        <Route path="/admin/revision" element={<SoloRol roles={["ADMINISTRADOR"]}><AdminPublicaciones soloPendientes key="pend" /></SoloRol>} />
        <Route path="/admin/revision/:id" element={<SoloRol roles={["ADMINISTRADOR"]}><RevisarPublicacion /></SoloRol>} />
        <Route path="/admin/reportes/usuarios" element={<SoloRol roles={["ADMINISTRADOR"]}><ReporteUsuarios /></SoloRol>} />
        <Route path="/admin/reportes/publicaciones" element={<SoloRol roles={["ADMINISTRADOR"]}><ReportePublicaciones /></SoloRol>} />
        <Route path="/admin/tarifa" element={<SoloRol roles={["ADMINISTRADOR"]}><TarifaServicioPage /></SoloRol>} />
        <Route path="/admin/registro" element={<SoloRol roles={["ADMINISTRADOR"]}><RegistroAcciones /></SoloRol>} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
