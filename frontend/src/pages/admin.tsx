import { ArrowLeft, Ban, Check, CheckCircle2, CircleDashed, ClipboardList, PauseCircle, Search, ShieldOff, Undo2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { cop, faltantesRevision, type EstadoPub } from "../data";
import { Page } from "../layout";
import { useStore, useToast } from "../store";
import { Alert, Badge, Field, ImageTile, Modal } from "../ui";

/* Moderación del administrador (módulo ADM), incluida para completar el ciclo de estados de ALO. */
export function AdminPublicaciones({ soloPendientes = false }: { soloPendientes?: boolean }) {
  const { publicaciones, usuarios, cambiarEstado } = useStore();
  const toast = useToast();
  const go = useNavigate();
  const [q, setQ] = useState("");
  const [estado, setEstado] = useState<"" | EstadoPub>(soloPendientes ? "PENDIENTE_REVISION" : "");
  const [bloquear, setBloquear] = useState<number | null>(null);
  const [motivo, setMotivo] = useState("");
  const nombre = (id: number) => usuarios.find((u) => u.id === id)?.nombre ?? "";
  const lista = publicaciones.filter((p) =>
    p.estado !== "BORRADOR" &&
    (!estado || p.estado === estado) &&
    (!q || `${p.titulo} ${p.ciudad} ${nombre(p.anfitrionId)}`.toLowerCase().includes(q.toLowerCase())));
  const n = (e: EstadoPub) => publicaciones.filter((p) => p.estado === e).length;
  const stats = [
    { label: "Pendientes de revisión", v: n("PENDIENTE_REVISION"), icon: ClipboardList, bg: "#fdf0c8", fg: "#8a4b05" },
    { label: "Activas", v: n("ACTIVA"), icon: CheckCircle2, bg: "#dcf3e4", fg: "#166534" },
    { label: "Pausadas", v: n("PAUSADA"), icon: PauseCircle, bg: "#e3ecfa", fg: "#1e4a8a" },
    { label: "Bloqueadas", v: n("BLOQUEADA"), icon: Ban, bg: "#fbe1de", fg: "#9b1c12" },
  ];
  const pub = publicaciones.find((p) => p.id === bloquear);

  return (
    <Page req="RF-D-ADM-01.1 · RF-D-ALO-02.1 · el administrador puede modificar cualquier publicación">
      <div className="page-head">
        <div><h1>{soloPendientes ? "Pendientes de revisión" : "Todas las publicaciones"}</h1><p>Publicaciones de todos los anfitriones (los borradores solo los ve su dueño).</p></div>
      </div>
      {!soloPendientes && (
        <div className="grid-4">
          {stats.map((s) => (
            <div key={s.label} className="card card-tight stat">
              <span className="ico" style={{ background: s.bg, color: s.fg }}><s.icon /></span>
              <div><b>{s.v}</b><span>{s.label}</span></div>
            </div>
          ))}
        </div>
      )}
      <div className="toolbar">
        <div className="search"><Search /><input className="input" placeholder="Buscar por título, anfitrión o ciudad" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        {!soloPendientes && (
          <select className="select" value={estado} onChange={(e) => setEstado(e.target.value as EstadoPub | "")}>
            <option value="">Estado: todos</option>
            {(["PENDIENTE_REVISION", "ACTIVA", "PAUSADA", "BLOQUEADA"] as EstadoPub[]).map((e) => <option key={e}>{e}</option>)}
          </select>
        )}
      </div>
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {lista.length === 0 ? <div className="empty-state"><CheckCircle2 /><b>No hay publicaciones pendientes</b></div> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Publicación</th><th>Anfitrión</th><th>Ciudad</th><th>Estado</th><th>Acción</th></tr></thead>
              <tbody>
                {lista.map((p) => (
                  <tr key={p.id}>
                    <td><div className="pub-cell"><ImageTile img={p.imagenes[0]} style={{ width: 52, height: 40, borderRadius: 8 }} /><b>{p.titulo}</b></div></td>
                    <td>{nombre(p.anfitrionId)}</td>
                    <td>{p.ciudad}</td>
                    <td><Badge estado={p.estado} /></td>
                    <td>
                      <div className="row" style={{ gap: 6 }}>
                        {p.estado === "PENDIENTE_REVISION" && <button className="btn btn-primary btn-sm" onClick={() => go(`/admin/revision/${p.id}`)}>Revisar</button>}
                        {(p.estado === "ACTIVA" || p.estado === "PAUSADA") && <button className="btn btn-danger btn-sm" onClick={() => { setBloquear(p.id); setMotivo(""); }}><Ban /> Bloquear</button>}
                        {p.estado === "BLOQUEADA" && <button className="btn btn-secondary btn-sm" onClick={() => { cambiarEstado(p.id, "PAUSADA", { motivoBloqueo: undefined }); toast("Desbloqueada: queda PAUSADA y el anfitrión puede reactivarla"); }}><ShieldOff /> Desbloquear</button>}
                        <Link className="btn btn-ghost btn-sm" to={`/publicaciones/${p.id}`}>Ver</Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {pub && (
        <Modal onClose={() => setBloquear(null)}>
          <span className="ico-big" style={{ background: "var(--err-soft)", color: "var(--err)" }}><Ban /></span>
          <h2>Bloquear «{pub.titulo}»</h2>
          <p className="muted">Deja de aparecer en las búsquedas y el anfitrión ve el motivo. Solo un administrador puede desbloquearla.</p>
          <Field label="Motivo" hint="Obligatorio.">
            <textarea className="textarea" placeholder="Ej. La información de la publicación es engañosa." value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </Field>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setBloquear(null)}>Cancelar</button>
            <button className="btn btn-primary" style={{ background: "var(--err)" }} disabled={!motivo.trim()}
              onClick={() => { cambiarEstado(pub.id, "BLOQUEADA", { motivoBloqueo: motivo.trim() }); setBloquear(null); toast("Publicación bloqueada"); }}>Bloquear</button>
          </div>
        </Modal>
      )}
    </Page>
  );
}

export function RevisarPublicacion() {
  const { id } = useParams();
  const { publicaciones, usuarios, cambiarEstado } = useStore();
  const toast = useToast();
  const go = useNavigate();
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");
  const p = publicaciones.find((x) => x.id === Number(id));
  if (!p || p.estado !== "PENDIENTE_REVISION")
    return <Page req="RF-D-ADM-01.1"><div className="card empty-state"><CheckCircle2 /><b>Esta publicación ya no está pendiente</b><Link className="btn btn-secondary" to="/admin/revision">Volver</Link></div></Page>;
  const faltan = new Set(faltantesRevision(p));
  const checks: [string, boolean][] = [
    ["Título y descripción", !faltan.has("título") && !faltan.has("descripción")],
    ["Ciudad y ubicación", !faltan.has("ciudad") && !faltan.has("ubicación")],
    ["Tipo y capacidad mayor que 0", !faltan.has("tipo de alojamiento") && !faltan.has("capacidad mayor que 0")],
    ["Precio por noche mayor que 0", !faltan.has("precio por noche")],
    ["Política de cancelación", !faltan.has("política de cancelación")],
    ["Al menos una imagen", !faltan.has("al menos una imagen")],
  ];

  return (
    <Page req="RF-D-ADM-01.1 · CU-ADM-01 · HU-19">
      <div>
        <Link to="/admin/revision" className="back"><ArrowLeft /> Pendientes de revisión</Link>
        <div className="page-head">
          <div className="row" style={{ gap: 12 }}><h1>{p.titulo}</h1><Badge estado={p.estado} /></div>
          <div className="row">
            <button className="btn btn-secondary" onClick={() => {
              if (!motivo.trim()) return setError("Escribe la observación para el anfitrión.");
              cambiarEstado(p.id, "BORRADOR", { observacion: motivo.trim() });
              toast("Devuelta al anfitrión con tu observación"); go("/admin/revision");
            }}><Undo2 /> Devolver</button>
            <button className="btn btn-primary" onClick={() => { cambiarEstado(p.id, "ACTIVA"); toast("Aprobada: ya aparece en las búsquedas"); go("/admin/revision"); }}>
              <Check /> Aprobar y activar
            </button>
          </div>
        </div>
      </div>
      <div className="detail-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,1.7fr) minmax(0,1fr)", gap: 20, alignItems: "start" }}>
        <section className="card stack">
          <div className="kv">
            <div><span>Anfitrión</span><b>{usuarios.find((u) => u.id === p.anfitrionId)?.nombre}</b></div>
            <div><span>Ciudad</span><b>{p.ciudad}</b></div>
            <div><span>Tipo</span><b>{p.tipo}</b></div>
            <div><span>Capacidad</span><b>{p.capacidad} huéspedes</b></div>
            <div><span>Precio por noche</span><b>{cop(p.precioNoche)}</b></div>
            <div><span>Política</span><b>{p.politica}</b></div>
          </div>
          <p>{p.descripcion}</p>
          <div className="img-grid">{p.imagenes.map((im, i) => <ImageTile key={im.id} img={im} etiqueta={i === 0 ? "Portada" : im.nombre} />)}</div>
        </section>
        <aside className="card stack">
          <h3>Datos obligatorios</h3>
          <ul className="list-plain">
            {checks.map(([t, ok]) => (
              <li key={t} style={{ color: ok ? "var(--ok)" : "var(--err)" }}>{ok ? <Check /> : <CircleDashed />}{t}</li>
            ))}
          </ul>
          <Field label="Observación si la devuelves" error={error}>
            <textarea className="textarea" placeholder="Ej. Las fotos no corresponden al alojamiento." value={motivo} onChange={(e) => { setMotivo(e.target.value); setError(""); }} />
          </Field>
          <Alert tipo="info">Al aprobarla pasa a ACTIVA y aparece en las búsquedas. Al devolverla vuelve a BORRADOR y el anfitrión ve tu observación.</Alert>
        </aside>
      </div>
    </Page>
  );
}

/* Consulta del registro de acciones (módulo ADM): muestra lo que el prototipo deja registrado. */
export function RegistroAcciones() {
  const { eventos } = useStore();
  const [filtro, setFiltro] = useState<"" | "EXITO" | "FALLO">("");
  const lista = eventos.filter((e) => !filtro || e.resultado === filtro);
  return (
    <Page req="Registro de inicios de sesión, accesos negados y cambios de estado · CA-02.2 · CA-05.2">
      <div className="page-head">
        <div><h1>Registro de acciones</h1><p>Quién hizo cada acción, sobre qué, cuándo y con qué resultado.</p></div>
        <select className="select" style={{ width: 200 }} value={filtro} onChange={(e) => setFiltro(e.target.value as "" | "EXITO" | "FALLO")}>
          <option value="">Resultado: todos</option><option value="EXITO">Éxito</option><option value="FALLO">Fallo</option>
        </select>
      </div>
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {lista.length === 0 ? <div className="empty-state"><CheckCircle2 /><b>Aún no hay acciones registradas</b><span>Inicia sesión con otras cuentas o intenta entrar a una función de otro rol.</span></div> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Fecha y hora</th><th>Quién</th><th>Acción</th><th>Detalle</th><th>Resultado</th></tr></thead>
              <tbody>
                {lista.map((e) => (
                  <tr key={e.id}>
                    <td style={{ whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>{new Date(e.fecha).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "medium" })}</td>
                    <td>{e.quien}</td>
                    <td>{e.accion}</td>
                    <td className="muted">{e.detalle}</td>
                    <td><span className={`badge ${e.resultado === "EXITO" ? "badge-ACTIVA" : "badge-BLOQUEADA"}`}>{e.resultado === "EXITO" ? "ÉXITO" : "FALLO"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Page>
  );
}
