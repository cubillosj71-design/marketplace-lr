import { ArrowLeft, CalendarX, Check, Lock, MapPin, Search, Star, Users } from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  busquedaApi, catalogoApi, leerError, reservasApi,
  type DetallePublico, type FiltrosBusqueda, type ItemCatalogo, type ResultadoBusqueda, type Tramo,
} from "../api";
import { cop } from "../data";
import { Page } from "../layout";
import { useStore } from "../store";
import { Alert, Field, Logo } from "../ui";

/* ---------------- utilidades de fechas (RF-D-ALO-02.2: hasta hoy + 12 meses) ---------------- */
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const hoyIso = () => iso(new Date());
export const maximoIso = () => { const d = new Date(); d.setMonth(d.getMonth() + 12); return iso(d); };
const fechaCorta = (f: string) => new Date(f + "T12:00:00").toLocaleDateString("es-CO", { day: "numeric", month: "short" });
const pesos = (v: string | null | undefined) => (v == null ? "—" : cop(Number(v)));

/** Noches seguidas -> rangos [primera, última]. */
function rangos(fechas: string[]): [string, string][] {
  const out: [string, string][] = [];
  for (const f of fechas) {
    const ultimo = out[out.length - 1];
    if (ultimo) {
      const sig = new Date(ultimo[1] + "T12:00:00"); sig.setDate(sig.getDate() + 1);
      if (iso(sig) === f) { ultimo[1] = f; continue; }
    }
    out.push([f, f]);
  }
  return out;
}

const textoTramo = (t: Tramo) =>
  t.dias_maximos == null ? `${t.dias_minimos} días o más antes de la llegada`
    : t.dias_minimos === 0 ? `Menos de ${t.dias_maximos + 1} días antes`
      : `Entre ${t.dias_minimos} y ${t.dias_maximos} días antes`;

function Estrellas({ promedio, total }: { promedio: string | null; total: number }) {
  if (!total || promedio == null) return <span className="subtle">Sin reseñas todavía</span>;
  return <span className="row" style={{ gap: 4 }}><Star size={14} /> {Number(promedio).toFixed(1).replace(".", ",")} ({total})</span>;
}

function Foto({ src, alt, style }: { src?: string | null; alt: string; style?: React.CSSProperties }) {
  return (
    <div className="img-ph" style={{ background: "linear-gradient(135deg,#cfdcd8,#e8efec)", ...style }}>
      {src && <img src={src} alt={alt} loading="lazy" />}
    </div>
  );
}

/** Barra superior para el Visitante (sin sesión). */
function PublicShell({ children }: { children: ReactNode }) {
  const { usuario } = useStore();
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header className="public-top">
        <Link to="/explorar-publico" style={{ color: "var(--text)" }}><Logo /></Link>
        <div className="row right">
          {usuario ? <Link className="btn btn-ghost" to="/inicio">Mi cuenta</Link> : (
            <>
              <Link className="btn btn-ghost" to="/ingresar">Iniciar sesión</Link>
              <Link className="btn btn-primary" to="/registro">Registrarse</Link>
            </>
          )}
        </div>
      </header>
      {children}
    </div>
  );
}

/* ---------------- HU-10 Buscar alojamientos ---------------- */
function Explorador({ base }: { base: string }) {
  const [cat, setCat] = useState<{ ciudades: ItemCatalogo[]; tipos: ItemCatalogo[]; servicios: ItemCatalogo[] }>({ ciudades: [], tipos: [], servicios: [] });
  const [f, setF] = useState({ ciudad: "", llegada: "", salida: "", huespedes: 1, tipo: "", precio_min: "", precio_max: "", servicios: [] as number[] });
  const [lista, setLista] = useState<ResultadoBusqueda[] | null>(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  const buscar = async (filtros = f) => {
    setError("");
    if ((filtros.llegada || filtros.salida) && !(filtros.llegada && filtros.salida)) return setError("Indica la fecha de llegada y la de salida.");
    if (filtros.llegada && filtros.salida && filtros.salida <= filtros.llegada)  // CA-10.3: no busca
      return setError("La fecha de salida debe ser posterior a la de llegada.");
    const consulta: FiltrosBusqueda = {
      ciudad: filtros.ciudad ? Number(filtros.ciudad) : undefined, tipo: filtros.tipo ? Number(filtros.tipo) : undefined,
      llegada: filtros.llegada || undefined, salida: filtros.salida || undefined, huespedes: filtros.huespedes,
      precio_min: filtros.precio_min ? Number(filtros.precio_min) : undefined,
      precio_max: filtros.precio_max ? Number(filtros.precio_max) : undefined, servicios: filtros.servicios,
    };
    setCargando(true);
    try { setLista((await busquedaApi.buscar(consulta)).data); }
    catch (e) { setError(leerError(e).error); }
    finally { setCargando(false); }
  };

  useEffect(() => {
    Promise.all([catalogoApi.ciudades(), catalogoApi.tipos(), catalogoApi.servicios()])
      .then(([c, t, s]) => setCat({ ciudades: c.data, tipos: t.data, servicios: s.data }))
      .catch(() => setError("No se pudieron cargar las ciudades y los servicios."));
    buscar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const enviar = (e: FormEvent) => { e.preventDefault(); buscar(); };
  const alternarServicio = (id: number) =>
    setF({ ...f, servicios: f.servicios.includes(id) ? f.servicios.filter((x) => x !== id) : [...f.servicios, id] });

  return (
    <Page req="RF-D-RES-01.1 · HU-10 · solo publicaciones ACTIVAS de anfitriones con cuenta activa y sin restricción">
      <section className="public-hero">
        <div><h1>Explora alojamientos</h1><p>Elige la ciudad, las fechas y cuántos son.</p></div>
        <form className="stack" onSubmit={enviar} noValidate>
          <div className="search-bar">
            <select className="select" value={f.ciudad} onChange={(e) => setF({ ...f, ciudad: e.target.value })} aria-label="Ciudad">
              <option value="">Todas las ciudades</option>{cat.ciudades.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
            <input className="input" type="date" aria-label="Llegada" value={f.llegada} min={hoyIso()} max={maximoIso()} onChange={(e) => setF({ ...f, llegada: e.target.value })} />
            <input className="input" type="date" aria-label="Salida" value={f.salida} min={f.llegada || hoyIso()} max={maximoIso()} onChange={(e) => setF({ ...f, salida: e.target.value })} />
            <button className="btn btn-primary" type="submit" disabled={cargando}><Search /> Buscar</button>
          </div>
          <details className="card" style={{ padding: 12, color: "var(--text)" }}>
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>Más filtros</summary>
            <div className="grid-2" style={{ marginTop: 12 }}>
              <Field label="Huéspedes">
                <input className="input" type="number" min={1} value={f.huespedes} onChange={(e) => setF({ ...f, huespedes: Math.max(1, Number(e.target.value) || 1) })} />
              </Field>
              <Field label="Tipo de alojamiento">
                <select className="select" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}>
                  <option value="">Todos</option>{cat.tipos.map((t) => <option key={t.id} value={t.id}>{t.nombre}</option>)}
                </select>
              </Field>
              <Field label="Precio por noche desde">
                <input className="input" type="number" min={0} step={10000} value={f.precio_min} onChange={(e) => setF({ ...f, precio_min: e.target.value })} />
              </Field>
              <Field label="Precio por noche hasta">
                <input className="input" type="number" min={0} step={10000} value={f.precio_max} onChange={(e) => setF({ ...f, precio_max: e.target.value })} />
              </Field>
            </div>
            <p style={{ margin: "10px 0 6px", fontWeight: 600, fontSize: 14 }}>Servicios (deben estar todos)</p>
            <div className="chips">
              {cat.servicios.map((s) => (
                <label key={s.id} className="svc" style={{ cursor: "pointer" }}>
                  <input type="checkbox" checked={f.servicios.includes(s.id)} onChange={() => alternarServicio(s.id)} /> {s.nombre}
                </label>
              ))}
            </div>
          </details>
        </form>
      </section>
      {error && <Alert tipo="error">{error}</Alert>}
      {lista && <p className="muted">{lista.length} {lista.length === 1 ? "alojamiento" : "alojamientos"}</p>}
      <div className="cards">
        {(lista ?? []).map((p) => {
          const consulta = f.llegada && f.salida ? `?llegada=${f.llegada}&salida=${f.salida}&huespedes=${f.huespedes}` : "";
          return (
            <Link key={p.id} to={`${base}/${p.id}${consulta}`} className="listing" style={{ color: "inherit", textDecoration: "none" }}>
              <div style={{ position: "relative" }}>
                <Foto src={p.imagen_principal} alt={p.titulo} />
                <span className="type">{p.tipo}</span>
              </div>
              <div className="body">
                <h3>{p.titulo}</h3>
                <span className="subtle" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><MapPin size={14} />{p.ciudad} · hasta {p.capacidad} huéspedes</span>
                <Estrellas {...p.calificacion} />
                <div className="price"><b>{pesos(p.precio_noche)}</b> <span>/ noche</span></div>
              </div>
            </Link>
          );
        })}
      </div>
    </Page>
  );
}

/* ---------------- HU-11 Detalle y formulario de cotización (HU-12) ---------------- */
function Detalle({ base }: { base: string }) {
  const { id } = useParams();
  const { usuario } = useStore();
  const go = useNavigate();
  const loc = useLocation();
  const inicial = new URLSearchParams(loc.search);
  const [d, setD] = useState<DetallePublico | null>(null);
  const [noExiste, setNoExiste] = useState(false);
  const [f, setF] = useState({ llegada: inicial.get("llegada") ?? "", salida: inicial.get("salida") ?? "",
    huespedes: Number(inicial.get("huespedes") ?? 1), adicionales: [] as number[] });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    const hasta = new Date(); hasta.setDate(hasta.getDate() + 120);
    busquedaApi.detalle(Number(id), hoyIso(), iso(hasta))
      .then((r) => setD(r.data))
      .catch(() => setNoExiste(true));
  }, [id]);

  if (noExiste)
    return <Page req="RF-D-RES-01.2"><div className="card empty-state"><Lock /><h2>Este alojamiento no está disponible</h2><Link className="btn btn-secondary" to={base}>Volver</Link></div></Page>;
  if (!d) return <Page req="RF-D-RES-01.2"><p className="muted">Cargando…</p></Page>;

  const ocupadas = new Set(d.disponibilidad.noches_no_disponibles);
  const cotizar = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (!usuario) // CA-05.1: el Visitante debe iniciar sesión para cotizar o reservar
      return go("/ingresar", { state: { aviso: "Inicia sesión como huésped para cotizar y reservar.", volver: loc.pathname + loc.search } });
    if (usuario.rol !== "HUESPED") return setError("Solo los huéspedes pueden cotizar y reservar.");
    if (!f.llegada || !f.salida) return setError("Elige la fecha de llegada y la de salida.");
    if (f.salida <= f.llegada) return setError("La fecha de salida debe ser posterior a la de llegada.");
    if (f.huespedes > d.capacidad) return setError(`La capacidad máxima de este alojamiento es de ${d.capacidad} huéspedes.`);
    setEnviando(true);
    try {
      const { data } = await reservasApi.cotizar({ publicacion: d.id, fecha_llegada: f.llegada, fecha_salida: f.salida,
        num_huespedes: f.huespedes, adicionales: f.adicionales });
      go(`/cotizacion/${data.id}`);
    } catch (err) {
      setError(leerError(err).error);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Page req="RF-D-RES-01.2 · HU-11 · RF-D-RES-02.1 · HU-12">
      <Link to={base} className="back"><ArrowLeft /> Volver a explorar</Link>
      <div className="page-head"><div><h1>{d.titulo}</h1><p style={{ display: "inline-flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}><MapPin size={15} />{d.ubicacion_textual}, {d.ciudad} · <Estrellas {...d.calificacion} /></p></div></div>
      <div style={{ display: "grid", gridTemplateColumns: d.imagenes.length <= 1 ? "1fr" : "2fr 1fr", gridTemplateRows: d.imagenes.length <= 2 ? "310px" : "150px 150px", gap: 10 }} className="gallery">
        <Foto src={d.imagenes[0]?.ruta} alt={d.titulo} style={{ gridRow: "span 2" }} />
        {d.imagenes.slice(1, 3).map((im) => <Foto key={im.orden} src={im.ruta} alt={`${d.titulo} ${im.orden}`} />)}
      </div>
      <div className="detail-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,1.6fr) minmax(0,1fr)", gap: 20, alignItems: "start" }}>
        <div className="stack">
          <section className="card stack">
            <div className="row" style={{ gap: 18, flexWrap: "wrap" }}>
              <span className="row" style={{ gap: 6 }}><Users size={18} /> Hasta {d.capacidad} huéspedes</span>
              <span className="muted">{d.tipo}</span>
              {d.anfitrion_nombre && <span className="muted">Anfitrión: {d.anfitrion_nombre}</span>}
            </div>
            <p>{d.descripcion}</p>
            <div className="chips">{d.servicios.map((s) => <span key={s.id} className="svc"><Check />{s.nombre}</span>)}</div>
          </section>
          <section className="card stack">
            <h3>Reglas del alojamiento</h3>
            <ol className="reglas">{d.reglas.map((r) => <li key={r.orden}>{r.descripcion}</li>)}</ol>
            {d.politica && (
              <>
                <h3>Política de cancelación: {d.politica.nombre}</h3>
                <ul className="list-plain">
                  {d.politica.tramos.map((t) => <li key={t.dias_minimos}><b style={{ width: 52 }}>{Number(t.porcentaje_devolucion)} %</b>{textoTramo(t)}</li>)}
                </ul>
              </>
            )}
          </section>
          <section className="card stack">
            <h3 className="row" style={{ gap: 8 }}><CalendarX size={18} /> Fechas no disponibles</h3>
            {ocupadas.size === 0 ? <p className="muted">Todas las noches de los próximos meses están libres.</p> : (
              <div className="chips">
                {rangos(d.disponibilidad.noches_no_disponibles).map(([a, b]) => (
                  <span key={a} className="svc">{a === b ? fechaCorta(a) : `${fechaCorta(a)} al ${fechaCorta(b)}`}</span>
                ))}
              </div>
            )}
          </section>
        </div>
        <aside className="card stack">
          <div className="price"><b style={{ fontSize: 24 }}>{pesos(d.precio_noche)}</b> <span>/ noche</span></div>
          <p className="subtle">Limpieza {pesos(d.tarifa_limpieza)}{d.descuento_porcentaje ? ` · ${Number(d.descuento_porcentaje)} % de descuento desde ${d.descuento_min_noches} noches` : ""}</p>
          <form className="stack" onSubmit={cotizar} noValidate>
            <div className="grid-2">
              <Field label="Llegada"><input className="input" type="date" value={f.llegada} min={hoyIso()} max={maximoIso()} onChange={(e) => setF({ ...f, llegada: e.target.value })} /></Field>
              <Field label="Salida"><input className="input" type="date" value={f.salida} min={f.llegada || hoyIso()} max={maximoIso()} onChange={(e) => setF({ ...f, salida: e.target.value })} /></Field>
            </div>
            <Field label="Huéspedes" hint={`Máximo ${d.capacidad}.`}>
              <input className="input" type="number" min={1} max={d.capacidad} value={f.huespedes} onChange={(e) => setF({ ...f, huespedes: Math.max(1, Number(e.target.value) || 1) })} />
            </Field>
            {d.servicios_adicionales.length > 0 && (
              <div className="stack" style={{ gap: 6 }}>
                <span className="subtle">Servicios adicionales (una vez por estancia)</span>
                {d.servicios_adicionales.map((a) => (
                  <label key={a.id} className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                    <span className="row" style={{ gap: 8 }}>
                      <input type="checkbox" checked={f.adicionales.includes(a.id)}
                        onChange={() => setF({ ...f, adicionales: f.adicionales.includes(a.id) ? f.adicionales.filter((x) => x !== a.id) : [...f.adicionales, a.id] })} />
                      {a.nombre}
                    </span>
                    <span>{pesos(a.precio)}</span>
                  </label>
                ))}
              </div>
            )}
            {error && <Alert tipo="error">{error}</Alert>}
            {!usuario && <Alert tipo="info">Para cotizar o reservar necesitas iniciar sesión como huésped.</Alert>}
            <button className="btn btn-primary btn-block" type="submit" disabled={enviando}>{enviando ? "Cotizando…" : "Cotizar estancia"}</button>
          </form>
        </aside>
      </div>
    </Page>
  );
}

export const Explorar = () => <Explorador base="/explorar" />;
export const ExplorarDetalle = () => <Detalle base="/explorar" />;
export const ExplorarPublico = () => <PublicShell><Explorador base="/explorar-publico" /></PublicShell>;
export const ExplorarPublicoDetalle = () => <PublicShell><Detalle base="/explorar-publico" /></PublicShell>;
