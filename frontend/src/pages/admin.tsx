import {
  ArrowLeft, Ban, BarChart3, Check, CheckCircle2, ClipboardList, History, PauseCircle, Percent, PlayCircle, Search,
  ShieldAlert, ShieldOff, Undo2, Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  adminApi, leerError,
  type EventoAuditoriaApi, type PublicacionAdmin, type PublicacionCompleta, type TableroApi, type UsuarioAdmin,
} from "../api";
import { ROL_TXT, cop, type AccionModeracion, type EstadoPub, type Rol } from "../data";
import { Page } from "../layout";
import { useStore, useToast } from "../store";
import { Alert, Badge, Field, Modal } from "../ui";

const pesos = (v: string | null | undefined) => (v == null ? "—" : cop(Number(v)));
const fechaHora = (f: string) => new Date(f).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" }).replace(/\.$/, "");
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function Stat({ icon: Icon, v, label, bg, fg }: { icon: typeof Users; v: ReactNode; label: string; bg: string; fg: string }) {
  return (
    <div className="card card-tight stat">
      <span className="ico" style={{ background: bg, color: fg }}><Icon /></span>
      <div><b>{v}</b><span>{label}</span></div>
    </div>
  );
}

/** Nombres de las cuentas para mostrar al anfitrión o al administrador de una fila. */
function useNombres() {
  const [nombres, setNombres] = useState<Record<number, string>>({});
  useEffect(() => {
    adminApi.usuarios().then((r) => setNombres(Object.fromEntries(r.data.map((u) => [u.id, u.nombre_completo])))).catch(() => {});
  }, []);
  return nombres;
}

/* ---------------- acciones de moderación sobre una publicación (HU-19, HU-20) ---------------- */
function AccionesPublicacion({ p, alCambiar, compacto }: { p: Pick<PublicacionAdmin, "id" | "titulo" | "estado">; alCambiar: () => void; compacto?: boolean }) {
  const toast = useToast();
  const go = useNavigate();
  const [bloquear, setBloquear] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const sm = compacto ? " btn-sm" : "";

  const hacer = async (accion: () => Promise<unknown>, ok: string) => {
    setEnviando(true);
    try { await accion(); toast(ok); alCambiar(); return true; }
    catch (e) { toast(leerError(e).error, "err"); return false; }
    finally { setEnviando(false); }
  };

  return (
    <>
      <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
        {p.estado === "PENDIENTE_REVISION" && compacto && <button className={`btn btn-primary${sm}`} onClick={() => go(`/admin/revision/${p.id}`)}>Revisar</button>}
        {p.estado === "ACTIVA" && <button className={`btn btn-secondary${sm}`} disabled={enviando} onClick={() => hacer(() => adminApi.pausar(p.id), "Publicación pausada: ya no aparece en las búsquedas")}><PauseCircle /> Pausar</button>}
        {p.estado === "PAUSADA" && <button className={`btn btn-secondary${sm}`} disabled={enviando} onClick={() => hacer(() => adminApi.reactivar(p.id), "Publicación reactivada")}><PlayCircle /> Reactivar</button>}
        {(p.estado === "ACTIVA" || p.estado === "PAUSADA") && <button className={`btn btn-danger${sm}`} disabled={enviando} onClick={() => { setMotivo(""); setError(""); setBloquear(true); }}><Ban /> Bloquear</button>}
        {p.estado === "BLOQUEADA" && <button className={`btn btn-secondary${sm}`} disabled={enviando} onClick={() => hacer(() => adminApi.desbloquear(p.id), "Desbloqueada: queda PAUSADA y el anfitrión puede reactivarla")}><ShieldOff /> Desbloquear</button>}
        {compacto && <Link className={`btn btn-ghost${sm}`} to={`/admin/publicaciones/${p.id}`}>Ver</Link>}
      </div>
      {bloquear && (
        <Modal onClose={() => setBloquear(false)}>
          <span className="ico-big" style={{ background: "var(--err-soft)", color: "var(--err)" }}><Ban /></span>
          <h2>Bloquear «{p.titulo}»</h2>
          <p className="muted">Deja de aparecer en las búsquedas y sus reservas futuras pasan a EN_REVISION. El anfitrión ve el motivo.</p>
          <Field label="Motivo" hint="Obligatorio." error={error}>
            <textarea className="textarea" placeholder="Ej. La dirección publicada no coincide con la del alojamiento." value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </Field>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setBloquear(false)}>Cancelar</button>
            <button className="btn btn-primary" style={{ background: "var(--err)" }} disabled={!motivo.trim() || enviando}
              onClick={async () => { if (await hacer(() => adminApi.bloquear(p.id, motivo.trim()), "Publicación bloqueada")) setBloquear(false); }}>Bloquear</button>
          </div>
        </Modal>
      )}
    </>
  );
}

/* ---------------- HU-19 Todas las publicaciones y Pendientes de revisión ---------------- */
export function AdminPublicaciones({ soloPendientes = false }: { soloPendientes?: boolean }) {
  const nombres = useNombres();
  const [todas, setTodas] = useState<PublicacionAdmin[] | null>(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [estado, setEstado] = useState<"" | EstadoPub>(soloPendientes ? "PENDIENTE_REVISION" : "");
  const cargar = useCallback(() => {
    adminApi.publicaciones().then(setTodas).catch((e) => setError(leerError(e).error));
  }, []);
  useEffect(cargar, [cargar]);

  const lista = (todas ?? []).filter((p) => (!estado || p.estado === estado)
    && (!q || `${p.titulo} ${p.ciudad_nombre ?? ""} ${nombres[p.anfitrion] ?? ""}`.toLowerCase().includes(q.toLowerCase())));
  const n = (e: EstadoPub) => (todas ?? []).filter((p) => p.estado === e).length;

  return (
    <Page req="RF-D-ADM-01.1 · RF-D-ADM-01.2 · HU-19 · HU-20">
      <div className="page-head">
        <div><h1>{soloPendientes ? "Pendientes de revisión" : "Todas las publicaciones"}</h1><p>Publicaciones de todos los anfitriones (los borradores solo los ve su dueño).</p></div>
      </div>
      {!soloPendientes && (
        <div className="grid-4">
          <Stat icon={ClipboardList} v={n("PENDIENTE_REVISION")} label="Pendientes de revisión" bg="#fdf0c8" fg="#8a4b05" />
          <Stat icon={CheckCircle2} v={n("ACTIVA")} label="Activas" bg="#dcf3e4" fg="#166534" />
          <Stat icon={PauseCircle} v={n("PAUSADA")} label="Pausadas" bg="#e3ecfa" fg="#1e4a8a" />
          <Stat icon={Ban} v={n("BLOQUEADA")} label="Bloqueadas" bg="#fbe1de" fg="#9b1c12" />
        </div>
      )}
      <div className="toolbar">
        <div className="search"><Search /><input className="input" placeholder="Buscar por título, anfitrión o ciudad" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        {!soloPendientes && (
          <select className="select" value={estado} onChange={(e) => setEstado(e.target.value as EstadoPub | "")} aria-label="Estado">
            <option value="">Estado: todos</option>
            {(["PENDIENTE_REVISION", "ACTIVA", "PAUSADA", "BLOQUEADA"] as EstadoPub[]).map((e) => <option key={e} value={e}>{e.replace("_", " ")}</option>)}
          </select>
        )}
      </div>
      {error && <Alert tipo="error">{error}</Alert>}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {todas && lista.length === 0 ? <div className="empty-state"><CheckCircle2 /><b>No hay publicaciones para mostrar</b></div> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Publicación</th><th>Anfitrión</th><th>Ciudad</th><th>Precio</th><th>Estado</th><th>Acción</th></tr></thead>
              <tbody>
                {lista.map((p) => (
                  <tr key={p.id}>
                    <td><b>{p.titulo}</b><span className="subtle" style={{ display: "block" }}>{p.tipo_nombre}</span></td>
                    <td>{nombres[p.anfitrion] ?? `#${p.anfitrion}`}</td>
                    <td>{p.ciudad_nombre}</td>
                    <td>{pesos(p.precio_noche)}</td>
                    <td><Badge estado={p.estado} /></td>
                    <td><AccionesPublicacion p={p} alCambiar={cargar} compacto /></td>
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

/* ---------------- HU-19 Revisar: aprobar o devolver con observación ---------------- */
export function RevisarPublicacion() {
  const { id } = useParams();
  const go = useNavigate();
  const toast = useToast();
  const nombres = useNombres();
  const [p, setP] = useState<PublicacionCompleta | null>(null);
  const [error, setError] = useState("");
  const [devolver, setDevolver] = useState(false);
  const [obs, setObs] = useState("");
  const [enviando, setEnviando] = useState(false);
  const cargar = useCallback(() => {
    adminApi.publicacion(Number(id)).then((r) => setP(r.data)).catch((e) => setError(leerError(e).error));
  }, [id]);
  useEffect(cargar, [cargar]);

  const revisar = async (accion: "APROBAR" | "DEVOLVER") => {
    if (!p) return;
    setEnviando(true);
    try {
      await adminApi.revisar(p.id, accion, accion === "DEVOLVER" ? obs.trim() : undefined);
      toast(accion === "APROBAR" ? "Aprobada: ya aparece en las búsquedas" : "Devuelta al anfitrión con la observación");
      go("/admin/revision");
    } catch (e) { setError(leerError(e).error); setDevolver(false); }
    finally { setEnviando(false); }
  };

  if (!p) return <Page req="RF-D-ADM-01.1">{error ? <Alert tipo="error">{error}</Alert> : <p className="muted">Cargando…</p>}</Page>;
  return (
    <Page req="RF-D-ADM-01.1 · RF-D-ADM-01.2 · HU-19">
      <Link to={p.estado === "PENDIENTE_REVISION" ? "/admin/revision" : "/admin/publicaciones"} className="back"><ArrowLeft /> Volver</Link>
      <div className="page-head">
        <div><div className="row" style={{ gap: 12, flexWrap: "wrap" }}><h1>{p.titulo}</h1><Badge estado={p.estado} /></div>
          <p>{p.ubicacion_textual}, {p.ciudad_nombre} · Anfitrión: {nombres[p.anfitrion] ?? `#${p.anfitrion}`}</p></div>
      </div>
      {error && <Alert tipo="error">{error}</Alert>}
      {p.imagenes.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
          {p.imagenes.map((im) => <div key={im.orden} className="img-ph" style={{ height: 120 }}><img src={im.ruta} alt={`${p.titulo} ${im.orden}`} /></div>)}
        </div>
      )}
      <div className="detail-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,1.6fr) minmax(0,1fr)", gap: 20, alignItems: "start" }}>
        <section className="card stack">
          <p>{p.descripcion}</p>
          <div className="grid-2">
            <div><span className="subtle">Tipo</span><b style={{ display: "block" }}>{p.tipo_nombre}</b></div>
            <div><span className="subtle">Capacidad</span><b style={{ display: "block" }}>{p.capacidad} huéspedes</b></div>
            <div><span className="subtle">Precio por noche</span><b style={{ display: "block" }}>{pesos(p.precio_noche)}</b></div>
            <div><span className="subtle">Limpieza</span><b style={{ display: "block" }}>{pesos(p.tarifa_limpieza)}</b></div>
            <div><span className="subtle">Política</span><b style={{ display: "block" }}>{p.politica_nombre}</b></div>
            <div><span className="subtle">Descuento</span><b style={{ display: "block" }}>{p.descuento_porcentaje ? `${Number(p.descuento_porcentaje)} % desde ${p.descuento_min_noches} noches` : "Sin descuento"}</b></div>
          </div>
          <div className="chips">{p.servicios.map((s) => <span key={s.id} className="svc"><Check />{s.nombre}</span>)}</div>
          {p.servicios_adicionales.length > 0 && <p className="subtle">Adicionales: {p.servicios_adicionales.map((a) => `${a.nombre} (${pesos(a.precio)})`).join(" · ")}</p>}
          <h3>Reglas</h3>
          <ol className="reglas">{p.reglas.map((r) => <li key={r.orden}>{r.descripcion}</li>)}</ol>
        </section>
        <aside className="stack">
          <section className="card stack">
            <h3>Moderación</h3>
            {p.estado === "PENDIENTE_REVISION" ? (
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                <button className="btn btn-primary" disabled={enviando} onClick={() => revisar("APROBAR")}><Check /> Aprobar</button>
                <button className="btn btn-secondary" disabled={enviando} onClick={() => { setObs(""); setDevolver(true); }}><Undo2 /> Devolver</button>
              </div>
            ) : <AccionesPublicacion p={p} alCambiar={cargar} />}
          </section>
          <section className="card stack" style={{ gap: 8 }}>
            <h3 className="row" style={{ gap: 8 }}><History size={18} /> Historial de revisiones</h3>
            {p.revisiones.length === 0 ? <p className="subtle">Aún no tiene revisiones del administrador.</p> : (
              <ul className="list-plain historial">
                {p.revisiones.map((r, i) => (
                  <li key={i}><b>{ACCION_TXT[r.accion as AccionModeracion] ?? r.accion}</b>
                    <span className="subtle">{fechaHora(r.fecha)} · {nombres[r.administrador] ?? ""}</span>
                    {r.observacion && <span>«{r.observacion}»</span>}</li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
      {devolver && (
        <Modal onClose={() => setDevolver(false)}>
          <h2>Devolver al anfitrión</h2>
          <p className="muted">La publicación vuelve a BORRADOR y el anfitrión ve la observación.</p>
          <Field label="Observación" hint="Obligatoria.">
            <textarea className="textarea" placeholder="Ej. Las fotos no corresponden al alojamiento." value={obs} onChange={(e) => setObs(e.target.value)} />
          </Field>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setDevolver(false)}>Cancelar</button>
            <button className="btn btn-primary" disabled={!obs.trim() || enviando} onClick={() => revisar("DEVOLVER")}>Devolver</button>
          </div>
        </Modal>
      )}
    </Page>
  );
}

/* ---------------- HU-21 Usuarios: restringir y quitar la restricción ---------------- */
export function UsuariosAdmin() {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [rol, setRol] = useState<"" | Rol>("");
  const [lista, setLista] = useState<UsuarioAdmin[] | null>(null);
  const [error, setError] = useState("");
  const [restringir, setRestringir] = useState<UsuarioAdmin | null>(null);
  const [motivo, setMotivo] = useState("");
  const [hasta, setHasta] = useState("");
  const [errModal, setErrModal] = useState("");

  const ultima = useMemo(() => ({ n: 0 }), []);
  const cargar = useCallback(() => {
    const n = ++ultima.n;  // solo se pinta la respuesta de la última búsqueda
    adminApi.usuarios(rol, q).then((r) => { if (n === ultima.n) { setLista(r.data); setError(""); } })
      .catch((e) => { if (n === ultima.n) setError(leerError(e).error); });
  }, [rol, q, ultima]);
  useEffect(() => { const t = window.setTimeout(cargar, 250); return () => window.clearTimeout(t); }, [cargar]);

  const confirmar = async () => {
    if (!restringir) return;
    if (!motivo.trim()) return setErrModal("Escribe el motivo de la restricción.");
    try {
      // La fecha de fin es opcional: la restricción termina al final de ese día (hora de Colombia)
      await adminApi.restringir(restringir.id, motivo.trim(), hasta ? `${hasta}T23:59:00-05:00` : null);
      toast(`${restringir.nombre_completo} quedó restringido`);
      setRestringir(null); cargar();
    } catch (e) { setErrModal(leerError(e).error); }
  };
  const quitar = async (u: UsuarioAdmin) => {
    try { await adminApi.quitarRestriccion(u.id); toast(`Se quitó la restricción de ${u.nombre_completo}`); cargar(); }
    catch (e) { toast(leerError(e).error, "err"); }
  };
  const estado = (u: UsuarioAdmin) => (u.restringida ? "RESTRINGIDA" : u.activa ? "ACTIVA" : "DESACTIVADA");

  return (
    <Page req="RF-D-ADM-02.1 · HU-21">
      <div className="page-head"><div><h1>Usuarios</h1><p>Restringe una cuenta por incumplir las reglas o quita la restricción. Restringir no cambia sus reservas.</p></div></div>
      <div className="toolbar">
        <div className="search"><Search /><input className="input" placeholder="Buscar por nombre o correo" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select className="select" value={rol} onChange={(e) => setRol(e.target.value as Rol | "")} aria-label="Rol">
          <option value="">Rol: todos</option>{(Object.keys(ROL_TXT) as Rol[]).map((r) => <option key={r} value={r}>{ROL_TXT[r]}</option>)}
        </select>
      </div>
      {error && <Alert tipo="error">{error}</Alert>}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {lista && lista.length === 0 ? <div className="empty-state"><Users /><b>No hay usuarios con ese filtro</b></div> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Usuario</th><th>Rol</th><th>Estado</th><th>Acción</th></tr></thead>
              <tbody>
                {(lista ?? []).map((u) => (
                  <tr key={u.id}>
                    <td className="cell-2"><b>{u.nombre_completo}</b><span className="subtle">{u.correo}</span></td>
                    <td>{ROL_TXT[u.rol]}</td>
                    <td>
                      <span className={`badge ${estado(u) === "ACTIVA" ? "badge-ACTIVA" : estado(u) === "RESTRINGIDA" ? "badge-BLOQUEADA" : "badge-PAUSADA"}`}>{estado(u)}</span>
                      {u.motivo_restriccion && <span className="subtle" style={{ display: "block", marginTop: 4, maxWidth: 260 }}>
                        {u.motivo_restriccion}{u.restriccion_hasta ? ` · hasta ${new Date(u.restriccion_hasta).toLocaleDateString("es-CO")}` : ""}</span>}
                    </td>
                    <td>
                      {u.rol !== "ADMINISTRADOR" && (u.restringida
                        ? <button className="btn btn-secondary btn-sm" onClick={() => quitar(u)}><ShieldOff /> Quitar restricción</button>
                        : <button className="btn btn-danger btn-sm" onClick={() => { setMotivo(""); setHasta(""); setErrModal(""); setRestringir(u); }}><ShieldAlert /> Restringir</button>)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {restringir && (
        <Modal onClose={() => setRestringir(null)}>
          <span className="ico-big" style={{ background: "var(--err-soft)", color: "var(--err)" }}><ShieldAlert /></span>
          <h2>Restringir a {restringir.nombre_completo}</h2>
          <p className="muted">No podrá iniciar sesión y, si es anfitrión, sus publicaciones dejan de aparecer en las búsquedas.</p>
          <Field label="Motivo" error={errModal}><textarea className="textarea" value={motivo} onChange={(e) => setMotivo(e.target.value)} /></Field>
          <Field label="Hasta (opcional)" hint="Sin fecha, la restricción sigue hasta que la quites.">
            <input className="input" type="date" min={iso(new Date())} value={hasta} onChange={(e) => setHasta(e.target.value)} />
          </Field>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setRestringir(null)}>Cancelar</button>
            <button className="btn btn-primary" style={{ background: "var(--err)" }} onClick={confirmar}>Restringir</button>
          </div>
        </Modal>
      )}
    </Page>
  );
}

/* ---------------- HU-23 Registro de acciones ---------------- */
function sobreQue(e: EventoAuditoriaApi): string {
  const d = e.detalle ?? {};
  if (e.entidad) return `${e.entidad}${e.entidad_id ? ` #${e.entidad_id}` : ""}`;
  if (typeof d.ruta === "string") return d.ruta;
  if (typeof d.tipo === "string") return `Reporte ${d.tipo}`;
  return "—";
}

function detalleCorto(e: EventoAuditoriaApi): string {
  const d = e.detalle ?? {};
  const partes = ["motivo", "observacion", "valor_devolucion", "formato", "estado_pago", "correo"]
    .filter((k) => d[k] != null && d[k] !== "").map((k) => `${k.replace("_", " ")}: ${String(d[k])}`);
  if (typeof d.desde === "string" && typeof d.hasta === "string") partes.push(`periodo: ${d.desde} a ${d.hasta}`);
  return partes.join(" · ");
}

export function RegistroAcciones() {
  const [f, setF] = useState({ usuario: "", tipo: "", desde: "", hasta: "" });
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState<{ count: number; results: EventoAuditoriaApi[]; tipos: { clave: string; nombre: string }[] } | null>(null);
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { adminApi.usuarios().then((r) => setUsuarios(r.data)).catch(() => {}); }, []);
  useEffect(() => {
    let vigente = true;
    adminApi.auditoria({ usuario: f.usuario ? Number(f.usuario) : undefined, tipo: f.tipo || undefined, desde: f.desde || undefined,
      hasta: f.hasta || undefined, page: pagina })
      .then((r) => { if (vigente) { setDatos(r.data); setError(""); } })
      .catch((e) => { if (vigente) setError(leerError(e).error); });
    return () => { vigente = false; };
  }, [f, pagina]);
  const cambiar = (k: keyof typeof f, v: string) => { setPagina(1); setF({ ...f, [k]: v }); };
  const paginas = datos ? Math.max(1, Math.ceil(datos.count / 50)) : 1;

  return (
    <Page req="RF-D-ADM-04.1 · HU-23 · registro de solo inserción">
      <div className="page-head"><div><h1>Registro de acciones</h1><p>Quién hizo cada acción, sobre qué, cuándo y con qué resultado. Nadie puede modificarlo ni borrarlo.</p></div></div>
      <div className="toolbar" style={{ flexWrap: "wrap" }}>
        <select className="select" value={f.usuario} onChange={(e) => cambiar("usuario", e.target.value)} aria-label="Usuario">
          <option value="">Usuario: todos</option>{usuarios.map((u) => <option key={u.id} value={u.id}>{u.nombre_completo}</option>)}
        </select>
        <select className="select" value={f.tipo} onChange={(e) => cambiar("tipo", e.target.value)} aria-label="Tipo de acción">
          <option value="">Tipo de acción: todos</option>{(datos?.tipos ?? []).map((t) => <option key={t.clave} value={t.clave}>{t.nombre}</option>)}
        </select>
        <input className="input" type="date" aria-label="Desde" value={f.desde} onChange={(e) => cambiar("desde", e.target.value)} style={{ maxWidth: 170 }} />
        <input className="input" type="date" aria-label="Hasta" value={f.hasta} onChange={(e) => cambiar("hasta", e.target.value)} style={{ maxWidth: 170 }} />
      </div>
      {error && <Alert tipo="error">{error}</Alert>}
      <p className="muted">{datos ? `${datos.count} ${datos.count === 1 ? "acción" : "acciones"}` : "Cargando…"}</p>
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Fecha</th><th>Quién</th><th>Acción</th><th>Sobre qué</th><th>Resultado</th><th>Detalle</th></tr></thead>
            <tbody>
              {(datos?.results ?? []).map((e) => (
                <tr key={e.id}>
                  <td className="subtle" style={{ whiteSpace: "nowrap" }}>{fechaHora(e.fecha)}</td>
                  <td className="cell-2"><b>{e.actor_nombre ?? (e.actor_id ? `#${e.actor_id}` : "Sistema o visitante")}</b>{e.actor_correo && <span className="subtle">{e.actor_correo}</span>}</td>
                  <td>{e.accion}</td>
                  <td>{sobreQue(e)}</td>
                  <td><span className={`badge ${e.exitoso ? "badge-ACTIVA" : "badge-BLOQUEADA"}`}>{e.exitoso ? "ÉXITO" : "FALLO"}</span></td>
                  <td className="subtle" style={{ maxWidth: 320 }}>{detalleCorto(e)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {paginas > 1 && (
        <div className="row" style={{ gap: 8, justifyContent: "center" }}>
          <button className="btn btn-secondary btn-sm" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>Anterior</button>
          <span className="subtle">Página {pagina} de {paginas}</span>
          <button className="btn btn-secondary btn-sm" disabled={pagina >= paginas} onClick={() => setPagina(pagina + 1)}>Siguiente</button>
        </div>
      )}
    </Page>
  );
}

/* Historial local del prototipo: lo usa la pantalla del anfitrión, que aún no está conectada a la API. */
export const ACCION_TXT: Record<AccionModeracion, string> = {
  APROBAR: "Aprobada", DEVOLVER: "Devuelta", PAUSAR: "Pausada", REACTIVAR: "Reactivada", BLOQUEAR: "Bloqueada", DESBLOQUEAR: "Desbloqueada",
};

export function HistorialRevisiones({ pubId }: { pubId: number }) {
  const { revisionesDe, usuarios } = useStore();
  const lista = revisionesDe(pubId);
  return (
    <div className="stack" style={{ gap: 8 }}>
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}><History size={18} /> Historial de revisiones</h3>
      {lista.length === 0 ? <p className="subtle">Aún no tiene revisiones del administrador.</p> : (
        <ul className="list-plain historial">
          {lista.map((r) => (
            <li key={r.id}>
              <b>{ACCION_TXT[r.accion]}</b>
              <span className="subtle">
                {new Date(r.fecha).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" })} · {usuarios.find((u) => u.id === r.adminId)?.nombre}
              </span>
              {r.observacion && <span>«{r.observacion}»</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ---------------- HU-22 Tarifa de servicio ---------------- */
export function TarifaServicioPage() {
  const toast = useToast();
  const [datos, setDatos] = useState<{ porcentaje: string; historial: { porcentaje: string; vigente_desde: string; administrador: number }[] } | null>(null);
  const [nuevo, setNuevo] = useState("");
  const [error, setError] = useState("");
  const nombres = useNombres();
  const cargar = useCallback(() => {
    adminApi.tarifa().then((r) => { setDatos(r.data); setNuevo(String(Number(r.data.porcentaje))); }).catch((e) => setError(leerError(e).error));
  }, []);
  useEffect(cargar, [cargar]);

  const guardar = async () => {
    setError("");
    try { await adminApi.cambiarTarifa(nuevo); toast("Tarifa actualizada: aplica a las cotizaciones nuevas"); cargar(); }
    catch (e) { setError(leerError(e).error); }  // CA-22.2: fuera de 0 % a 30 %
  };

  return (
    <Page req="RF-D-ADM-03.1 · HU-22">
      <div className="page-head"><div><h1>Tarifa de servicio</h1><p>Porcentaje que cobra la plataforma sobre el precio de la estancia. Solo cambia las cotizaciones nuevas.</p></div></div>
      <div className="detail-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1.4fr)", gap: 20, alignItems: "start" }}>
        <section className="card stack">
          <div className="card-title"><span className="ico"><Percent /></span><h3>Tarifa vigente: {datos ? `${Number(datos.porcentaje)} %` : "…"}</h3></div>
          <Field label="Nuevo porcentaje" hint="Entre 0 % y 30 %." error={error}>
            <input className="input" type="number" step="0.5" min={0} max={30} value={nuevo} onChange={(e) => setNuevo(e.target.value)} />
          </Field>
          <button className="btn btn-primary" disabled={!datos || nuevo === "" || Number(nuevo) === Number(datos?.porcentaje)} onClick={guardar}>Guardar</button>
          <Alert tipo="info">Las reservas ya confirmadas conservan los valores con los que se cotizaron (CA-22.1).</Alert>
        </section>
        <section className="card stack">
          <h3 className="row" style={{ gap: 8 }}><History size={18} /> Historial</h3>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Porcentaje</th><th>Vigente desde</th><th>Administrador</th></tr></thead>
              <tbody>
                {(datos?.historial ?? []).map((t) => (
                  <tr key={t.vigente_desde}><td><b>{Number(t.porcentaje)} %</b></td><td>{fechaHora(t.vigente_desde)}</td><td>{nombres[t.administrador] ?? `#${t.administrador}`}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Page>
  );
}

/* ---------------- HU-24 Tablero (RF-D-ADM-05.1) ---------------- */
export function periodosRapidos(): { nombre: string; desde: string; hasta: string }[] {
  const hoy = new Date();
  const mes = (y: number, m: number) => ({ desde: iso(new Date(y, m, 1)), hasta: iso(new Date(y, m + 1, 0)) });
  return [
    { nombre: "Este mes", ...mes(hoy.getFullYear(), hoy.getMonth()) },
    { nombre: "Mes anterior", ...mes(hoy.getFullYear(), hoy.getMonth() - 1) },
    { nombre: "Año en curso", desde: iso(new Date(hoy.getFullYear(), 0, 1)), hasta: iso(new Date(hoy.getFullYear(), 11, 31)) },
  ];
}

export function SelectorPeriodo({ desde, hasta, onCambio }: { desde: string; hasta: string; onCambio: (desde: string, hasta: string) => void }) {
  return (
    <div className="toolbar" style={{ flexWrap: "wrap" }}>
      <Field label="Desde"><input className="input" type="date" value={desde} onChange={(e) => onCambio(e.target.value, hasta)} /></Field>
      <Field label="Hasta"><input className="input" type="date" value={hasta} onChange={(e) => onCambio(desde, e.target.value)} /></Field>
      <div className="row" style={{ gap: 6, flexWrap: "wrap", alignSelf: "flex-end" }}>
        {periodosRapidos().map((p) => (
          <button key={p.nombre} className={`btn btn-sm ${p.desde === desde && p.hasta === hasta ? "btn-primary" : "btn-secondary"}`} onClick={() => onCambio(p.desde, p.hasta)}>{p.nombre}</button>
        ))}
      </div>
    </div>
  );
}

const ESTADOS_RESERVA: [string, string, string][] = [
  ["CONFIRMADA", "#dcf3e4", "#166534"], ["EN_REVISION", "#e3ecfa", "#1e4a8a"], ["COMPLETADA", "#fdf0c8", "#8a4b05"], ["CANCELADA", "#fbe1de", "#9b1c12"],
];

export function Tablero() {
  const inicial = periodosRapidos()[0]!;
  const [p, setP] = useState({ desde: inicial.desde, hasta: inicial.hasta });
  const [t, setT] = useState<TableroApi | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!p.desde || !p.hasta) return;
    let vigente = true;  // si el periodo cambia antes de que llegue la respuesta, se descarta la vieja
    adminApi.tablero(p.desde, p.hasta)
      .then((r) => { if (vigente) { setT(r.data); setError(""); } })
      .catch((e) => { if (vigente) { setT(null); setError(leerError(e).error); } });
    return () => { vigente = false; };
  }, [p]);
  const maxCiudad = useMemo(() => Math.max(1, ...(t?.top_ciudades ?? []).map((c) => c.reservas)), [t]);

  return (
    <Page req="RF-D-ADM-05.1 · HU-24 · una reserva cuenta en el periodo según su fecha de creación">
      <div className="page-head"><div><h1>Tablero</h1><p>Indicadores del periodo. Los reportes descargables usan las mismas cifras.</p></div></div>
      <SelectorPeriodo desde={p.desde} hasta={p.hasta} onCambio={(desde, hasta) => setP({ desde, hasta })} />
      {error && <Alert tipo="error">{error}</Alert>}
      {t && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 14 }}>
            <Stat icon={BarChart3} v={pesos(t.ingresos.bruto)} label="Monto bruto de reservas" bg="#dcf3e4" fg="#166534" />
            <Stat icon={Percent} v={pesos(t.ingresos.plataforma)} label="Ingreso de la plataforma" bg="#e3ecfa" fg="#1e4a8a" />
            <Stat icon={CheckCircle2} v={t.publicaciones_activas} label="Publicaciones ACTIVAS" bg="#fdf0c8" fg="#8a4b05" />
            <Stat icon={ClipboardList} v={t.reservas_total} label="Reservas creadas" bg="#f1f1ef" fg="#57534e" />
          </div>
          <div className="detail-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 20, alignItems: "start" }}>
            <section className="card stack">
              <h3>Reservas por estado</h3>
              <ul className="list-plain stack" style={{ gap: 8 }}>
                {ESTADOS_RESERVA.map(([e, bg, fg]) => (
                  <li key={e} className="row-between"><span className="badge" style={{ background: bg, color: fg }}>{e.replace("_", " ")}</span><b>{t.reservas_por_estado[e] ?? 0}</b></li>
                ))}
              </ul>
            </section>
            <section className="card stack">
              <h3>Usuarios por rol</h3>
              <ul className="list-plain stack" style={{ gap: 8 }}>
                {(Object.keys(ROL_TXT) as Rol[]).map((r) => <li key={r} className="row-between"><span>{ROL_TXT[r]}</span><b>{t.usuarios_por_rol[r] ?? 0}</b></li>)}
              </ul>
            </section>
            <section className="card stack">
              <h3>Las 5 ciudades con más reservas</h3>
              {t.top_ciudades.length === 0 ? <p className="muted">Sin reservas en el periodo.</p> : (
                <ol className="list-plain stack" style={{ gap: 10 }}>
                  {t.top_ciudades.map((c) => (
                    <li key={c.ciudad} className="stack" style={{ gap: 4 }}>
                      <div className="row-between"><b>{c.ciudad}</b><span className="subtle">{c.reservas} · {pesos(c.monto_bruto)}</span></div>
                      <div style={{ height: 8, borderRadius: 999, background: "var(--accent-soft)" }}>
                        <div style={{ width: `${(c.reservas / maxCiudad) * 100}%`, height: "100%", borderRadius: 999, background: "var(--accent)" }} />
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        </>
      )}
    </Page>
  );
}
