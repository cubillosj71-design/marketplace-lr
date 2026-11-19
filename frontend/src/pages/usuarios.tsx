import { Check, KeyRound, Minus, PowerOff, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { catalogoApi, identidadApi, leerError, misReservasApi, type ReservaResumen } from "../api";
import { PERMISO_TXT, RESERVA_TXT, ROL_TXT, fechaLarga, iniciales, isoDia } from "../data";
import { Page } from "../layout";
import { useStore, useToast } from "../store";
import { Alert, Field, Modal } from "../ui";

/* ---------------- CU-USU-04 Actualizar perfil · CU-USU-05 Desactivar cuenta ---------------- */
const PENDIENTES = new Set(["CONFIRMADA", "EN_REVISION"]);

export function Perfil() {
  const { usuario, tiene, actualizarUsuario, olvidarSesion } = useStore();
  const toast = useToast();
  const go = useNavigate();
  const u = usuario!;
  // Ciudad opcional: "" en el formulario equivale a "Sin ciudad" (null en la API)
  const [f, setF] = useState({ nombre: u.nombre_completo, telefono: u.telefono, ciudad: u.ciudad ?? "" });
  const [err, setErr] = useState<Record<string, string>>({});
  const [guardado, setGuardado] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const [ciudades, setCiudades] = useState<string[]>([]);
  const [pendientes, setPendientes] = useState<ReservaResumen[]>([]);
  const puedeDesactivar = tiene("cuenta.desactivar");
  const comoHuesped = tiene("reservas.ver_propias");
  const comoAnfitrion = tiene("reservas.ver_de_mis_alojamientos");
  const cambiado = f.nombre !== u.nombre_completo || f.telefono !== u.telefono || f.ciudad !== (u.ciudad ?? "");

  useEffect(() => {
    catalogoApi.ciudades().then((r) => setCiudades(r.data.map((c) => c.nombre))).catch(() => {});
    // CA-04.2, CA-04.5: reservas CONFIRMADAS o EN_REVISION cuya salida no ha pasado, como huésped o en sus alojamientos
    const hoy = isoDia(new Date());
    const fuentes = [
      ...(comoHuesped ? [misReservasApi.mias()] : []),
      ...(comoAnfitrion ? [misReservasApi.deMisAlojamientos()] : []),
    ];
    Promise.all(fuentes)
      .then((rs) => setPendientes(rs.flatMap((r) => r.data).filter((x) => PENDIENTES.has(x.estado) && x.fecha_salida >= hoy)))
      .catch(() => {});
  }, [comoHuesped, comoAnfitrion]);

  const guardar = async () => {
    const er: Record<string, string> = {};
    if (!f.nombre.trim()) er.nombre = "El nombre no puede quedar vacío.";
    if (!f.telefono.trim()) er.telefono = "El teléfono no puede quedar vacío.";
    setErr(er);
    if (Object.keys(er).length) return;
    try {
      const { data } = await identidadApi.actualizarPerfil({ nombre_completo: f.nombre.trim(), telefono: f.telefono.trim(), ciudad: f.ciudad || null });
      actualizarUsuario(data);
      setGuardado(true);
      toast("Cambios guardados");
    } catch (e) {
      const r = leerError(e);
      setErr({ [r.campo === "nombre_completo" ? "nombre" : r.campo ?? "telefono"]: r.error });
    }
  };

  const desactivar = async () => {
    try {
      await identidadApi.desactivar();
      olvidarSesion();
      go("/ingresar", { state: { aviso: "Tu cuenta quedó desactivada. Se reactiva cuando vuelvas a iniciar sesión.", correo: u.correo } });
    } catch (e) {
      // CA-04.2: con reservas pendientes la API responde 409 con el motivo
      setConfirmar(false);
      toast(leerError(e).error, "err");
    }
  };

  return (
    <Page req="RF-D-USU-01.4 · CU-USU-04 · CU-USU-05 · HU-04">
      <div className="page-head">
        <div><h1>Mi perfil</h1><p>Consulta y actualiza tus datos básicos.</p></div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.6fr) minmax(0,1fr)", gap: 20 }} className="perfil-grid">
        <section className="card stack">
          <div className="row" style={{ gap: 16 }}>
            <span className="avatar" style={{ width: 56, height: 56, fontSize: 18 }}>{iniciales(u.nombre_completo)}</span>
            <div>
              <h2>{u.nombre_completo}</h2>
              <div className="row" style={{ gap: 8, marginTop: 4 }}>
                <span className="role-pill">{ROL_TXT[u.rol]}</span>
                {u.activa && !u.restringida && <span className="badge badge-ACTIVA">CUENTA ACTIVA</span>}
              </div>
            </div>
          </div>
          {guardado && !cambiado && <Alert tipo="ok">Cambios guardados. Tu información se actualizó.</Alert>}
          <div className="grid-2">
            <Field label="Nombre completo" error={err.nombre}>
              <input className="input" value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} />
            </Field>
            <Field label="Teléfono" error={err.telefono}>
              <input className="input" value={f.telefono} onChange={(e) => setF({ ...f, telefono: e.target.value })} />
            </Field>
            <Field label="Ciudad (opcional)" error={err.ciudad}>
              <select className="select" value={f.ciudad} onChange={(e) => setF({ ...f, ciudad: e.target.value })}>
                <option value="">Sin ciudad</option>
                {/* Si la cuenta trae una ciudad que no está en el catálogo, se conserva como opción */}
                {[...ciudades, ...(u.ciudad && !ciudades.includes(u.ciudad) ? [u.ciudad] : [])].map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Correo electrónico" hint="El correo identifica tu cuenta y no se puede cambiar.">
              <input className="input" value={u.correo} readOnly />
            </Field>
            <Field label="Fecha de registro">
              <input className="input" value={u.fecha_registro ? new Date(u.fecha_registro).toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" }) : ""} readOnly />
            </Field>
          </div>
          {u.autorizacion_datos && (
            <p className="subtle" style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <ShieldCheck size={15} /> Autorizaste el tratamiento de tus datos personales (Ley 1581 de 2012) el{" "}
              {new Date(u.autorizacion_datos).toLocaleString("es-CO", { dateStyle: "long", timeStyle: "short" })}.
            </p>
          )}
          <div className="row-between">
            <span />
            <button className="btn btn-primary" disabled={!cambiado} onClick={guardar}>Guardar cambios</button>
          </div>
        </section>

        {!puedeDesactivar ? (
          <section className="card stack" style={{ alignSelf: "start" }}>
            <div className="card-title"><span className="ico"><ShieldCheck /></span><h3>Tu cuenta no se desactiva</h3></div>
            <p className="muted">Las cuentas de Administrador no se desactivan desde el perfil, para que la plataforma nunca quede sin administración.</p>
          </section>
        ) : (
          <section className="card stack" style={{ alignSelf: "start" }}>
            <div className="card-title"><span className="ico" style={{ background: "var(--err-soft)", color: "var(--err)" }}><PowerOff /></span><h3>Desactivar cuenta</h3></div>
            <p className="muted">
              {comoAnfitrion
                ? "Mientras esté desactivada, tus publicaciones no aparecen en las búsquedas. "
                : "Mientras esté desactivada, no podrás reservar. "}
              Se reactiva sola cuando vuelvas a iniciar sesión.
            </p>
            {pendientes.length > 0 && (
              <Alert tipo="warn">
                No puedes desactivarla: tienes {pendientes.length} {pendientes.length === 1 ? "reserva pendiente" : "reservas pendientes"} (confirmadas o en revisión)
                {comoAnfitrion ? " en tus alojamientos" : " como huésped"}.
                <ul>
                  {pendientes.map((r) => (
                    <li key={r.id}>{r.alojamiento}: {fechaLarga(r.fecha_llegada)} al {fechaLarga(r.fecha_salida)} ({RESERVA_TXT[r.estado]?.toLowerCase()})</li>
                  ))}
                </ul>
              </Alert>
            )}
            <button className="btn btn-danger btn-block" disabled={pendientes.length > 0} onClick={() => setConfirmar(true)}>
              Desactivar mi cuenta
            </button>
          </section>
        )}
      </div>

      {confirmar && (
        <Modal onClose={() => setConfirmar(false)}>
          <span className="ico-big" style={{ background: "var(--err-soft)", color: "var(--err)" }}><PowerOff /></span>
          <h2>¿Desactivar tu cuenta?</h2>
          <p className="muted">Se cerrará tu sesión. Para reactivarla, solo vuelve a iniciar sesión con tu correo y contraseña.</p>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setConfirmar(false)}>Cancelar</button>
            <button className="btn btn-primary" style={{ background: "var(--err)" }} onClick={desactivar}>Sí, desactivar</button>
          </div>
        </Modal>
      )}
    </Page>
  );
}

/* ---------------- Cambiar contraseña con sesión iniciada ---------------- */
export function CambiarContrasena() {
  const toast = useToast();
  const [f, setF] = useState({ actual: "", nueva: "", conf: "" });
  const [err, setErr] = useState<Record<string, string>>({});
  return (
    <Page req="RF-D-USU-01.3 · RF-D-USU-01.4">
      <div className="page-head"><div><h1>Cambiar contraseña</h1><p>Usa al menos 8 caracteres.</p></div></div>
      <form className="card stack" style={{ maxWidth: 560 }} noValidate onSubmit={async (e) => {
        e.preventDefault();
        const er: Record<string, string> = {};
        if (!f.actual) er.actual = "Escribe tu contraseña actual.";
        if (f.nueva.length < 8) er.nueva = "Debe tener al menos 8 caracteres.";
        if (f.nueva !== f.conf) er.conf = "Las contraseñas no coinciden.";
        if (!Object.keys(er).length) {
          try {
            await identidadApi.actualizarPerfil({ password_actual: f.actual, password_nueva: f.nueva });
            toast("Contraseña actualizada");
            setF({ actual: "", nueva: "", conf: "" });
          } catch (ex) {
            const r = leerError(ex);
            er[r.campo === "password_nueva" ? "nueva" : "actual"] = r.error;
          }
        }
        setErr(er);
      }}>
        <div className="card-title"><span className="ico"><KeyRound /></span><h3>Nueva contraseña</h3></div>
        <Field label="Contraseña actual" error={err.actual}><input className="input" type="password" value={f.actual} onChange={(e) => setF({ ...f, actual: e.target.value })} /></Field>
        <Field label="Nueva contraseña" error={err.nueva} hint="Mínimo 8 caracteres."><input className="input" type="password" value={f.nueva} onChange={(e) => setF({ ...f, nueva: e.target.value })} /></Field>
        <Field label="Confirmar nueva contraseña" error={err.conf}><input className="input" type="password" value={f.conf} onChange={(e) => setF({ ...f, conf: e.target.value })} /></Field>
        <div className="row"><button className="btn btn-primary right" type="submit">Actualizar contraseña</button></div>
      </form>
    </Page>
  );
}

/* ---------------- RF-D-USU-02.1 Roles y permisos (consulta) ---------------- */
const CORTO: Record<string, string> = { VISITANTE: "Visit.", HUESPED: "Huésp.", ANFITRION: "Anfit.", ADMINISTRADOR: "Admin" };

/** La matriz sale de GET /identidad/roles (rbac.PERMISOS en el backend); se resalta la columna del usuario actual. */
export function Roles() {
  const { usuario } = useStore();
  const [roles, setRoles] = useState<{ rol: string; permisos: string[] }[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    identidadApi.roles().then((r) => setRoles(r.data.roles)).catch((e) => setError(leerError(e).error));
  }, []);
  const actual = usuario?.rol ?? "VISITANTE";  // solo para resaltar la columna
  const filas = roles ? [...new Set(roles.flatMap((r) => r.permisos))] : [];
  const porRol = new Map((roles ?? []).map((r) => [r.rol, new Set(r.permisos)]));

  return (
    <Page req="RF-D-USU-02.1 · HU-05 · GET /identidad/roles">
      <div className="page-head">
        <div><h1>Roles y permisos</h1><p>Cada cuenta tiene un único rol. Si alguien intenta usar una función que no le corresponde, el sistema la niega.</p></div>
      </div>
      {error && <Alert tipo="error">{error}</Alert>}
      {!roles ? (!error && <p className="muted">Cargando…</p>) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div className="table-wrap">
            <table className="table matriz-roles">
              <thead>
                <tr>
                  <th>Permiso</th>
                  {roles.map((r) => (
                    <th key={r.rol} style={{ textAlign: "center", color: r.rol === actual ? "var(--accent)" : undefined }}>
                      <span className="largo">{ROL_TXT[r.rol] ?? r.rol}{r.rol === actual && " (tú)"}</span>
                      <span className="corto" title={ROL_TXT[r.rol]}>{CORTO[r.rol] ?? r.rol}{r.rol === actual && " ●"}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filas.map((p) => (
                  <tr key={p}>
                    <td>{PERMISO_TXT[p] ?? p}</td>
                    {roles.map((r) => (
                      <td key={r.rol} style={{ textAlign: "center", background: r.rol === actual ? "var(--accent-soft)" : undefined }}>
                        {porRol.get(r.rol)?.has(p)
                          ? <Check size={18} color="var(--ok)" aria-label="Permitido" />
                          : <Minus size={18} color="#c4ccca" aria-label="No permitido" />}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <p className="subtle" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
        <UserRound size={14} /> El Visitante es quien entra sin cuenta o sin haber iniciado sesión.
      </p>
    </Page>
  );
}
