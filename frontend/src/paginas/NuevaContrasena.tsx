import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Aviso, Campo } from "../componentes/Campo";
import { leerError, type ErrorApi } from "../errores";
import { identidad } from "../identidad/api";

/** HU-03 Recuperar la contraseña, paso 2: abrir el enlace y definir la nueva (CA-03.2, CA-03.3). */
export function NuevaContrasena() {
  const { token = "" } = useParams();
  const navegar = useNavigate();
  const [estadoEnlace, setEstadoEnlace] = useState<"verificando" | "valido" | ErrorApi>("verificando");
  const [password, setPassword] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [error, setError] = useState<ErrorApi | null>(null);
  const [enviando, setEnviando] = useState(false);

  // Se verifica el enlace apenas se abre, para avisar de una vez si venció o ya se usó.
  useEffect(() => {
    let activo = true;
    identidad
      .verificarEnlace(token)
      .then(() => activo && setEstadoEnlace("valido"))
      .catch((e) => activo && setEstadoEnlace(leerError(e)));
    return () => {
      activo = false;
    };
  }, [token]);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    if (password !== confirmacion) {
      setError({ mensaje: "Las contraseñas no coinciden.", campos: { confirmacion: "Debe ser igual a la contraseña." } });
      return;
    }
    setEnviando(true);
    try {
      await identidad.restablecer(token, password);
      navegar("/iniciar-sesion", { replace: true, state: { contrasenaCambiada: true } });
    } catch (e) {
      const leido = leerError(e);
      // Si el enlace venció o se usó mientras escribía, se muestra como enlace inválido.
      if (leido.codigo?.startsWith("enlace_")) setEstadoEnlace(leido);
      else setError(leido);
    } finally {
      setEnviando(false);
    }
  }

  if (estadoEnlace === "verificando") return <p className="cargando">Verificando el enlace…</p>;

  if (estadoEnlace !== "valido") {
    return (
      <section className="tarjeta">
        <h1>Este enlace no sirve</h1>
        <Aviso tipo="error">{estadoEnlace.mensaje}</Aviso>
        <Link to="/recuperar" className="boton">
          Pedir un enlace nuevo
        </Link>
      </section>
    );
  }

  return (
    <section className="tarjeta">
      <h1>Define tu nueva contraseña</h1>
      {error && <Aviso tipo="error">{error.mensaje}</Aviso>}
      <form onSubmit={enviar} noValidate>
        <Campo
          etiqueta="Nueva contraseña"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          ayuda="Mínimo 8 caracteres."
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={error?.campos.password}
        />
        <Campo
          etiqueta="Confirma la contraseña"
          type="password"
          autoComplete="new-password"
          required
          value={confirmacion}
          onChange={(e) => setConfirmacion(e.target.value)}
          error={error?.campos.confirmacion}
        />
        <button type="submit" className="boton" disabled={enviando}>
          {enviando ? "Guardando…" : "Guardar contraseña"}
        </button>
      </form>
    </section>
  );
}
