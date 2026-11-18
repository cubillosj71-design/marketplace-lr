import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Aviso, Campo } from "../componentes/Campo";
import { leerError, type ErrorApi } from "../errores";
import { identidad } from "../identidad/api";

/**
 * HU-03 Recuperar la contraseña, paso 1 (CU-USU-03).
 * La recuperación es simulada (AMB-08): el enlace se muestra aquí en lugar de
 * enviarse por correo.
 */
export function RecuperarContrasena() {
  const [correo, setCorreo] = useState("");
  const [enlace, setEnlace] = useState<string | null>(null);
  const [error, setError] = useState<ErrorApi | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setEnlace(null);
    setEnviando(true);
    try {
      const { data } = await identidad.solicitarRecuperacion(correo);
      setEnlace(data.enlace);
    } catch (e) {
      setError(leerError(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="tarjeta">
      <h1>Recupera tu contraseña</h1>
      <p>Escribe el correo con el que te registraste y te daremos un enlace para definir una contraseña nueva.</p>
      {error && <Aviso tipo="error">{error.mensaje}</Aviso>}
      {enlace && (
        <Aviso tipo="exito">
          <p>Este es tu enlace. Sirve una sola vez y vence en 20 minutos.</p>
          <p>
            <Link to={enlace} className="enlace-recuperacion">
              Definir mi nueva contraseña
            </Link>
          </p>
          <small>En la versión final este enlace llegaría a tu correo; en el MVP se muestra aquí.</small>
        </Aviso>
      )}
      <form onSubmit={enviar} noValidate>
        <Campo
          etiqueta="Correo electrónico"
          type="email"
          autoComplete="email"
          required
          value={correo}
          onChange={(e) => setCorreo(e.target.value)}
          error={error?.campos.correo}
        />
        <button type="submit" className="boton" disabled={enviando}>
          {enviando ? "Generando el enlace…" : "Obtener enlace"}
        </button>
      </form>
      <p className="pie-tarjeta">
        <Link to="/iniciar-sesion">Volver a iniciar sesión</Link>
      </p>
    </section>
  );
}
