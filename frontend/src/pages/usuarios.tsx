import { Check, KeyRound, Minus, PowerOff, ShieldCheck, UserRound } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CIUDADES, ROL_TXT, fechaLarga, iniciales } from "../data";
import { Page } from "../layout";
import { useStore, useToast } from "../store";
import { Alert, Field, Modal } from "../ui";

/* ---------------- CU-USU-04 Actualizar perfil · CU-USU-05 Desactivar cuenta ---------------- */
export function Perfil() {
  const { usuario, actualizarPerfil, reservasPendientesDe, desactivarCuenta, publicaciones } = useStore();
  const toast = useToast();
  const go = useNavigate();
  const u = usuario!;
  const [f, setF] = useState({ nombre: u.nombre, telefono: u.telefono, ciudad: u.ciudad });
  const [err, setErr] = useState<Record<string, string>>({});
  const [guardado, setGuardado] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const pendientes = reservasPendientesDe(u);
  const esAdmin = u.rol === "ADMINISTRADOR";
  const cambiado = f.nombre !== u.nombre || f.telefono !== u.telefono || f.ciudad !== u.ciudad;

  const guardar = () => {
    const er: Record<string, string> = {};
    if (!f.nombre.trim()) er.nombre = "El nombre no puede quedar vacío.";
    if (!f.telefono.trim()) er.telefono = "El teléfono no puede quedar vacío.";
    setErr(er);
    if (Object.keys(er).length) return;
    actualizarPerfil(f);
    setGuardado(true);
    toast("Cambios guardados");
  };

  return (
    <Page req="RF-D-USU-01.4 · CU-USU-04 · CU-USU-05 · HU-04">
      <div className="page-head">
        <div><h1>Mi perfil</h1><p>Consulta y actualiza tus datos básicos.</p></div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.6fr) minmax(0,1fr)", gap: 20 }} className="perfil-grid">
        <section className="card stack">
          <div className="row" style={{ gap: 16 }}>
            <span className="avatar" style={{ width: 56, height: 56, fontSize: 18 }}>{iniciales(u.nombre)}</span>
            <div>
              <h2>{u.nombre}</h2>
              <div className="row" style={{ gap: 8, marginTop: 4 }}>
                <span className="role-pill">{ROL_TXT[u.rol]}</span>
                <span className="badge badge-ACTIVA">CUENTA ACTIVA</span>
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
            <Field label="Ciudad">
              <select className="select" value={f.ciudad} onChange={(e) => setF({ ...f, ciudad: e.target.value })}>
                <option value="">Selecciona tu ciudad</option>
                {CIUDADES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Correo electrónico" hint="El correo identifica tu cuenta y no se puede cambiar.">
              <input className="input" value={u.correo} readOnly />
            </Field>
          </div>
          <div className="row-between">
            <span className="subtle">El rol tampoco se cambia: cada cuenta tiene un único rol.</span>
            <button className="btn btn-primary" disabled={!cambiado} onClick={guardar}>Guardar cambios</button>
          </div>
        </section>

        {esAdmin ? (
          <section className="card stack" style={{ alignSelf: "start" }}>
            <div className="card-title"><span className="ico"><ShieldCheck /></span><h3>Cuenta de administrador</h3></div>
            <p className="muted">Las cuentas de Administrador no se crean por registro: la primera la carga el equipo al poner en marcha la plataforma.</p>
            <Alert tipo="info">Tu rol modera publicaciones y puede modificar cualquier publicación.</Alert>
          </section>
        ) : (
          <section className="card stack" style={{ alignSelf: "start" }}>
            <div className="card-title"><span className="ico" style={{ background: "var(--err-soft)", color: "var(--err)" }}><PowerOff /></span><h3>Desactivar cuenta</h3></div>
            <p className="muted">
              {u.rol === "ANFITRION"
                ? "Mientras esté desactivada, tus publicaciones no aparecen en las búsquedas. "
                : "Mientras esté desactivada, no podrás reservar. "}
              Se reactiva sola cuando vuelvas a iniciar sesión.
            </p>
            {pendientes.length > 0 && (
              <Alert tipo="warn">
                No puedes desactivarla: tienes {pendientes.length} {pendientes.length === 1 ? "reserva CONFIRMADA pendiente" : "reservas CONFIRMADAS pendientes"}
                {u.rol === "ANFITRION" ? " en tus alojamientos" : " como huésped"}.
                <ul>
                  {pendientes.map((r) => (
                    <li key={r.id}>{publicaciones.find((p) => p.id === r.publicacionId)?.titulo}: {fechaLarga(r.llegada)} al {fechaLarga(r.salida)}</li>
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
            <button className="btn btn-primary" style={{ background: "var(--err)" }} onClick={() => {
              const r = desactivarCuenta();
              if (r.ok) go("/ingresar", { state: { aviso: "Tu cuenta quedó desactivada. Se reactiva cuando vuelvas a iniciar sesión.", correo: u.correo } });
            }}>Sí, desactivar</button>
          </div>
        </Modal>
      )}
    </Page>
  );
}

/* ---------------- Cambiar contraseña con sesión iniciada ---------------- */
export function CambiarContrasena() {
  const { cambiarClave } = useStore();
  const toast = useToast();
  const [f, setF] = useState({ actual: "", nueva: "", conf: "" });
  const [err, setErr] = useState<Record<string, string>>({});
  return (
    <Page req="RF-D-USU-01.3 · RF-D-USU-01.4">
      <div className="page-head"><div><h1>Cambiar contraseña</h1><p>Usa al menos 8 caracteres.</p></div></div>
      <form className="card stack" style={{ maxWidth: 560 }} noValidate onSubmit={(e) => {
        e.preventDefault();
        const er: Record<string, string> = {};
        if (!f.actual) er.actual = "Escribe tu contraseña actual.";
        if (f.nueva.length < 8) er.nueva = "Debe tener al menos 8 caracteres.";
        if (f.nueva !== f.conf) er.conf = "Las contraseñas no coinciden.";
        if (!Object.keys(er).length) {
          const r = cambiarClave(f.actual, f.nueva);
          if (!r.ok) er[r.campo ?? "actual"] = r.error;
          else { toast("Contraseña actualizada"); setF({ actual: "", nueva: "", conf: "" }); }
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
const MATRIZ: [string, boolean, boolean, boolean, boolean][] = [
  ["Buscar alojamientos y ver su detalle", true, true, false, false],
  ["Registrarse", true, false, false, false],
  ["Iniciar sesión y actualizar su perfil", false, true, true, true],
  ["Desactivar su cuenta", false, true, true, false],
  ["Crear y editar sus publicaciones", false, false, true, false],
  ["Enviar publicación a revisión", false, false, true, false],
  ["Pausar o reactivar publicación", false, false, true, false],
  ["Administrar el calendario", false, false, true, false],
  ["Cotizar, reservar, cancelar y reseñar", false, true, false, false],
  ["Aprobar, devolver o bloquear publicaciones", false, false, false, true],
  ["Modificar cualquier publicación", false, false, false, true],
  ["Consultar el registro de acciones", false, false, false, true],
  ["Descargar reportes de usuarios y publicaciones (PDF o Excel)", false, false, false, true],
];

export function Roles() {
  const { usuario } = useStore();
  const col = { HUESPED: 2, ANFITRION: 3, ADMINISTRADOR: 4 }[usuario!.rol];
  return (
    <Page req="RF-D-USU-02.1 · HU-05">
      <div className="page-head">
        <div><h1>Roles y permisos</h1><p>Cada cuenta tiene un único rol. Si alguien intenta usar una función que no le corresponde, el sistema la niega.</p></div>
      </div>
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Acción</th>
                {["Visitante", "Huésped", "Anfitrión", "Administrador"].map((r, i) => (
                  <th key={r} style={{ textAlign: "center", color: i + 1 === col ? "var(--accent)" : undefined }}>
                    {r}{i + 1 === col && " (tú)"}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MATRIZ.map(([accion, ...permisos]) => (
                <tr key={accion}>
                  <td>{accion}</td>
                  {permisos.map((p, i) => (
                    <td key={i} style={{ textAlign: "center", background: i + 1 === col ? "var(--accent-soft)" : undefined }}>
                      {p
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
      <p className="subtle" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
        <UserRound size={14} /> El Visitante es quien entra sin cuenta o sin haber iniciado sesión.
      </p>
    </Page>
  );
}
