import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { NOMBRE_ROL } from "../identidad/api";
import { useSesion } from "../sesion/SesionContext";

/** Encabezado con la navegación de cada rol y el contenido de la página. */
export function Plantilla() {
  const { usuario, cerrarSesion } = useSesion();
  const navegar = useNavigate();

  async function salir() {
    await cerrarSesion();
    navegar("/iniciar-sesion");
  }

  return (
    <>
      <header className="encabezado">
        <Link to="/" className="marca">
          Alojamientos LR
        </Link>
        <nav aria-label="Principal">
          {usuario ? (
            <>
              <span className="saludo">
                {usuario.nombre_completo.split(" ")[0]} · {NOMBRE_ROL[usuario.rol]}
              </span>
              {usuario.rol !== "ADMINISTRADOR" && <NavLink to="/perfil">Mi perfil</NavLink>}
              <button type="button" className="boton-enlace" onClick={salir}>
                Cerrar sesión
              </button>
            </>
          ) : (
            <>
              <NavLink to="/iniciar-sesion">Iniciar sesión</NavLink>
              <NavLink to="/registro" className="boton boton-pequeno">
                Registrarse
              </NavLink>
            </>
          )}
        </nav>
      </header>
      <main className="contenido">
        <Outlet />
      </main>
    </>
  );
}
