import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Aviso, Campo } from "../componentes/Campo";
import { leerError, type ErrorApi } from "../errores";
import { identidad, NOMBRE_ROL, type Usuario } from "../identidad/api";
import { useSesion } from "../sesion/SesionContext";

/** HU-04 Mantener el perfil (CU-USU-04 Actualizar perfil, CU-USU-05 Desactivar cuenta). */
export function Perfil() {
  const { actualizarUsuario, olvidarSesion } = useSesion();
  const navegar = useNavigate();
  const [perfil, setPerfil] = useState<Usuario | null>(null);
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [error, setError] = useState<ErrorApi | null>(null);
  const [guardado, setGuardado] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [confirmandoDesactivacion, setConfirmandoDesactivacion] = useState(false);
  const [errorDesactivacion, setErrorDesactivacion] = useState<ErrorApi | null>(null);

  useEffect(() => {
    // "activo" descarta la respuesta si el componente ya se desmontó o si el
    // efecto se volvió a ejecutar (React.StrictMode lo ejecuta dos veces en
    // desarrollo). Sin esto, una respuesta tardía podría borrar lo que el
    // usuario ya empezó a escribir.
    let activo = true;
    identidad
      .perfil()
      .then(({ data }) => {
        if (!activo) return;
        setPerfil(data);
        setNombre(data.nombre_completo);
        setTelefono(data.telefono);
      })
      .catch((e) => activo && setError(leerError(e)));
    return () => {
      activo = false;
    };
  }, []);

  async function guardar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setGuardado(false);
    setEnviando(true);
    try {
      const { data } = await identidad.actualizarPerfil({ nombre_completo: nombre, telefono });
      setPerfil(data);
      actualizarUsuario(data);
      setGuardado(true);
    } catch (e) {
      setError(leerError(e));
    } finally {
      setEnviando(false);
    }
  }

  async function desactivar() {
    setErrorDesactivacion(null);
    try {
      await identidad.desactivar();
      olvidarSesion();
      navegar("/iniciar-sesion", { replace: true, state: { desactivada: true } });
    } catch (e) {
      // CA-04.2: con reservas confirmadas pendientes el sistema no lo permite e informa el motivo.
      setErrorDesactivacion(leerError(e));
      setConfirmandoDesactivacion(false);
    }
  }

  if (!perfil) return error ? <Aviso tipo="error">{error.mensaje}</Aviso> : <p className="cargando">Cargando tu perfil…</p>;

  return (
    <>
      <section className="tarjeta">
        <h1>Mi perfil</h1>
        <dl className="datos-fijos">
          <dt>Correo</dt>
          <dd>{perfil.correo}</dd>
          <dt>Rol</dt>
          <dd>{NOMBRE_ROL[perfil.rol]}</dd>
          <dt>Miembro desde</dt>
          <dd>{new Date(perfil.fecha_registro).toLocaleDateString("es-CO", { dateStyle: "long" })}</dd>
        </dl>
        {guardado && <Aviso tipo="exito">Tus datos quedaron actualizados.</Aviso>}
        {error && <Aviso tipo="error">{error.mensaje}</Aviso>}
        <form onSubmit={guardar} noValidate>
          <Campo
            etiqueta="Nombre completo"
            autoComplete="name"
            required
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            error={error?.campos.nombre_completo}
          />
          <Campo
            etiqueta="Teléfono"
            type="tel"
            autoComplete="tel"
            required
            value={telefono}
            onChange={(e) => setTelefono(e.target.value)}
            error={error?.campos.telefono}
          />
          <button type="submit" className="boton" disabled={enviando}>
            {enviando ? "Guardando…" : "Guardar cambios"}
          </button>
        </form>
      </section>

      <section className="tarjeta zona-peligro">
        <h2>Desactivar mi cuenta</h2>
        <p>
          Mientras tu cuenta esté desactivada no podrás usar la plataforma
          {perfil.rol === "ANFITRION" ? " y tus alojamientos no aparecerán en las búsquedas" : ""}. Para reactivarla,
          basta con volver a iniciar sesión.
        </p>
        {errorDesactivacion && <Aviso tipo="error">{errorDesactivacion.mensaje}</Aviso>}
        {confirmandoDesactivacion ? (
          <div className="acciones">
            <button type="button" className="boton boton-peligro" onClick={desactivar}>
              Sí, desactivar
            </button>
            <button type="button" className="boton boton-secundario" onClick={() => setConfirmandoDesactivacion(false)}>
              Cancelar
            </button>
          </div>
        ) : (
          <button type="button" className="boton boton-secundario" onClick={() => setConfirmandoDesactivacion(true)}>
            Desactivar cuenta
          </button>
        )}
      </section>
    </>
  );
}
