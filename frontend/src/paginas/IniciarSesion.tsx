import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Aviso, Campo } from "../componentes/Campo";
import { leerError, type ErrorApi } from "../errores";
import { useSesion } from "../sesion/SesionContext";

interface EstadoNavegacion {
  desde?: string;
  registrado?: string;
  contrasenaCambiada?: boolean;
  desactivada?: boolean;
}

/** HU-02 Iniciar sesión (CU-USU-02), con el punto de extensión "Olvidó contraseña". */
export function IniciarSesion() {
  const { iniciarSesion } = useSesion();
  const navegar = useNavigate();
  const estado = (useLocation().state ?? {}) as EstadoNavegacion;
  const [correo, setCorreo] = useState(estado.registrado ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ErrorApi | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await iniciarSesion(correo, password);
      navegar(estado.desde ?? "/", { replace: true });
    } catch (e) {
      setError(leerError(e));
      setPassword("");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="tarjeta">
      <h1>Inicia sesión</h1>
      {estado.registrado && <Aviso tipo="exito">Tu cuenta quedó creada. Ya puedes iniciar sesión.</Aviso>}
      {estado.contrasenaCambiada && <Aviso tipo="exito">Tu contraseña quedó actualizada.</Aviso>}
      {estado.desactivada && <Aviso tipo="info">Tu cuenta quedó desactivada. Inicia sesión cuando quieras reactivarla.</Aviso>}
      {estado.desde && !error && <Aviso tipo="info">Inicia sesión para continuar.</Aviso>}
      {error && <Aviso tipo="error">{error.mensaje}</Aviso>}
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
        <Campo
          etiqueta="Contraseña"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={error?.campos.password}
        />
        <p className="derecha">
          <Link to="/recuperar">¿Olvidaste tu contraseña?</Link>
        </p>
        <button type="submit" className="boton" disabled={enviando}>
          {enviando ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
      <p className="pie-tarjeta">
        ¿No tienes cuenta? <Link to="/registro">Regístrate</Link>
      </p>
    </section>
  );
}
