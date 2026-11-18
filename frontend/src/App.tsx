import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Plantilla } from "./componentes/Plantilla";
import { IniciarSesion } from "./paginas/IniciarSesion";
import { Inicio, NoEncontrada, SinPermiso } from "./paginas/Inicio";
import { NuevaContrasena } from "./paginas/NuevaContrasena";
import { Perfil } from "./paginas/Perfil";
import { RecuperarContrasena } from "./paginas/RecuperarContrasena";
import { Registro } from "./paginas/Registro";
import { ProveedorSesion } from "./sesion/SesionContext";
import { RutaProtegida, SoloVisitante } from "./sesion/RutaProtegida";

/**
 * Rutas de la aplicación. Cada módulo agrega las suyas dentro del grupo de su
 * rol, por ejemplo:
 *   <Route element={<RutaProtegida roles={["ANFITRION"]} />}>
 *     <Route path="/mis-publicaciones" element={<MisPublicaciones />} />
 *   </Route>
 */
export default function App() {
  return (
    <BrowserRouter>
      <ProveedorSesion>
        <Routes>
          <Route element={<Plantilla />}>
            <Route path="/" element={<Inicio />} />

            {/* Solo sin sesión */}
            <Route element={<SoloVisitante />}>
              <Route path="/registro" element={<Registro />} />
              <Route path="/iniciar-sesion" element={<IniciarSesion />} />
            </Route>

            {/* Recuperación: sin sesión, pero no se redirige si hay una abierta */}
            <Route path="/recuperar" element={<RecuperarContrasena />} />
            <Route path="/recuperar/:token" element={<NuevaContrasena />} />

            {/* Huésped y Anfitrión (matriz de permisos, sección 2) */}
            <Route element={<RutaProtegida roles={["HUESPED", "ANFITRION"]} />}>
              <Route path="/perfil" element={<Perfil />} />
            </Route>

            <Route path="/sin-permiso" element={<SinPermiso />} />
            <Route path="*" element={<NoEncontrada />} />
          </Route>
        </Routes>
      </ProveedorSesion>
    </BrowserRouter>
  );
}
