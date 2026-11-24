import {
  ArrowLeft, CalendarDays, Check, CheckCircle2, CircleDashed, ClipboardList, FileEdit, Home, ImagePlus,
  PauseCircle, PlayCircle, Plus, Search, Send, Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { isAxiosError } from "axios";
import {
  anfitrionApi, catalogoApi, leerError, misReservasApi, textoTramo,
  type ItemCatalogo, type PoliticaApi, type PublicacionAdmin, type PublicacionCompleta, type PublicacionEntrada, type ReservaResumen,
} from "../api";
import { ESTADO_TXT, cop, fechaLarga, imagenDe, type EstadoPub } from "../data";
import { HistorialRevisiones } from "./admin";
import { Denegado, Page } from "../layout";
import { useStore, useToast } from "../store";
import { Alert, Badge, Field, ImageTile, Modal } from "../ui";

/** Datos que faltan para enviar a revisión: la API los manda en `faltantes` (RF-D-ALO-01.2). */
const faltantesDe = (e: unknown): string[] =>
  isAxiosError(e) && Array.isArray((e.response?.data as { faltantes?: unknown })?.faltantes)
    ? (e.response!.data as { faltantes: string[] }).faltantes : [];

const mayuscula = (t: string) => t[0]!.toUpperCase() + t.slice(1);

/* =========================================================
   CU-ALO-03 Consultar mis publicaciones (GET /catalogo/mis-publicaciones)
   ========================================================= */
export function MisPublicaciones() {
  const go = useNavigate();
  const [mias, setMias] = useState<PublicacionAdmin[] | null>(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [estado, setEstado] = useState<"" | EstadoPub>("");
  const [tipo, setTipo] = useState("");

  useEffect(() => { anfitrionApi.mias().then(setMias).catch((e) => setError(leerError(e).error)); }, []);

  const todas = mias ?? [];
  const lista = todas.filter((p) =>
    (!q || `${p.titulo} ${p.ciudad_nombre ?? ""}`.toLowerCase().includes(q.toLowerCase())) &&
    (!estado || p.estado === estado) && (!tipo || p.tipo_nombre === tipo));
  const n = (e: EstadoPub) => todas.filter((p) => p.estado === e).length;
  // Devuelta = borrador cuya última revisión del administrador es DEVOLVER (RevisionPublicacion)
  const devueltas = todas.filter((p) => p.estado === "BORRADOR" && p.ultima_revision?.accion === "DEVOLVER");
  const tipos = [...new Set(todas.map((p) => p.tipo_nombre).filter(Boolean))] as string[];

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
      {error && <Alert tipo="error">{error}</Alert>}

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
          <b>{p.titulo}</b> fue devuelta por el administrador: «{p.ultima_revision?.observacion}»{" "}
          <Link to={`/publicaciones/${p.id}/editar`}>Corregir</Link>
        </Alert>
      ))}

      <div className="toolbar">
        <div className="search"><Search /><input className="input" placeholder="Buscar por título o ciudad" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select className="select" value={estado} onChange={(e) => setEstado(e.target.value as EstadoPub | "")}>
          <option value="">Estado: todos</option>
          {(["ACTIVA", "PENDIENTE_REVISION", "PAUSADA", "BORRADOR", "BLOQUEADA"] as EstadoPub[]).map((e) => <option key={e} value={e}>{ESTADO_TXT[e]}</option>)}
        </select>
        <select className="select" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          <option value="">Tipo: todos</option>
          {tipos.map((t) => <option key={t}>{t}</option>)}
        </select>
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {!mias ? <p className="muted" style={{ padding: 20 }}>{error ? "" : "Cargando…"}</p> : lista.length === 0 ? (
          <div className="empty-state"><Home /><b>No hay publicaciones con esos filtros</b>
            <Link className="btn btn-secondary btn-sm" to="/publicaciones/nueva"><Plus /> Crear una</Link></div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Publicación</th><th>Tipo</th><th>Precio / noche</th><th>Estado</th><th>Actualizada</th></tr></thead>
              <tbody>
                {lista.map((p, i) => (
                  <tr key={p.id} className="clickable" onClick={() => go(`/publicaciones/${p.id}`)}>
                    <td>
                      <div className="pub-cell">
                        <ImageTile img={imagenDe(p.imagen, i, p.titulo)} style={{ width: 52, height: 40, borderRadius: 8 }} />
                        <div><Link to={`/publicaciones/${p.id}`} onClick={(e) => e.stopPropagation()}>{p.titulo || "Sin título"}</Link><span className="subtle">{p.ciudad_nombre || "Sin ciudad"}</span></div>
                      </div>
                    </td>
                    <td>{p.tipo_nombre || "—"}</td>
                    <td>{cop(p.precio_noche)}</td>
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
  const toast = useToast();
  const go = useNavigate();
  const [p, setP] = useState<PublicacionCompleta | null>(null);
  const [negado, setNegado] = useState<string | null>(null);
  const [reservas, setReservas] = useState<ReservaResumen[]>([]);
  const [politicas, setPoliticas] = useState<PoliticaApi[]>([]);
  const [aviso, setAviso] = useState("");  // datos complementarios que no cargaron
  const [modal, setModal] = useState<null | "pausar" | "reactivar" | "eliminar" | { faltan: string[] }>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    // CA-05.3: la API responde 403 si la publicación es de otro anfitrión
    anfitrionApi.publicacion(Number(id)).then((r) => setP(r.data)).catch((e) => setNegado(leerError(e).error));
    misReservasApi.deMisAlojamientos()
      .then((r) => setReservas(r.data.filter((x) => x.publicacion === Number(id) && x.estado === "CONFIRMADA")))
      .catch((e) => setAviso(`No se pudieron cargar las reservas de esta publicación: ${leerError(e).error}`));
    catalogoApi.politicas().then((r) => setPoliticas(r.data))
      .catch((e) => setAviso(`No se pudo cargar la política de cancelación: ${leerError(e).error}`));
  }, [id]);

  if (negado) return <Denegado titulo="No puedes ver esta publicación" texto={negado} />;
  if (!p) return <Page req="RF-D-ALO-02.1"><p className="muted">Cargando…</p></Page>;

  const ultima = p.revisiones[0];
  const editable = ["BORRADOR", "ACTIVA", "PAUSADA"].includes(p.estado);
  const politica = politicas.find((x) => x.id === p.politica);

  const ejecutar = async (accion: () => Promise<{ data: PublicacionCompleta }>, ok: string) => {
    setOcupado(true);
    try {
      setP((await accion()).data);
      setModal(null);
      toast(ok);
    } catch (e) {
      const faltan = faltantesDe(e);
      if (faltan.length) setModal({ faltan });
      else { setModal(null); toast(leerError(e).error, "err"); }
    } finally {
      setOcupado(false);
    }
  };
  const enviar = () => (p.faltantes.length
    ? setModal({ faltan: p.faltantes })
    : ejecutar(() => anfitrionApi.enviarRevision(p.id), "Publicación enviada a revisión"));

  return (
    <Page req="RF-D-ALO-02.1 · CU-ALO-02 · CU-ALO-05">
      <div>
        <Link to="/publicaciones" className="back"><ArrowLeft /> Mis publicaciones</Link>
        {aviso && <Alert tipo="warn">{aviso}</Alert>}
        <div className="page-head">
          <div className="row" style={{ gap: 12 }}><h1>{p.titulo || "Sin título"}</h1><Badge estado={p.estado} /></div>
          <div className="row">
            {p.estado === "ACTIVA" && <button className="btn btn-secondary" onClick={() => setModal("pausar")}><PauseCircle /> Pausar</button>}
            {p.estado === "PAUSADA" && <button className="btn btn-secondary" onClick={() => setModal("reactivar")}><PlayCircle /> Reactivar</button>}
            {["ACTIVA", "PAUSADA", "BORRADOR"].includes(p.estado) &&
              <Link className="btn btn-secondary" to={`/calendario?pub=${p.id}`}><CalendarDays /> Calendario</Link>}
            {editable && <Link className={`btn ${p.estado === "BORRADOR" ? "btn-secondary" : "btn-primary"}`} to={`/publicaciones/${p.id}/editar`}><FileEdit /> Editar</Link>}
            {p.estado === "BORRADOR" && <button className="btn btn-ghost" disabled={ocupado} onClick={() => setModal("eliminar")}><Trash2 /> Eliminar</button>}
            {p.estado === "BORRADOR" && <button className="btn btn-primary" disabled={ocupado} onClick={enviar}><Send /> Enviar a revisión</button>}
          </div>
        </div>
      </div>

      {p.estado === "BORRADOR" && ultima?.accion === "DEVOLVER" && <Alert tipo="info"><b>Observación del administrador:</b> «{ultima.observacion}»</Alert>}
      {p.estado === "PENDIENTE_REVISION" && <Alert tipo="warn">En revisión: el administrador la aprobará o la devolverá con observaciones. Mientras tanto no aparece en las búsquedas.</Alert>}
      {p.estado === "BLOQUEADA" && <Alert tipo="error"><b>Bloqueada por moderación:</b> {ultima?.accion === "BLOQUEAR" ? ultima.observacion : ""} Solo un administrador puede desbloquearla.</Alert>}
      {p.estado === "PAUSADA" && <Alert tipo="info">Pausada: no aparece en las búsquedas ni recibe reservas nuevas. Las reservas confirmadas se mantienen.</Alert>}

      <div className="card card-tight">
        <div className="kv">
          <div><span>Ciudad</span><b>{p.ciudad_nombre || "—"}</b></div>
          <div><span>Tipo</span><b>{p.tipo_nombre || "—"}</b></div>
          <div><span>Capacidad</span><b>{p.capacidad ? `${p.capacidad} huéspedes` : "—"}</b></div>
          <div><span>Precio por noche</span><b>{cop(p.precio_noche)}</b></div>
          <div><span>Limpieza</span><b>{cop(p.tarifa_limpieza)}</b></div>
          <div><span>Descuento</span><b>{p.descuento_porcentaje ? `${Number(p.descuento_porcentaje)} % desde ${p.descuento_min_noches} noches` : "Sin descuento"}</b></div>
        </div>
      </div>

      <div className="grid-3">
        <section className="card stack">
          <h3>Servicios incluidos</h3>
          <div className="chips">{p.servicios.length ? p.servicios.map((s) => <span key={s.id} className="svc"><Check />{s.nombre}</span>) : <span className="muted">Ninguno</span>}</div>
          <h3>Servicios adicionales</h3>
          {p.servicios_adicionales.length ? (
            <ul className="list-plain">{p.servicios_adicionales.map((a) => <li key={a.id} className="row-between" style={{ display: "flex" }}><span>{a.nombre}</span><b>{cop(a.precio)}</b></li>)}</ul>
          ) : <span className="muted">Ninguno</span>}
        </section>
        <section className="card stack">
          <h3>Reglas y política</h3>
          {p.reglas.length
            ? <ol className="reglas">{[...p.reglas].sort((a, b) => a.orden - b.orden).map((r) => <li key={r.orden}>{r.descripcion}</li>)}</ol>
            : <span className="muted">Sin reglas</span>}
          <p className="muted">{p.ubicacion_textual}</p>
          <div><span className="label">Política de cancelación: </span><b>{p.politica_nombre || "Sin elegir"}</b></div>
          {politica && <ul className="list-plain subtle">{politica.tramos.map((t) => <li key={t.dias_minimos}>{Number(t.porcentaje_devolucion)} % · {textoTramo(t)}</li>)}</ul>}
        </section>
        <section className="card stack">
          <h3>Imágenes ({p.imagenes.length})</h3>
          {p.imagenes.length ? (
            <div className="img-grid">{p.imagenes.map((im, i) => <ImageTile key={im.orden} img={imagenDe(im.ruta, i)} etiqueta={i === 0 ? "Portada" : undefined} />)}</div>
          ) : <Alert tipo="warn">Falta al menos una imagen para enviar a revisión.</Alert>}
        </section>
      </div>

      <section className="card"><HistorialRevisiones revisiones={p.revisiones} /></section>

      <section className="card stack">
        <div className="card-head" style={{ margin: 0 }}>
          <h3>Reservas confirmadas</h3>
          <span className="role-pill">{reservas.length}</span>
        </div>
        {reservas.length ? (
          <ul className="list-plain">
            {reservas.map((r) => (
              <li key={r.id}><CalendarDays color="var(--brand-700)" />{fechaLarga(r.fecha_llegada)} al {fechaLarga(r.fecha_salida)} · {r.huesped_nombre}</li>
            ))}
          </ul>
        ) : <p className="muted">No tiene reservas confirmadas.</p>}
        <p className="subtle">Los cambios de precio o de política no afectan las reservas ya confirmadas.</p>
      </section>

      {modal === "eliminar" && (
        <Modal onClose={() => setModal(null)}>
          <span className="ico-big" style={{ background: "#fbe1de", color: "#9b1c12" }}><Trash2 /></span>
          <h2>¿Eliminar «{p.titulo || "Sin título"}»?</h2>
          <p className="muted">Se borran el borrador, sus fotos, reglas y servicios. Esta acción no se puede deshacer.</p>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setModal(null)}>Cancelar</button>
            <button className="btn btn-danger" disabled={ocupado} onClick={async () => {
              setOcupado(true);
              try { await anfitrionApi.eliminarBorrador(p.id); toast("Borrador eliminado"); go("/publicaciones"); }
              catch (e) { setModal(null); toast(leerError(e).error, "err"); }
              finally { setOcupado(false); }
            }}>Eliminar borrador</button>
          </div>
        </Modal>
      )}
      {modal === "pausar" && (
        <Modal onClose={() => setModal(null)}>
          <span className="ico-big" style={{ background: "#e3ecfa", color: "#1e4a8a" }}><PauseCircle /></span>
          <h2>¿Pausar «{p.titulo}»?</h2>
          <div className="row"><Badge estado="ACTIVA" /><span>→</span><Badge estado="PAUSADA" /></div>
          <p className="muted">No aparecerá en las búsquedas ni recibirá reservas nuevas.</p>
          {reservas.length > 0 && <Alert tipo="ok">Tus {reservas.length} reservas confirmadas se mantienen igual.</Alert>}
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setModal(null)}>Cancelar</button>
            <button className="btn btn-primary" disabled={ocupado} onClick={() => ejecutar(() => anfitrionApi.pausar(p.id), "Publicación pausada")}>Pausar publicación</button>
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
            <button className="btn btn-primary" disabled={ocupado} onClick={() => ejecutar(() => anfitrionApi.reactivar(p.id), "Publicación activa de nuevo")}>Reactivar</button>
          </div>
        </Modal>
      )}
      {modal && typeof modal === "object" && (
        <Modal onClose={() => setModal(null)}>
          <span className="ico-big" style={{ background: "var(--err-soft)", color: "var(--err)" }}><Send /></span>
          <h2>Aún no se puede enviar a revisión</h2>
          <p className="muted">La publicación sigue en BORRADOR. Completa lo siguiente:</p>
          <ul className="list-plain">{modal.faltan.map((f) => <li key={f}><CircleDashed color="var(--err)" />{mayuscula(f)}</li>)}</ul>
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
   POST /catalogo/publicaciones · PATCH /catalogo/publicaciones/{id}
   ========================================================= */
interface Formulario {
  titulo: string; descripcion: string; ciudad: number | null; tipo_alojamiento: number | null; politica: number | null;
  ubicacion_textual: string; capacidad: number | null; precio_noche: number | null; tarifa_limpieza: number | null;
  descuento_porcentaje: number | null; descuento_min_noches: number | null; servicios: number[];
  servicios_adicionales: { nombre: string; precio: number }[]; reglas: string[]; imagenes: string[];
}

const VACIO: Formulario = {
  titulo: "", descripcion: "", ciudad: null, tipo_alojamiento: null, politica: null, ubicacion_textual: "", capacidad: null,
  precio_noche: null, tarifa_limpieza: null, descuento_porcentaje: null, descuento_min_noches: null, servicios: [],
  servicios_adicionales: [], reglas: [], imagenes: [],
};

const n = (v: string | null | undefined) => (v == null || v === "" ? null : Number(v));
const desdeApi = (p: PublicacionCompleta): Formulario => ({
  titulo: p.titulo, descripcion: p.descripcion ?? "", ciudad: p.ciudad, tipo_alojamiento: p.tipo_alojamiento, politica: p.politica,
  ubicacion_textual: p.ubicacion_textual ?? "", capacidad: p.capacidad, precio_noche: n(p.precio_noche), tarifa_limpieza: n(p.tarifa_limpieza),
  descuento_porcentaje: n(p.descuento_porcentaje), descuento_min_noches: p.descuento_min_noches,
  servicios: p.servicios.map((s) => s.id), servicios_adicionales: p.servicios_adicionales.map((a) => ({ nombre: a.nombre, precio: Number(a.precio) })),
  reglas: [...p.reglas].sort((a, b) => a.orden - b.orden).map((r) => r.descripcion), imagenes: p.imagenes.map((i) => i.ruta),
});

const num = (v: string) => (v.trim() === "" ? null : Number(v.replace(/\D/g, "")));
const esUrl = (t: string) => /^https?:\/\/\S+$/i.test(t.trim());

/** Formulario para crear o editar una publicación en dos pasos (RF-D-ALO-01.1 y 02.1). Avisa si los cambios no afectan reservas confirmadas. */
export function FormPublicacion() {
  const { id } = useParams();
  const { tiene } = useStore();
  const toast = useToast();
  const go = useNavigate();
  const [existente, setExistente] = useState<PublicacionCompleta | null>(null);
  const [negado, setNegado] = useState<string | null>(null);
  const [p, setP] = useState<Formulario>(VACIO);
  const [cat, setCat] = useState<{ ciudades: ItemCatalogo[]; tipos: ItemCatalogo[]; servicios: ItemCatalogo[]; politicas: PoliticaApi[] }>(
    { ciudades: [], tipos: [], servicios: [], politicas: [] });
  const [paso, setPaso] = useState<1 | 2>(1);
  const [err, setErr] = useState<Record<string, string>>({});
  const [faltan, setFaltan] = useState<string[]>([]);
  const [general, setGeneral] = useState("");
  const [url, setUrl] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [nReservas, setNReservas] = useState(0);
  // El Administrador también edita (publicaciones.moderar, RF-D-ALO-02.1): al terminar vuelve a su pantalla
  const esDueno = tiene("publicaciones.gestionar_propias");
  const detalle = (pid: number) => (esDueno ? `/publicaciones/${pid}` : `/admin/publicaciones/${pid}`);

  useEffect(() => {
    Promise.all([catalogoApi.ciudades(), catalogoApi.tipos(), catalogoApi.servicios(), catalogoApi.politicas()])
      .then(([c, t, s, po]) => setCat({ ciudades: c.data, tipos: t.data, servicios: s.data, politicas: po.data }))
      .catch((e) => setGeneral(leerError(e).error));
    if (!id) return;
    anfitrionApi.publicacion(Number(id))
      .then((r) => { setExistente(r.data); setP(desdeApi(r.data)); })
      .catch((e) => setNegado(leerError(e).error));  // CA-05.3: 403 si es de otro anfitrión
    if (esDueno)
      misReservasApi.deMisAlojamientos()
        .then((r) => setNReservas(r.data.filter((x) => x.publicacion === Number(id) && x.estado === "CONFIRMADA").length))
        // Sin este dato no se mostraría el aviso de reservas confirmadas al editar el precio
        .catch((e) => setGeneral(`No se pudo comprobar si esta publicación tiene reservas confirmadas: ${leerError(e).error}`));
  }, [id, esDueno]);

  const set = <K extends keyof Formulario>(k: K, v: Formulario[K]) => setP((x) => ({ ...x, [k]: v }));

  if (negado) return <Denegado titulo="No puedes editar esta publicación" texto={negado} />;
  if (id && !existente) return <Page req="RF-D-ALO-02.1"><p className="muted">Cargando…</p></Page>;

  const estado: EstadoPub = existente?.estado ?? "BORRADOR";
  const politica = cat.politicas.find((x) => x.id === p.politica);

  const validarPaso1 = () => {
    const e: Record<string, string> = {};
    if (!p.titulo.trim()) e.titulo = "Escribe un título.";
    if (p.capacidad !== null && p.capacidad <= 0) e.capacidad = "Debe ser mayor que cero.";
    return e;
  };
  const validarPaso2 = () => {
    const e: Record<string, string> = {};
    if (p.precio_noche !== null && p.precio_noche <= 0) e.precio_noche = "Debe ser mayor que cero.";
    if ((p.descuento_porcentaje == null) !== (p.descuento_min_noches == null)) e.descuento = "Indica el porcentaje y desde cuántas noches, o deja ambos vacíos.";
    if (p.servicios_adicionales.some((a) => !a.nombre.trim())) e.adicionales = "Cada servicio adicional necesita un nombre.";
    return e;
  };

  const guardar = async (enviar: boolean) => {
    const e = { ...validarPaso1(), ...validarPaso2() };
    setErr(e); setFaltan([]); setGeneral("");
    if (Object.keys(e).length) {
      if (validarPaso1().titulo || validarPaso1().capacidad) setPaso(1);
      return;
    }
    const datos: PublicacionEntrada = { ...p, reglas: p.reglas.map((r) => r.trim()).filter(Boolean) };
    setGuardando(true);
    try {
      const g = (existente ? await anfitrionApi.actualizar(existente.id, datos) : await anfitrionApi.crear(datos)).data;
      setExistente(g);
      if (!enviar) {
        toast(id ? "Cambios guardados" : "Publicación guardada como BORRADOR");
        return go(detalle(g.id));
      }
      if (g.faltantes.length) { setFaltan(g.faltantes); return; }
      await anfitrionApi.enviarRevision(g.id);
      toast("Publicación enviada a revisión");
      go(detalle(g.id));
    } catch (ex) {
      const f = faltantesDe(ex);
      if (f.length) setFaltan(f);
      else {
        const r = leerError(ex);
        const campo = r.campo === "descuento_porcentaje" || r.campo === "descuento_min_noches" ? "descuento" : r.campo;
        if (campo && ["titulo", "capacidad", "precio_noche", "descuento"].includes(campo)) {
          setErr({ [campo]: r.error });
          setPaso(campo === "titulo" || campo === "capacidad" ? 1 : 2);
        } else setGeneral(r.error);
      }
    } finally {
      setGuardando(false);
    }
  };

  const agregarUrl = () => {
    if (!esUrl(url)) return setErr({ ...err, imagen: "Escribe una dirección que empiece por http:// o https://." });
    set("imagenes", [...p.imagenes, url.trim()]);
    setUrl(""); setErr({ ...err, imagen: "" });
  };

  const enEdicionActiva = existente && estado !== "BORRADOR";

  return (
    <Page req={existente ? "RF-D-ALO-02.1 · CU-ALO-04 · editar una publicación ACTIVA no la devuelve a revisión" : "RF-D-ALO-01.1 · CU-ALO-01 · queda en BORRADOR"}>
      <div>
        <Link to={existente ? detalle(existente.id) : "/publicaciones"} className="back"><ArrowLeft /> {existente ? "Volver al detalle" : "Mis publicaciones"}</Link>
        <div className="page-head">
          <div className="row" style={{ gap: 12 }}>
            <h1>{id ? "Editar publicación" : "Nueva publicación"}</h1>
            <Badge estado={estado} />
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
          La publicación sigue {ESTADO_TXT[estado].toLowerCase()}, sin volver a revisión.
          {nReservas > 0 && ` Los cambios de precio o de política no afectan sus ${nReservas} reservas confirmadas.`}
        </Alert>
      )}
      {general && <Alert tipo="error">{general}</Alert>}
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
              <select className="select" value={p.tipo_alojamiento ?? ""} onChange={(e) => set("tipo_alojamiento", n(e.target.value))}>
                <option value="">Selecciona</option>{cat.tipos.map((t) => <option key={t.id} value={t.id}>{t.nombre}</option>)}
              </select>
            </Field>
            <Field label="Capacidad (huéspedes)" error={err.capacidad}>
              <input className="input" inputMode="numeric" placeholder="Mayor que 0" value={p.capacidad ?? ""} onChange={(e) => set("capacidad", num(e.target.value))} />
            </Field>
            <Field label="Ciudad">
              <select className="select" value={p.ciudad ?? ""} onChange={(e) => set("ciudad", n(e.target.value))}>
                <option value="">Selecciona</option>{cat.ciudades.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </Field>
          </div>
          <Field label="Ubicación" hint="Dirección o referencia en texto.">
            <input className="input" placeholder="Ej. Vereda El Roble, a 5 min de la plaza" value={p.ubicacion_textual} onChange={(e) => set("ubicacion_textual", e.target.value)} />
          </Field>
          <div className="stack" style={{ gap: 8 }}>
            <span className="label">Reglas del alojamiento <span className="subtle">(una por línea, en el orden en que se muestran)</span></span>
            {p.reglas.map((r, i) => (
              <div className="regla-row" key={i}>
                <span className="regla-n">{i + 1}</span>
                <input className="input" aria-label={`Regla ${i + 1}`} placeholder={["Ej. No fumar", "Ej. Sin fiestas", "Ej. Silencio después de las 10 p. m."][i] ?? "Escribe la regla"}
                  value={r} onChange={(e) => set("reglas", p.reglas.map((x, j) => (j === i ? e.target.value : x)))} />
                <button type="button" className="icon-btn" aria-label="Quitar regla" onClick={() => set("reglas", p.reglas.filter((_, j) => j !== i))}><Trash2 /></button>
              </div>
            ))}
            <button type="button" className="link-btn" style={{ alignSelf: "flex-start" }} onClick={() => set("reglas", [...p.reglas, ""])}>
              + Agregar regla
            </button>
          </div>
          <div className="row">
            <Link className="btn btn-ghost" to={existente ? detalle(existente.id) : "/publicaciones"}>Cancelar</Link>
            <button className="btn btn-secondary right" disabled={guardando} onClick={() => guardar(false)}>{estado === "BORRADOR" ? "Guardar borrador" : "Guardar cambios"}</button>
            <button className="btn btn-primary" onClick={() => { const e = validarPaso1(); setErr(e); if (!Object.keys(e).length) setPaso(2); }}>Siguiente</button>
          </div>
        </section>
      ) : (
        <>
          <div className="form-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr)", gap: 20 }}>
            <section className="card stack">
              <h3>Precios</h3>
              <div className="grid-2">
                <Field label="Precio por noche (COP)" error={err.precio_noche}>
                  <div className="input-prefix"><span>$</span><input className="input" inputMode="numeric" placeholder="Mayor que 0" value={p.precio_noche ?? ""} onChange={(e) => set("precio_noche", num(e.target.value))} /></div>
                </Field>
                <Field label="Tarifa de limpieza (COP)">
                  <div className="input-prefix"><span>$</span><input className="input" inputMode="numeric" placeholder="0" value={p.tarifa_limpieza ?? ""} onChange={(e) => set("tarifa_limpieza", num(e.target.value))} /></div>
                </Field>
                <Field label="Descuento (%)" opcional error={err.descuento} hint="Por estancia larga.">
                  <input className="input" inputMode="numeric" placeholder="Ej. 10" value={p.descuento_porcentaje ?? ""} onChange={(e) => set("descuento_porcentaje", num(e.target.value))} />
                </Field>
                <Field label="Desde cuántas noches" opcional>
                  <input className="input" inputMode="numeric" placeholder="Ej. 7" value={p.descuento_min_noches ?? ""} onChange={(e) => set("descuento_min_noches", num(e.target.value))} />
                </Field>
              </div>
              <p className="subtle">La tarifa de servicio de la plataforma la fija el administrador y se suma en la cotización del huésped.</p>
              <Field label="Política de cancelación">
                <select className="select" value={p.politica ?? ""} onChange={(e) => set("politica", n(e.target.value))}>
                  <option value="">Selecciona una política</option>
                  {cat.politicas.map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
                </select>
              </Field>
              {politica && (
                <div className="card card-tight" style={{ boxShadow: "none", background: "var(--brand-50)" }}>
                  <ul className="list-plain">{politica.tramos.map((t) => <li key={t.dias_minimos}><b style={{ width: 52 }}>{Number(t.porcentaje_devolucion)} %</b><span>{textoTramo(t)}</span></li>)}</ul>
                </div>
              )}
            </section>

            <section className="card stack">
              <h3>Servicios incluidos <span className="subtle">(sin costo)</span></h3>
              <div className="chips">
                {cat.servicios.map((s) => {
                  const on = p.servicios.includes(s.id);
                  return (
                    <button key={s.id} type="button" className={`chip-toggle ${on ? "on" : ""}`} aria-pressed={on}
                      onClick={() => set("servicios", on ? p.servicios.filter((x) => x !== s.id) : [...p.servicios, s.id])}>
                      {on && <Check />}{s.nombre}
                    </button>
                  );
                })}
              </div>
              <h3>Servicios adicionales <span className="subtle">(se cobran aparte)</span></h3>
              {p.servicios_adicionales.map((a, i) => (
                <div className="addon-row" key={i}>
                  <input className="input" placeholder="Ej. Desayuno" value={a.nombre} onChange={(e) => set("servicios_adicionales", p.servicios_adicionales.map((x, j) => (j === i ? { ...x, nombre: e.target.value } : x)))} />
                  <div className="input-prefix"><span>$</span><input className="input" inputMode="numeric" value={a.precio || ""} placeholder="0" onChange={(e) => set("servicios_adicionales", p.servicios_adicionales.map((x, j) => (j === i ? { ...x, precio: num(e.target.value) ?? 0 } : x)))} /></div>
                  <button type="button" className="icon-btn" aria-label="Quitar servicio" onClick={() => set("servicios_adicionales", p.servicios_adicionales.filter((_, j) => j !== i))}><Trash2 /></button>
                </div>
              ))}
              {err.adicionales && <span className="error-text">{err.adicionales}</span>}
              <button type="button" className="link-btn" style={{ alignSelf: "flex-start" }} onClick={() => set("servicios_adicionales", [...p.servicios_adicionales, { nombre: "", precio: 0 }])}>
                + Agregar servicio adicional
              </button>
            </section>
          </div>

          <section className="card stack">
            <h3>Imágenes <span className="subtle">(mínimo una; la primera es la portada)</span></h3>
            <div className="img-grid">
              {p.imagenes.map((ruta, i) => (
                <ImageTile key={`${i}-${ruta}`} img={imagenDe(ruta, i)} etiqueta={i === 0 ? "Portada" : undefined}
                  onRemove={() => set("imagenes", p.imagenes.filter((_, j) => j !== i))} />
              ))}
            </div>
            <Field label="Dirección (URL) de la imagen" error={err.imagen} hint="La plataforma guarda la dirección de cada imagen.">
              <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
                <input className="input" placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); agregarUrl(); } }} />
                <button type="button" className="btn btn-secondary" onClick={agregarUrl}><ImagePlus /> Agregar</button>
              </div>
            </Field>
          </section>

          <div className="row">
            <button className="btn btn-ghost" onClick={() => setPaso(1)}><ArrowLeft /> Paso anterior</button>
            <button className="btn btn-secondary right" disabled={guardando} onClick={() => guardar(false)}>{estado === "BORRADOR" ? "Guardar borrador" : "Guardar cambios"}</button>
            {estado === "BORRADOR" && esDueno && <button className="btn btn-primary" disabled={guardando} onClick={() => guardar(true)}><Send /> Enviar a revisión</button>}
          </div>
        </>
      )}
    </Page>
  );
}

/** Reinicia el formulario al pasar de una publicación a otra. */
export function FormPublicacionRuta() {
  const { id } = useParams();
  return <FormPublicacion key={id ?? "nueva"} />;
}
