import { Link } from "react-router-dom";
import { NOMBRE_ROL } from "../identidad/api";
import { useSesion } from "../sesion/SesionContext";

/**
 * Página de inicio. Las secciones de cada rol (búsqueda, publicaciones,
 * moderación) las agregan los demás módulos en sus propias rutas.
 */
export function Inicio() {
  const { usuario } = useSesion();

  if (!usuario) {
    return (
      <section className="portada">
        <h1>Encuentra dónde quedarte</h1>
        <p>Busca alojamientos, conoce el precio total antes de pagar y reserva al instante.</p>
        <div className="acciones">
          <Link to="/registro" className="boton">
            Crear una cuenta
          </Link>
          <Link to="/iniciar-sesion" className="boton boton-secundario">
            Ya tengo cuenta
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="tarjeta">
      <h1>Hola, {usuario.nombre_completo.split(" ")[0]}</h1>
      <p>Iniciaste sesión como {NOMBRE_ROL[usuario.rol]}.</p>
    </section>
  );
}

export function SinPermiso() {
  return (
    <section className="tarjeta">
      <h1>No tienes acceso a esta sección</h1>
      <p>Esta función no corresponde a tu rol en la plataforma.</p>
      <Link to="/" className="boton">
        Ir al inicio
      </Link>
    </section>
  );
}

export function NoEncontrada() {
  return (
    <section className="tarjeta">
      <h1>Página no encontrada</h1>
      <Link to="/" className="boton">
        Ir al inicio
      </Link>
    </section>
  );
}
