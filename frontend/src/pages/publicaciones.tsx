import {
  ArrowLeft, CalendarDays, Check, CheckCircle2, CircleDashed, ClipboardList, Eye, FileEdit, Home, ImagePlus,
  Lock, PauseCircle, PlayCircle, Plus, Search, Send, Sparkles, Trash2, Upload,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  CIUDADES, PALETA, POLITICA_MODERADA, SERVICIOS, TIPOS, cop, faltantesRevision, fechaLarga,
  type Adicional, type EstadoPub, type Publicacion,
} from "../data";
import { Denegado, Page } from "../layout";
import { useStore, useToast } from "../store";
import { Alert, Badge, Field, ImageTile, Modal } from "../ui";

/* =========================================================
   CU-ALO-03 Consultar mis publicaciones
   ========================================================= */
export function MisPublicaciones() {
  const { usuario, publicaciones } = useStore();
  const go = useNavigate();
  const [q, setQ] = useState("");
  const [estado, setEstado] = useState<"" | EstadoPub>("");
  const [tipo, setTipo] = useState("");
  const mias = publicaciones.filter((p) => p.anfitrionId === usuario!.id);
  const lista = mias.filter((p) =>
    (!q || (p.titulo + " " + p.ciudad).toLowerCase().includes(q.toLowerCase())) &&
    (!estado || p.estado === estado) && (!tipo || p.tipo === tipo));
  const n = (e: EstadoPub) => mias.filter((p) => p.estado === e).length;
  const devueltas = mias.filter((p) => p.estado === "BORRADOR" && p.observacion);

  const stats = [
    { label: "Activas", v: n("ACTIVA"), icon: CheckCircle2, bg: "#dcf3e4", fg: "#166534" },
    { label: "En revisión", v: n("PENDIENTE_REVISION"), icon: ClipboardList, bg: "#fdf0c8", fg: "#8a4b05" },
    { label: "Pausadas", v: n("PAUSADA"), icon: PauseCircle, bg: "#e3ecfa", fg: "#1e4a8a" },
    { label: "Borradores", v: n("BORRADOR"), icon: CircleDashed, bg: "#eceeed", fg: "#48514f" },
  ];

  return (
    <Page req="RF-D-ALO-02.1 · CU-ALO-03 · solo ves y modificas tus propios alojamientos">
      <div className="page-head">
        <div><h1>Mis publicaciones</h1><p>Tus alojamientos y el estado de cada uno.</p></div>
        <Link className="btn btn-primary" to="/publicaciones/nueva"><Plus /> Nueva publicación</Link>
      </div>

      <div className="grid-4">
        {stats.map((s) => (
          <div key={s.label} className="card card-tight stat">
            <span className="ico" style={{ background: s.bg, color: s.fg }}><s.icon /></span>
            <div><b>{s.v}</b><span>{s.label}</span></div>
          </div>
        ))}
      </div>

      {devueltas.map((p) => (
        <Alert key={p.id} tipo="info">
          <b>{p.titulo}</b> fue devuelta por el administrador: «{p.observacion}»{" "}
          <Link to={`/publicaciones/${p.id}/editar`}>Corregir</Link>
        </Alert>
      ))}

      <div className="toolbar">
        <div className="search"><Search /><input className="input" placeholder="Buscar por título o ciudad" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select className="select" value={estado} onChange={(e) => setEstado(e.target.value as EstadoPub | "")}>
          <option value="">Estado: todos</option>
          {(["ACTIVA", "PENDIENTE_REVISION", "PAUSADA", "BORRADOR", "BLOQUEADA"] as EstadoPub[]).map((e) => <option key={e} value={e}>{e}</option>)}
        </select>
        <select className="select" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          <option value="">Tipo: todos</option>
          {TIPOS.map((t) => <option key={t}>{t}</option>)}
        </select>
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {lista.length === 0 ? (
          <div className="empty-state"><Home /><b>No hay publicaciones con esos filtros</b>
            <Link className="btn btn-secondary btn-sm" to="/publicaciones/nueva"><Plus /> Crear una</Link></div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Publicación</th><th>Tipo</th><th>Precio / noche</th><th>Estado</th><th>Actualizada</th></tr></thead>
              <tbody>
                {lista.map((p) => (
                  <tr key={p.id} className="clickable" onClick={() => go(`/publicaciones/${p.id}`)}>
                    <td>
                      <div className="pub-cell">
                        <ImageTile img={p.imagenes[0]} style={{ width: 52, height: 40, borderRadius: 8 }} />
                        <div><Link to={`/publicaciones/${p.id}`} onClick={(e) => e.stopPropagation()}>{p.titulo}</Link><span className="subtle">{p.ciudad || "Sin ciudad"}</span></div>
                      </div>
                    </td>
                    <td>{p.tipo || "—"}</td>
                    <td>{cop(p.precioNoche)}</td>
                    <td><Badge estado={p.estado} /></td>
                    <td className="muted">{fechaLarga(p.actualizada)}</td>
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

/* =========================================================
   Detalle de una publicación del anfitrión, con sus acciones por estado
   CU-ALO-02 Enviar a revisión · CU-ALO-05 Pausar o reactivar
   ========================================================= */
export function DetallePublicacion() {
  const { id } = useParams();
  const { usuario, publicaciones, reservasConfirmadas, enviarARevision, cambiarEstado, usuarios } = useStore();
  const toast = useToast();
  const go = useNavigate();
  const [modal, setModal] = useState<null | "pausar" | "reactivar" | { faltan: string[] }>(null);
  const p = publicaciones.find((x) => x.id === Number(id));
  const esAdmin = usuario!.rol === "ADMINISTRADOR";

  if (!p || (!esAdmin && p.anfitrionId !== usuario!.id))
    return <Denegado titulo="No puedes ver esta publicación" texto="Solo el anfitrión dueño o un administrador pueden abrirla." />;

  const reservas = reservasConfirmadas(p.id);
  const anfitrion = usuarios.find((u) => u.id === p.anfitrionId);
  const editable = ["BORRADOR", "ACTIVA", "PAUSADA"].includes(p.estado) || esAdmin;
  const volver = esAdmin ? "/admin/publicaciones" : "/publicaciones";

  const enviar = () => {
    const faltan = faltantesRevision(p);
    if (faltan.length) return setModal({ faltan });
    enviarARevision(p.id);
    toast("Publicación enviada a revisión");
  };

  return (
    <Page req="RF-D-ALO-02.1 · CU-ALO-02 · CU-ALO-05">
      <div>
        <Link to={volver} className="back"><ArrowLeft /> {esAdmin ? "Todas las publicaciones" : "Mis publicaciones"}</Link>
        <div className="page-head">
          <div className="row" style={{ gap: 12 }}><h1>{p.titulo}</h1><Badge estado={p.estado} /></div>
          <div className="row">
            {p.estado === "ACTIVA" && <button className="btn btn-secondary" onClick={() => setModal("pausar")}><PauseCircle /> Pausar</button>}
            {p.estado === "PAUSADA" && <button className="btn btn-secondary" onClick={() => setModal("reactivar")}><PlayCircle /> Reactivar</button>}
            {p.anfitrionId === usuario!.id && ["ACTIVA", "PAUSADA", "BORRADOR"].includes(p.estado) &&
              <Link className="btn btn-secondary" to={`/calendario?pub=${p.id}`}><CalendarDays /> Calendario</Link>}
            {editable && <Link className={`btn ${p.estado === "BORRADOR" ? "btn-secondary" : "btn-primary"}`} to={`/publicaciones/${p.id}/editar`}><FileEdit /> Editar</Link>}
            {p.estado === "BORRADOR" && <button className="btn btn-primary" onClick={enviar}><Send /> Enviar a revisión</button>}
          </div>
        </div>
      </div>

      {p.estado === "BORRADOR" && p.observacion && <Alert tipo="info"><b>Observación del administrador:</b> «{p.observacion}»</Alert>}
      {p.estado === "PENDIENTE_REVISION" && <Alert tipo="warn">En revisión: el administrador la aprobará o la devolverá con observaciones. Mientras tanto no aparece en las búsquedas.</Alert>}
      {p.estado === "BLOQUEADA" && <Alert tipo="error"><b>Bloqueada por moderación:</b> {p.motivoBloqueo} Solo un administrador puede desbloquearla.</Alert>}
      {p.estado === "PAUSADA" && <Alert tipo="info">Pausada: no aparece en las búsquedas ni recibe reservas nuevas. Las reservas confirmadas se mantienen.</Alert>}

      <div className="card card-tight">
        <div className="kv">
          {esAdmin && <div><span>Anfitrión</span><b>{anfitrion?.nombre}</b></div>}
          <div><span>Ciudad</span><b>{p.ciudad || "—"}</b></div>
          <div><span>Tipo</span><b>{p.tipo || "—"}</b></div>
          <div><span>Capacidad</span><b>{p.capacidad ? `${p.capacidad} huéspedes` : "—"}</b></div>
          <div><span>Precio por noche</span><b>{cop(p.precioNoche)}</b></div>
          <div><span>Limpieza</span><b>{cop(p.limpieza)}</b></div>
          <div><span>Descuento</span><b>{p.descuentoPct ? `${p.descuentoPct} % desde ${p.descuentoNoches} noches` : "Sin descuento"}</b></div>
        </div>
      </div>

      <div className="grid-3">
        <section className="card stack">
          <h3>Servicios incluidos</h3>
          <div className="chips">{p.servicios.length ? p.servicios.map((s) => <span key={s} className="svc"><Check />{s}</span>) : <span className="muted">Ninguno</span>}</div>
          <h3>Servicios adicionales</h3>
          {p.adicionales.length ? (
            <ul className="list-plain">{p.adicionales.map((a) => <li key={a.nombre} className="row-between" style={{ display: "flex" }}><span>{a.nombre}</span><b>{cop(a.precio)}</b></li>)}</ul>
          ) : <span className="muted">Ninguno</span>}
        </section>
        <section className="card stack">
          <h3>Reglas y política</h3>
          <p>{p.reglas || <span className="muted">Sin reglas</span>}</p>
          <p className="muted">{p.ubicacion}</p>
          <div><span className="label">Política de cancelación: </span><b>{p.politica || "Sin elegir"}</b></div>
          {p.politica && <ul className="list-plain subtle">{POLITICA_MODERADA.map((t) => <li key={t.tramo}>{t.devolucion} · {t.tramo}</li>)}</ul>}
        </section>
        <section className="card stack">
          <h3>Imágenes ({p.imagenes.length})</h3>
          {p.imagenes.length ? (
            <div className="img-grid">{p.imagenes.map((im, i) => <ImageTile key={im.id} img={im} etiqueta={i === 0 ? "Portada" : im.nombre} />)}</div>
          ) : <Alert tipo="warn">Falta al menos una imagen para enviar a revisión.</Alert>}
        </section>
      </div>

      <section className="card stack">
        <div className="card-head" style={{ margin: 0 }}>
          <h3>Reservas confirmadas</h3>
          <span className="role-pill">{reservas.length}</span>
        </div>
        {reservas.length ? (
          <ul className="list-plain">
            {reservas.map((r) => (
              <li key={r.id}><CalendarDays color="var(--brand-700)" />{fechaLarga(r.llegada)} al {fechaLarga(r.salida)} · {usuarios.find((u) => u.id === r.huespedId)?.nombre}</li>
            ))}
          </ul>
        ) : <p className="muted">No tiene reservas confirmadas.</p>}
        <p className="subtle">Los cambios de precio o de política no afectan las reservas ya confirmadas.</p>
      </section>

      {modal === "pausar" && (
        <Modal onClose={() => setModal(null)}>
          <span className="ico-big" style={{ background: "#e3ecfa", color: "#1e4a8a" }}><PauseCircle /></span>
          <h2>¿Pausar «{p.titulo}»?</h2>
          <div className="row"><Badge estado="ACTIVA" /><span>→</span><Badge estado="PAUSADA" /></div>
          <p className="muted">No aparecerá en las búsquedas ni recibirá reservas nuevas.</p>
          {reservas.length > 0 && <Alert tipo="ok">Tus {reservas.length} reservas confirmadas se mantienen igual.</Alert>}
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setModal(null)}>Cancelar</button>
            <button className="btn btn-primary" onClick={() => { cambiarEstado(p.id, "PAUSADA"); setModal(null); toast("Publicación pausada"); }}>Pausar publicación</button>
          </div>
        </Modal>
      )}
      {modal === "reactivar" && (
        <Modal onClose={() => setModal(null)}>
          <span className="ico-big" style={{ background: "#dcf3e4", color: "#166534" }}><PlayCircle /></span>
          <h2>¿Reactivar «{p.titulo}»?</h2>
          <div className="row"><Badge estado="PAUSADA" /><span>→</span><Badge estado="ACTIVA" /></div>
          <p className="muted">Vuelve a aparecer en las búsquedas y a recibir reservas.</p>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setModal(null)}>Cancelar</button>
            <button className="btn btn-primary" onClick={() => { cambiarEstado(p.id, "ACTIVA"); setModal(null); toast("Publicación activa de nuevo"); }}>Reactivar</button>
          </div>
        </Modal>
      )}
      {modal && typeof modal === "object" && (
        <Modal onClose={() => setModal(null)}>
          <span className="ico-big" style={{ background: "var(--err-soft)", color: "var(--err)" }}><Send /></span>
          <h2>Aún no se puede enviar a revisión</h2>
          <p className="muted">La publicación sigue en BORRADOR. Completa lo siguiente:</p>
          <ul className="list-plain">{modal.faltan.map((f) => <li key={f}><CircleDashed color="var(--err)" />{f[0]!.toUpperCase() + f.slice(1)}</li>)}</ul>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setModal(null)}>Cerrar</button>
            <button className="btn btn-primary" onClick={() => go(`/publicaciones/${p.id}/editar`)}>Completar datos</button>
          </div>
        </Modal>
      )}
    </Page>
  );
}

/* =========================================================
   CU-ALO-01 Crear publicación · CU-ALO-04 Editar publicación
   ========================================================= */
const vacia = (anfitrionId: number): Publicacion => ({
  id: 0, anfitrionId, titulo: "", descripcion: "", tipo: "", ciudad: "", ubicacion: "", capacidad: null,
  precioNoche: null, limpieza: null, descuentoPct: null, descuentoNoches: null, servicios: [], adicionales: [],
  reglas: "", imagenes: [], politica: "", estado: "BORRADOR", bloqueos: [], actualizada: "",
});

const num = (v: string) => (v.trim() === "" ? null : Number(v.replace(/\D/g, "")));

export function FormPublicacion() {
  const { id } = useParams();
  const { usuario, publicaciones, guardarPublicacion, enviarARevision, reservasConfirmadas } = useStore();
  const toast = useToast();
  const go = useNavigate();
  const existente = id ? publicaciones.find((x) => x.id === Number(id)) : undefined;
  const [p, setP] = useState<Publicacion>(() => existente ? structuredClone(existente) : vacia(usuario!.id));
  const [paso, setPaso] = useState<1 | 2>(1);
  const [err, setErr] = useState<Record<string, string>>({});
  const [faltan, setFaltan] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const set = <K extends keyof Publicacion>(k: K, v: Publicacion[K]) => setP((x) => ({ ...x, [k]: v }));
  const nReservas = useMemo(() => (existente ? reservasConfirmadas(existente.id).length : 0), [existente, reservasConfirmadas]);

  if (id && (!existente || (usuario!.rol !== "ADMINISTRADOR" && existente.anfitrionId !== usuario!.id)))
    return <Denegado titulo="No puedes editar esta publicación" texto="Solo el anfitrión dueño o un administrador pueden modificarla (CA-05.3)." />;

  const validarPaso1 = () => {
    const e: Record<string, string> = {};
    if (!p.titulo.trim()) e.titulo = "Escribe un título.";
    if (p.capacidad !== null && p.capacidad <= 0) e.capacidad = "Debe ser mayor que cero.";
    return e;
  };
  const validarPaso2 = () => {
    const e: Record<string, string> = {};
    if (p.precioNoche !== null && p.precioNoche <= 0) e.precioNoche = "Debe ser mayor que cero.";
    if ((p.descuentoPct == null) !== (p.descuentoNoches == null)) e.descuento = "Indica el porcentaje y desde cuántas noches, o deja ambos vacíos.";
    if (p.descuentoPct != null && (p.descuentoPct <= 0 || p.descuentoPct > 100)) e.descuento = "El descuento debe estar entre 1 y 100 %.";
    if (p.descuentoNoches != null && p.descuentoNoches < 2) e.descuento = "El descuento aplica desde 2 noches o más.";
    if (p.adicionales.some((a) => !a.nombre.trim())) e.adicionales = "Cada servicio adicional necesita un nombre.";
    return e;
  };

  const guardar = (enviar: boolean) => {
    const e = { ...validarPaso1(), ...validarPaso2() };
    setErr(e);
    if (Object.keys(e).length) {
      if (validarPaso1().titulo || validarPaso1().capacidad) setPaso(1);
      return;
    }
    const g = guardarPublicacion(p);
    if (!enviar) {
      toast(existente ? "Cambios guardados" : "Publicación guardada como BORRADOR");
      return go(`/publicaciones/${g.id}`);
    }
    const f = faltantesRevision(g);
    if (f.length) { setFaltan(f); setP(g); return; }
    enviarARevision(g.id, g);
    toast("Publicación enviada a revisión");
    go(`/publicaciones/${g.id}`);
  };

  const subir = (files: FileList | null) => {
    if (!files) return;
    Array.from(files).forEach((file) => {
      const r = new FileReader();
      r.onload = () => setP((x) => ({
        ...x,
        imagenes: [...x.imagenes, { id: crypto.randomUUID(), nombre: file.name.replace(/\.\w+$/, ""), color: PALETA[x.imagenes.length % PALETA.length]!, src: String(r.result) }],
      }));
      r.readAsDataURL(file);
    });
  };
  const ejemplo = () => {
    const nombres = ["Sala", "Habitación", "Cocina", "Baño", "Fachada", "Vista"];
    set("imagenes", [...p.imagenes, { id: crypto.randomUUID(), nombre: nombres[p.imagenes.length % nombres.length]!, color: PALETA[p.imagenes.length % PALETA.length]! }]);
  };

  const enEdicionActiva = existente && existente.estado !== "BORRADOR";

  return (
    <Page req={existente ? "RF-D-ALO-02.1 · CU-ALO-04 · editar una publicación ACTIVA no la devuelve a revisión" : "RF-D-ALO-01.1 · CU-ALO-01 · queda en BORRADOR"}>
      <div>
        <Link to={existente ? `/publicaciones/${existente.id}` : "/publicaciones"} className="back"><ArrowLeft /> {existente ? "Volver al detalle" : "Mis publicaciones"}</Link>
        <div className="page-head">
          <div className="row" style={{ gap: 12 }}>
            <h1>{existente ? "Editar publicación" : "Nueva publicación"}</h1>
            <Badge estado={p.estado} />
          </div>
        </div>
      </div>

      <div className="steps" role="tablist">
        <button className={`step ${paso === 1 ? "on" : "done"}`} onClick={() => setPaso(1)} role="tab" aria-selected={paso === 1}>
          <i>{paso === 1 ? "1" : <Check />}</i>Información general
        </button>
        <button className={`step ${paso === 2 ? "on" : ""}`} role="tab" aria-selected={paso === 2}
          onClick={() => { const e = validarPaso1(); setErr(e); if (!Object.keys(e).length) setPaso(2); }}>
          <i>2</i>Precios, servicios e imágenes
        </button>
      </div>

      {enEdicionActiva && (
        <Alert tipo="info">
          La publicación sigue {existente!.estado}, sin volver a revisión.
          {nReservas > 0 && ` Los cambios de precio o de política no afectan sus ${nReservas} reservas confirmadas.`}
        </Alert>
      )}
      {faltan.length > 0 && (
        <Alert tipo="error"><b>No se puede enviar a revisión.</b> Falta: {faltan.join(", ")}. Se guardó como BORRADOR.</Alert>
      )}

      {paso === 1 ? (
        <section className="card stack">
          <Field label="Título" error={err.titulo}>
            <input className="input" placeholder="Ej. Casa familiar en Villa de Leyva" value={p.titulo} onChange={(e) => set("titulo", e.target.value)} />
          </Field>
          <Field label="Descripción">
            <textarea className="textarea" placeholder="Cuenta cómo es el alojamiento y qué lo hace especial." value={p.descripcion} onChange={(e) => set("descripcion", e.target.value)} />
          </Field>
          <div className="grid-3">
            <Field label="Tipo de alojamiento">
              <select className="select" value={p.tipo} onChange={(e) => set("tipo", e.target.value as Publicacion["tipo"])}>
                <option value="">Selecciona</option>{TIPOS.map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Capacidad (huéspedes)" error={err.capacidad}>
              <input className="input" inputMode="numeric" placeholder="Mayor que 0" value={p.capacidad ?? ""} onChange={(e) => set("capacidad", num(e.target.value))} />
            </Field>
            <Field label="Ciudad">
              <select className="select" value={p.ciudad} onChange={(e) => set("ciudad", e.target.value)}>
                <option value="">Selecciona</option>{CIUDADES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
          </div>
          <Field label="Ubicación" hint="Dirección o referencia en texto.">
            <input className="input" placeholder="Ej. Vereda El Roble, a 5 min de la plaza" value={p.ubicacion} onChange={(e) => set("ubicacion", e.target.value)} />
          </Field>
          <Field label="Reglas del alojamiento">
            <textarea className="textarea" style={{ minHeight: 72 }} placeholder="Ej. No fumar. Sin fiestas. Silencio después de las 10 p. m." value={p.reglas} onChange={(e) => set("reglas", e.target.value)} />
          </Field>
          <div className="row">
            <Link className="btn btn-ghost" to="/publicaciones">Cancelar</Link>
            <button className="btn btn-secondary right" onClick={() => guardar(false)}>Guardar borrador</button>
            <button className="btn btn-primary" onClick={() => { const e = validarPaso1(); setErr(e); if (!Object.keys(e).length) setPaso(2); }}>Siguiente</button>
          </div>
        </section>
      ) : (
        <>
          <div className="form-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr)", gap: 20 }}>
            <section className="card stack">
              <h3>Precios</h3>
              <div className="grid-2">
                <Field label="Precio por noche (COP)" error={err.precioNoche}>
                  <div className="input-prefix"><span>$</span><input className="input" inputMode="numeric" placeholder="Mayor que 0" value={p.precioNoche ?? ""} onChange={(e) => set("precioNoche", num(e.target.value))} /></div>
                </Field>
                <Field label="Tarifa de limpieza (COP)">
                  <div className="input-prefix"><span>$</span><input className="input" inputMode="numeric" placeholder="0" value={p.limpieza ?? ""} onChange={(e) => set("limpieza", num(e.target.value))} /></div>
                </Field>
                <Field label="Descuento (%)" opcional error={err.descuento} hint="Por estancia larga.">
                  <input className="input" inputMode="numeric" placeholder="Ej. 10" value={p.descuentoPct ?? ""} onChange={(e) => set("descuentoPct", num(e.target.value))} />
                </Field>
                <Field label="Desde cuántas noches" opcional>
                  <input className="input" inputMode="numeric" placeholder="Ej. 7" value={p.descuentoNoches ?? ""} onChange={(e) => set("descuentoNoches", num(e.target.value))} />
                </Field>
              </div>
              <p className="subtle">La tarifa de servicio de la plataforma la fija el administrador y se suma en la cotización del huésped.</p>
              <Field label="Política de cancelación" hint="En el MVP la única política disponible es la Moderada.">
                <select className="select" value={p.politica} onChange={(e) => set("politica", e.target.value as Publicacion["politica"])}>
                  <option value="">Selecciona una política</option><option value="Moderada">Moderada</option>
                </select>
              </Field>
              {p.politica && (
                <div className="card card-tight" style={{ boxShadow: "none", background: "var(--brand-50)" }}>
                  <ul className="list-plain">{POLITICA_MODERADA.map((t) => <li key={t.tramo}><b style={{ width: 52 }}>{t.devolucion}</b><span>{t.tramo}</span></li>)}</ul>
                </div>
              )}
            </section>

            <section className="card stack">
              <h3>Servicios incluidos <span className="subtle">(sin costo)</span></h3>
              <div className="chips">
                {SERVICIOS.map((s) => {
                  const on = p.servicios.includes(s);
                  return (
                    <button key={s} type="button" className={`chip-toggle ${on ? "on" : ""}`} aria-pressed={on}
                      onClick={() => set("servicios", on ? p.servicios.filter((x) => x !== s) : [...p.servicios, s])}>
                      {on && <Check />}{s}
                    </button>
                  );
                })}
              </div>
              <h3>Servicios adicionales <span className="subtle">(se cobran aparte)</span></h3>
              {p.adicionales.map((a, i) => (
                <div className="addon-row" key={i}>
                  <input className="input" placeholder="Ej. Desayuno" value={a.nombre} onChange={(e) => set("adicionales", p.adicionales.map((x, j): Adicional => j === i ? { ...x, nombre: e.target.value } : x))} />
                  <div className="input-prefix"><span>$</span><input className="input" inputMode="numeric" value={a.precio || ""} placeholder="0" onChange={(e) => set("adicionales", p.adicionales.map((x, j): Adicional => j === i ? { ...x, precio: num(e.target.value) ?? 0 } : x))} /></div>
                  <button type="button" className="icon-btn" aria-label="Quitar servicio" onClick={() => set("adicionales", p.adicionales.filter((_, j) => j !== i))}><Trash2 /></button>
                </div>
              ))}
              {err.adicionales && <span className="error-text">{err.adicionales}</span>}
              <button type="button" className="link-btn" style={{ alignSelf: "flex-start" }} onClick={() => set("adicionales", [...p.adicionales, { nombre: "", precio: 0 }])}>
                + Agregar servicio adicional
              </button>
            </section>
          </div>

          <section className="card stack">
            <div className="row-between">
              <h3>Imágenes <span className="subtle">(mínimo una; la primera es la portada)</span></h3>
              <button type="button" className="btn btn-ghost btn-sm" onClick={ejemplo}><Sparkles /> Agregar imagen de ejemplo</button>
            </div>
            <div className="img-grid">
              {p.imagenes.map((im, i) => (
                <ImageTile key={im.id} img={im} etiqueta={i === 0 ? "Portada" : im.nombre}
                  onRemove={() => set("imagenes", p.imagenes.filter((x) => x.id !== im.id))} />
              ))}
              <button type="button" className="img-add" onClick={() => fileRef.current?.click()}>
                <span style={{ display: "grid", placeItems: "center", gap: 4 }}>{p.imagenes.length ? <ImagePlus /> : <Upload />}Subir imagen</span>
              </button>
              <input ref={fileRef} type="file" accept="image/*" multiple hidden onChange={(e) => { subir(e.target.files); e.target.value = ""; }} />
            </div>
          </section>

          <div className="row">
            <button className="btn btn-ghost" onClick={() => setPaso(1)}><ArrowLeft /> Paso anterior</button>
            <button className="btn btn-secondary right" onClick={() => guardar(false)}>{p.estado === "BORRADOR" ? "Guardar borrador" : "Guardar cambios"}</button>
            {p.estado === "BORRADOR" && <button className="btn btn-primary" onClick={() => guardar(true)}><Send /> Enviar a revisión</button>}
          </div>
        </>
      )}
      <p className="subtle" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><Eye size={14} /> Los datos se guardan solo en este navegador (prototipo).</p>
    </Page>
  );
}


/** Reinicia el formulario al pasar de una publicación a otra. */
export function FormPublicacionRuta() {
  const { id } = useParams();
  return <FormPublicacion key={id ?? "nueva"} />;
}
