import { ArrowLeft, Bell, CalendarCheck, CheckCheck, Home, Inbox, MapPin, Search, XCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  anfitrionApi, leerError, misReservasApi, notificacionesApi,
  type NotificacionApi, type ReservaDetalleApi, type ReservaResumen, type SimulacionCancelacion,
} from "../api";
import { RESERVA_TXT, cop, esReservaPendiente, hoyEnColombia } from "../data";
import { Page } from "../layout";
import { useStore, useToast } from "../store";
import { Alert, Field, Modal } from "../ui";

const pesos = (v: string) => cop(Number(v));
const fecha = (f: string) => new Date(f + "T12:00:00").toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
const fechaHora = (f: string) => new Date(f).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" }).replace(/\.$/, "");

const CLASE_ESTADO: Record<ReservaResumen["estado"], string> = {
  CONFIRMADA: "badge-ACTIVA", COMPLETADA: "badge-PENDIENTE_REVISION", CANCELADA: "badge-BLOQUEADA", EN_REVISION: "badge-PAUSADA",
};
type Fechas = Pick<ReservaResumen, "estado" | "fecha_llegada" | "fecha_salida">;
/** CONFIRMADA y hoy (Colombia) entre la llegada y la salida. Solo es visual: el estado en la base no cambia. */
const estaEnCurso = (r: Fechas, hoy = hoyEnColombia()) => r.estado === "CONFIRMADA" && r.fecha_llegada <= hoy && hoy <= r.fecha_salida;
const EN_CURSO_SIN_CANCELAR = "Tu estadía ya empezó; ya no se puede cancelar.";
const EstadoReserva = ({ r }: { r: Fechas }) => estaEnCurso(r)
  ? <span className="badge badge-EN_CURSO">En curso</span>
  : <span className={`badge ${CLASE_ESTADO[r.estado]}`}>{RESERVA_TXT[r.estado]}</span>;

const QUIEN_CANCELO: Record<string, { huesped: string; anfitrion: string }> = {
  HUESPED: { huesped: " por ti", anfitrion: " por el huésped" },
  ADMINISTRADOR: { huesped: " por el administrador", anfitrion: " por el administrador" },
  AUTOMATICA: { huesped: " automáticamente", anfitrion: " automáticamente" },
};
/** "Cancelada el 10 nov 2026, 10:00 a. m. por el huésped." */
const textoCancelada = (c: NonNullable<ReservaResumen["cancelacion"]>, vista: "huesped" | "anfitrion" | "admin") => {
  const quien = QUIEN_CANCELO[c.cancelada_por_rol]?.[vista === "huesped" ? "huesped" : "anfitrion"];
  // fechaHora quita el punto final de "a. m." para cerrar la frase; si sigue "por ...", va la hora completa
  const completa = new Date(c.fecha).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
  return quien ? `Cancelada el ${completa}${quien}.` : `Cancelada el ${fechaHora(c.fecha)}.`;
};

/** Hook común: carga una lista de la API y expone recargar. */
function useLista(cargar: () => Promise<{ data: ReservaResumen[] }>) {
  const [lista, setLista] = useState<ReservaResumen[] | null>(null);
  const [error, setError] = useState("");
  const recargar = useCallback(() => {
    cargar().then((r) => { setLista(r.data); setError(""); }).catch((e) => setError(leerError(e).error));
  }, [cargar]);
  useEffect(recargar, [recargar]);
  return { lista, error, recargar };
}

/* ---------------- HU-15 Cancelar: la misma ventana en la tarjeta y en el detalle ---------------- */
type ParaCancelar = Pick<ReservaResumen, "id" | "alojamiento" | "fecha_llegada" | "fecha_salida" | "total">;

function useCancelarReserva(alCancelar: () => void) {
  const toast = useToast();
  const [cancelar, setCancelar] = useState<{ r: ParaCancelar; sim: SimulacionCancelacion | null } | null>(null);
  const [motivo, setMotivo] = useState("");
  const [errModal, setErrModal] = useState("");
  const [enviando, setEnviando] = useState(false);

  const abrir = async (r: ParaCancelar) => {
    setMotivo(""); setErrModal(""); setCancelar({ r, sim: null });
    try { const { data } = await misReservasApi.simularCancelacion(r.id); setCancelar({ r, sim: data }); }
    catch (e) { setErrModal(leerError(e).error); }
  };
  const confirmar = async () => {
    if (!cancelar) return;
    if (!motivo.trim()) return setErrModal("Escribe el motivo de la cancelación.");
    setEnviando(true);
    try {
      await misReservasApi.cancelar(cancelar.r.id, motivo.trim());
      toast("Reserva cancelada");
      setCancelar(null);
      alCancelar();
    } catch (e) { setErrModal(leerError(e).error); }
    finally { setEnviando(false); }
  };

  const ventana = cancelar && (
    <Modal onClose={() => setCancelar(null)}>
      <h2>¿Cancelar esta reserva?</h2>
      <p className="muted">{cancelar.r.alojamiento} · {fecha(cancelar.r.fecha_llegada)} al {fecha(cancelar.r.fecha_salida)}</p>
      {cancelar.sim ? (
        <Alert tipo={Number(cancelar.sim.valor_devolucion) > 0 ? "info" : "warn"}>
          Faltan {cancelar.sim.dias_anticipacion} {cancelar.sim.dias_anticipacion === 1 ? "día" : "días"} para la llegada.
          Según la política de cancelación te devolvemos el {Number(cancelar.sim.porcentaje_devolucion)} %:
          <b> {pesos(cancelar.sim.valor_devolucion)}</b> de {pesos(cancelar.r.total)}.
        </Alert>
      ) : !errModal && <p className="muted">Calculando la devolución…</p>}
      <Field label="Motivo de la cancelación" error={errModal}>
        <textarea className="input" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </Field>
      <div className="modal-actions">
        <button className="btn btn-secondary" onClick={() => setCancelar(null)}>Volver</button>
        <button className="btn btn-primary" style={{ background: "var(--err)" }} disabled={enviando || !cancelar.sim?.cancelable} onClick={confirmar}>
          {enviando ? "Cancelando…" : "Sí, cancelar"}
        </button>
      </div>
    </Modal>
  );
  return { abrir, ventana };
}

/* ---------------- HU-20 Resolver una reserva EN_REVISION: la misma confirmación en la tarjeta y en el detalle ---------------- */
type ParaResolver = Pick<ReservaResumen, "id" | "alojamiento" | "fecha_llegada" | "fecha_salida" | "total">;

function useResolverReserva(alResolver: () => void) {
  const toast = useToast();
  const [pendiente, setPendiente] = useState<{ r: ParaResolver; mantener: boolean } | null>(null);
  const [motivo, setMotivo] = useState("");
  const [errModal, setErrModal] = useState("");
  const [enviando, setEnviando] = useState(false);

  const abrir = (r: ParaResolver, mantener: boolean) => { setMotivo(""); setErrModal(""); setPendiente({ r, mantener }); };
  const confirmar = async () => {
    if (!pendiente) return;
    const { r, mantener } = pendiente;
    if (!mantener && !motivo.trim()) return setErrModal("Escribe el motivo de la cancelación.");
    setEnviando(true);
    try {
      await misReservasApi.resolver(r.id, mantener, mantener ? undefined : motivo.trim());
      toast(mantener ? "La reserva sigue confirmada" : "Reserva cancelada con devolución del 100 %");
      setPendiente(null);
      alResolver();
    } catch (e) { setErrModal(leerError(e).error); }
    finally { setEnviando(false); }
  };

  const ventana = pendiente && (
    <Modal onClose={() => setPendiente(null)}>
      <h2>{pendiente.mantener ? "¿Mantener la reserva?" : "Cancelar con devolución"}</h2>
      <p className="muted">{pendiente.r.alojamiento} · {fecha(pendiente.r.fecha_llegada)} al {fecha(pendiente.r.fecha_salida)}</p>
      {pendiente.mantener ? (
        <>
          <Alert tipo="info">La reserva vuelve a Confirmada y se avisa al huésped y al anfitrión.</Alert>
          {errModal && <Alert tipo="error">{errModal}</Alert>}
        </>
      ) : (
        <>
          <Alert tipo="warn">Se cancela y se devuelve <b>{pesos(pendiente.r.total)}</b> (100 %) al huésped. El huésped y el anfitrión reciben un aviso.</Alert>
          <Field label="Motivo (obligatorio)" error={errModal}>
            <textarea className="input" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </Field>
        </>
      )}
      <div className="modal-actions">
        <button className="btn btn-secondary" onClick={() => setPendiente(null)}>Volver</button>
        <button className="btn btn-primary" style={pendiente.mantener ? undefined : { background: "var(--err)" }} disabled={enviando} onClick={confirmar}>
          {enviando ? "Guardando…" : pendiente.mantener ? "Sí, mantener" : "Cancelar reserva"}
        </button>
      </div>
    </Modal>
  );
  return { abrir, ventana };
}

/** "Faltan 5 días para la llegada. Si no se resuelve, se cancela sola el 10 de dic de 2026 con devolución del 100 %."
 *  Con 3 días o menos va en color de alerta. */
function AvisoPlazo({ r }: { r: ReservaResumen }) {
  const n = r.dias_para_llegada ?? 0;
  const faltan = n <= 0 ? "La llegada es hoy." : `Faltan ${n} ${n === 1 ? "día" : "días"} para la llegada.`;
  return (
    <Alert tipo={n <= 3 ? "warn" : "info"}>
      {faltan} Si no se resuelve, se cancela sola el {fecha(r.fecha_llegada)} con devolución del 100 %.
    </Alert>
  );
}

/** Bloqueo de la publicación (historial de revisiones) y, en Resueltas, el resultado. */
function DatosRevision({ r }: { r: ReservaResumen }) {
  const res = r.resolucion;
  return (
    <>
      {r.bloqueo && (
        <p className="muted" style={{ margin: 0 }}>
          Publicación bloqueada el {fechaHora(r.bloqueo.fecha)}. Motivo: {(r.bloqueo.motivo ?? "sin motivo").replace(/\.$/, "")}.
        </p>
      )}
      {res?.resultado === "MANTENIDA" && (
        <p style={{ margin: 0 }}><b>Mantenida:</b> volvió a Confirmada.{res.por ? ` La resolvió ${res.por}` : ""}{res.fecha ? ` el ${fechaHora(res.fecha)}` : ""}.</p>
      )}
      {res?.resultado === "CANCELADA_ADMINISTRADOR" && (
        <p style={{ margin: 0 }}>
          <b>Cancelada por el administrador</b>{res.por ? ` (${res.por})` : ""}{res.fecha ? ` el ${fechaHora(res.fecha)}` : ""}.
          {res.motivo ? ` Motivo: ${res.motivo.replace(/\.$/, "")}.` : ""} Devuelto: {pesos(res.valor_devolucion ?? "0")} (100 %).
        </p>
      )}
      {res?.resultado === "CANCELADA_AUTOMATICA" && (
        <p style={{ margin: 0 }}>
          <b>Cancelada automáticamente</b>{res.fecha ? ` el ${fechaHora(res.fecha)}` : ""}. Motivo: Sin resolución antes de la llegada.
          {" "}Devuelto: {pesos(res.valor_devolucion ?? "0")} (100 %).
        </p>
      )}
    </>
  );
}

/** Portada del alojamiento; sin imagen (o si no carga) queda el fondo neutro con el ícono de la casa. */
function Portada({ src, alt, className = "" }: { src: string | null; alt: string; className?: string }) {
  const [rota, setRota] = useState(false);
  useEffect(() => setRota(false), [src]);
  return (
    <div className={`img-ph portada-reserva ${className}`} style={{ background: "linear-gradient(135deg,#cfdcd8,#e8efec)" }}>
      {src && !rota ? <img src={src} alt={alt} loading="lazy" onError={() => setRota(true)} /> : <Home aria-hidden />}
    </div>
  );
}

/* ---------------- Pestañas y tarjetas con portada: Mis reservas (huésped) y Reservas de mis alojamientos (anfitrión) ---------------- */
type Vista = "huesped" | "anfitrion" | "admin";
const PESTANAS = [
  { clave: "proximas", nombre: "Próximas", vacia: "No hay reservas próximas." },
  { clave: "revision", nombre: "En revisión", vacia: "No hay reservas en revisión." },
  { clave: "pasadas", nombre: "Pasadas", vacia: "Todavía no hay estancias pasadas." },
  { clave: "canceladas", nombre: "Canceladas", vacia: "No hay reservas canceladas." },
] as const;
type Pestana = (typeof PESTANAS)[number]["clave"];  // las del huésped y el anfitrión

/** Huésped: Próximas son las pendientes (mismo criterio que el perfil, incluye EN_REVISION). Anfitrión: Próximas son las
 *  CONFIRMADAS con salida >= hoy y las EN_REVISION van en su propia pestaña. Pasadas: COMPLETADA o con la salida ya
 *  pasada, por llegada descendente. Canceladas: por fecha de cancelación descendente. "Hoy" es la fecha de Colombia. */
function separarReservas(lista: ReservaResumen[], vista: Vista, hoy = hoyEnColombia()): Record<Pestana, ReservaResumen[]> {
  const canceladas = lista.filter((r) => r.estado === "CANCELADA");
  const revision = vista === "anfitrion" ? lista.filter((r) => r.estado === "EN_REVISION") : [];
  const proximas = lista.filter((r) => !revision.includes(r) && esReservaPendiente(r, hoy));
  const pasadas = lista.filter((r) => r.estado !== "CANCELADA" && !revision.includes(r) && !proximas.includes(r));
  const porLlegada = (a: ReservaResumen, b: ReservaResumen) => a.fecha_llegada.localeCompare(b.fecha_llegada) || a.id - b.id;
  const fechaCancelacion = (r: ReservaResumen) => r.cancelacion?.fecha ?? "";
  return {
    proximas: proximas.sort(porLlegada),
    revision: revision.sort(porLlegada),
    pasadas: pasadas.sort((a, b) => -porLlegada(a, b)),
    canceladas: canceladas.sort((a, b) => fechaCancelacion(b).localeCompare(fechaCancelacion(a)) || b.id - a.id),
  };
}

/** Enlace a la publicación: el huésped va al detalle de Explorar; el anfitrión, a su publicación; el Administrador, al
 *  detalle de administración. */
const enlacePublicacion = (vista: Vista, id: number) =>
  vista === "huesped" ? { to: `/explorar/${id}`, texto: "Ver alojamiento" }
    : vista === "anfitrion" ? { to: `/publicaciones/${id}`, texto: "Ver publicación" }
      : { to: `/admin/publicaciones/${id}`, texto: "Ver publicación" };
const RUTA_DETALLE: Record<Vista, string> = { huesped: "/reservas", anfitrion: "/reservas-alojamientos", admin: "/admin/reservas" };

function TarjetaConPortada({ r, vista, onCancelar, onResolver }: {
  r: ReservaResumen; vista: Vista; onCancelar?: () => void; onResolver?: (mantener: boolean) => void;
}) {
  const go = useNavigate();
  const detalle = `${RUTA_DETALLE[vista]}/${r.id}`;
  const enlace = enlacePublicacion(vista, r.publicacion);
  const parar = (e: React.SyntheticEvent) => e.stopPropagation();  // los botones de adentro no abren el detalle
  return (
    <section className="card tarjeta-reserva" role="link" tabIndex={0} aria-label={`Ver la reserva en ${r.alojamiento ?? "el alojamiento"}`}
      onClick={() => go(detalle)} onKeyDown={(e) => { if (e.key === "Enter" && e.target === e.currentTarget) go(detalle); }}>
      <Portada src={r.portada} alt={r.alojamiento ?? "Alojamiento"} />
      <div className="stack" style={{ gap: 8, minWidth: 0 }}>
        <div className="row-between" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-start" }}>
          <div style={{ minWidth: 0 }}>
            <h3 style={{ margin: 0 }}>{r.alojamiento ?? `Alojamiento ${r.publicacion}`}</h3>
            {r.ciudad && <span className="muted row" style={{ gap: 4 }}><MapPin size={14} /> {r.ciudad}</span>}
          </div>
          <EstadoReserva r={r} />
        </div>
        <p className="muted" style={{ margin: 0 }}>
          {fecha(r.fecha_llegada)} al {fecha(r.fecha_salida)} · {r.noches} {r.noches === 1 ? "noche" : "noches"} · {r.num_huespedes} {r.num_huespedes === 1 ? "huésped" : "huéspedes"}
        </p>
        {vista === "anfitrion" && r.huesped_nombre && <p style={{ margin: 0 }}>Huésped: <b>{r.huesped_nombre}</b></p>}
        {vista === "admin" && (
          <p style={{ margin: 0 }}>Huésped: <b>{r.huesped_nombre ?? "—"}</b> · Anfitrión: <b>{r.anfitrion_nombre ?? "—"}</b></p>
        )}
        <p style={{ margin: 0 }}>Total: <b>{pesos(r.total)}</b></p>
        {vista === "huesped" && estaEnCurso(r) && <p className="muted" style={{ margin: 0 }}>{EN_CURSO_SIN_CANCELAR}</p>}
        {vista === "anfitrion" && r.estado === "EN_REVISION" && <p className="muted" style={{ margin: 0 }}>La resuelve el administrador antes de la llegada.</p>}
        {vista === "admin" && <DatosRevision r={r} />}
        {vista === "admin" && r.estado === "EN_REVISION" && <AvisoPlazo r={r} />}
        {vista !== "admin" && r.cancelacion && (
          <p className="muted" style={{ margin: 0 }}>
            {textoCancelada(r.cancelacion, vista)} Devolución: {pesos(r.cancelacion.valor_devolucion)} ({Number(r.cancelacion.porcentaje_devolucion)} %).
          </p>
        )}
        <div className="row" style={{ gap: 12, flexWrap: "wrap", marginTop: 2 }}>
          <Link to={enlace.to} onClick={parar}>{enlace.texto}</Link>
          {vista === "huesped" && r.cancelable && onCancelar && (
            <button className="btn btn-secondary btn-sm" onClick={(e) => { parar(e); onCancelar(); }}><XCircle /> Cancelar</button>
          )}
          {vista === "admin" && r.estado === "EN_REVISION" && onResolver && (
            <>
              <button className="btn btn-primary btn-sm" onClick={(e) => { parar(e); onResolver(true); }}>Mantener</button>
              <button className="btn btn-danger btn-sm" onClick={(e) => { parar(e); onResolver(false); }}>Cancelar con devolución</button>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

/** Pestañas con su número y la elegida en la URL (?pestana=; la primera no se escribe), con sus tarjetas. La usan las tres
 *  pantallas de reservas: huésped, anfitrión y Administrador. */
type PestanaDeReservas = { clave: string; nombre: string; vacia: string; lista: ReservaResumen[] };
function PestanasDeReservas({ pestanas, cargada, tarjeta, accionVacia }: {
  pestanas: PestanaDeReservas[]; cargada: boolean; tarjeta: (r: ReservaResumen) => React.ReactNode; accionVacia?: React.ReactNode;
}) {
  const [params, setParams] = useSearchParams();
  const actual = pestanas.find((p) => p.clave === params.get("pestana")) ?? pestanas[0];
  const elegir = (clave: string) => {
    const nuevos = new URLSearchParams(params);
    if (clave === pestanas[0].clave) nuevos.delete("pestana"); else nuevos.set("pestana", clave);
    setParams(nuevos, { replace: true });
  };
  return (
    <>
      <div className="chips" role="tablist" aria-label="Reservas">
        {pestanas.map((p) => (
          <button key={p.clave} role="tab" aria-selected={p.clave === actual.clave} className={`chip-toggle ${p.clave === actual.clave ? "on" : ""}`}
            onClick={() => elegir(p.clave)}>
            {p.nombre} ({cargada ? p.lista.length : "…"})
          </button>
        ))}
      </div>
      {cargada && actual.lista.length === 0 && (
        <div className="card empty-state"><CalendarCheck /><b>{actual.vacia}</b>{accionVacia}</div>
      )}
      <div className="stack" role="tabpanel" aria-label={actual.nombre}>{actual.lista.map((r) => tarjeta(r))}</div>
    </>
  );
}

/** Huésped y anfitrión: las pestañas salen de separarReservas. El anfitrión ve "En revisión" solo si hay. */
function ReservasConPestanas({ vista, lista, onCancelar }: { vista: Vista; lista: ReservaResumen[] | null; onCancelar?: (r: ReservaResumen) => void }) {
  const grupos = useMemo(() => separarReservas(lista ?? [], vista), [lista, vista]);
  const pestanas = PESTANAS.filter((p) => p.clave !== "revision" || (vista === "anfitrion" && grupos.revision.length > 0))
    .map((p) => ({ ...p, lista: grupos[p.clave] }));
  return (
    <PestanasDeReservas pestanas={pestanas} cargada={!!lista}
      accionVacia={vista === "huesped" && <Link className="btn btn-primary" to="/explorar"><Search /> Explorar alojamientos</Link>}
      tarjeta={(r) => <TarjetaConPortada key={r.id} r={r} vista={vista} onCancelar={onCancelar && (() => onCancelar(r))} />} />
  );
}

/* ---------------- HU-14 Mis reservas (huésped) ---------------- */
export function MisReservas() {
  const { lista, error, recargar } = useLista(misReservasApi.mias);
  const { abrir, ventana } = useCancelarReserva(recargar);
  return (
    <Page req="RF-D-RES-02.3 · RF-D-RES-03.1 · HU-14 · HU-15">
      <div className="page-head"><div><h1>Mis reservas</h1><p>Tus reservas próximas, pasadas y canceladas con su estado.</p></div></div>
      {error && <Alert tipo="error">{error}</Alert>}
      <ReservasConPestanas vista="huesped" lista={lista} onCancelar={abrir} />
      {ventana}
    </Page>
  );
}

/* ---------------- HU-26 Reservas de mis alojamientos (anfitrión) ---------------- */
export function ReservasDeMisAlojamientos() {
  const { lista, error } = useLista(misReservasApi.deMisAlojamientos);
  const [publicaciones, setPublicaciones] = useState<{ id: number; titulo: string }[]>([]);
  const [params, setParams] = useSearchParams();
  useEffect(() => {
    // Solo sus publicaciones: GET /catalogo/mis-publicaciones
    anfitrionApi.mias().then((ps) => setPublicaciones(ps.map((p) => ({ id: p.id, titulo: p.titulo })).sort((a, b) => a.titulo.localeCompare(b.titulo, "es"))))
      .catch(() => {});
  }, []);
  const alojamiento = Number(params.get("alojamiento")) || null;
  const filtrada = useMemo(() => lista && (alojamiento ? lista.filter((r) => r.publicacion === alojamiento) : lista), [lista, alojamiento]);
  const elegir = (valor: string) => {
    const nuevos = new URLSearchParams(params);
    if (valor) nuevos.set("alojamiento", valor); else nuevos.delete("alojamiento");
    setParams(nuevos, { replace: true });
  };
  return (
    <Page req="RF-D-RES-02.3 · HU-26">
      <div className="page-head"><div><h1>Reservas de mis alojamientos</h1><p>Las reservas de tus publicaciones, incluidas las canceladas.</p></div></div>
      <Field label="Alojamiento">
        <select className="select" value={alojamiento ?? ""} onChange={(e) => elegir(e.target.value)} style={{ maxWidth: 420 }}>
          <option value="">Todos</option>
          {publicaciones.map((p) => <option key={p.id} value={p.id}>{p.titulo}</option>)}
        </select>
      </Field>
      {error && <Alert tipo="error">{error}</Alert>}
      <ReservasConPestanas vista="anfitrion" lista={filtrada} />
    </Page>
  );
}

/* ---------------- Detalle de una reserva (MAL-34) ---------------- */
const TIPO_PAGO: Record<string, string> = { COBRO: "Cobro", DEVOLUCION: "Devolución" };
const ESTADO_PAGO: Record<string, string> = { APROBADO: "Aprobado", RECHAZADO: "Rechazado", EN_VERIFICACION: "En verificación" };

function textoTramo(t: { dias_minimos: number; dias_maximos: number | null }) {
  const d = (n: number) => `${n} ${n === 1 ? "día" : "días"}`;
  if (t.dias_maximos == null) return `${d(t.dias_minimos)} o más antes de la llegada`;
  if (t.dias_minimos === 0) return `Menos de ${d(t.dias_maximos + 1)} antes de la llegada`;
  return `De ${t.dias_minimos} a ${d(t.dias_maximos)} antes de la llegada`;
}

const Linea = ({ izq, der, fuerte }: { izq: React.ReactNode; der: React.ReactNode; fuerte?: boolean }) => (
  <div className="row-between" style={{ gap: 12, fontWeight: fuerte ? 700 : undefined }}><span>{izq}</span><span style={{ whiteSpace: "nowrap" }}>{der}</span></div>
);

export function DetalleReserva({ admin = false }: { admin?: boolean }) {
  const { id } = useParams();
  const { usuario, tiene } = useStore();
  const go = useNavigate();
  const [r, setR] = useState<ReservaDetalleApi | null>(null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => {
    (admin ? misReservasApi.detalleAdmin : misReservasApi.detalle)(Number(id))
      .then((x) => { setR(x.data); setError(""); }).catch((e) => setError(leerError(e).error));
  }, [id, admin]);
  useEffect(() => { setR(null); setError(""); }, [id]);  // otra reserva: no mostrar la anterior mientras carga
  useEffect(cargar, [cargar]);
  const { abrir, ventana } = useCancelarReserva(cargar);
  const resolver = useResolverReserva(cargar);
  const esHuesped = !!r && r.huesped === usuario?.id;
  const esAnfitrion = !!r && !esHuesped && r.anfitrion === usuario?.id;
  // Volver a la lista de donde viene: Mis reservas (huésped) o Reservas de mis alojamientos (anfitrión)
  const volver = admin ? { to: "/admin/reservas", texto: "Reservas en revisión" }
    : esHuesped || (!r && tiene("reservas.ver_propias")) ? { to: "/reservas", texto: "Mis reservas" }
    : esAnfitrion || (!r && tiene("reservas.ver_de_mis_alojamientos")) ? { to: "/reservas-alojamientos", texto: "Reservas de mis alojamientos" } : null;
  const enlaceVolver = volver
    ? <Link to={volver.to} className="row" style={{ gap: 4 }}><ArrowLeft size={16} /> {volver.texto}</Link>
    : <button className="link-btn row" style={{ gap: 4 }} onClick={() => go(-1)}><ArrowLeft size={16} /> Volver</button>;

  if (error) return <Page req="HU-14">{enlaceVolver}<Alert tipo="error">{error}</Alert></Page>;
  if (!r) return <Page req="HU-14"><p className="muted">Cargando la reserva…</p></Page>;
  const d = r.desglose;
  const dev = r.devolucion_hoy;

  return (
    <Page req="RF-D-RES-02.3 · RF-D-RES-03.1 · HU-14 · HU-15">
      {enlaceVolver}
      <div className="detalle-reserva">
        <section className="card stack" style={{ gap: 12 }}>
          <Portada src={r.portada} alt={r.alojamiento ?? "Alojamiento"} className="portada-grande" />
          <div className="row-between" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-start" }}>
            <div>
              <h1 style={{ margin: 0 }}>{r.alojamiento ?? `Alojamiento ${r.publicacion}`}</h1>
              {r.ciudad && <span className="muted row" style={{ gap: 4 }}><MapPin size={15} /> {r.ciudad}</span>}
            </div>
            <EstadoReserva r={r} />
          </div>
          <div className="stack" style={{ gap: 6 }}>
            <Linea izq="Fechas" der={`${fecha(r.fecha_llegada)} al ${fecha(r.fecha_salida)}`} />
            <Linea izq="Noches" der={r.noches} />
            <Linea izq="Huéspedes" der={r.num_huespedes} />
            {!esHuesped && r.huesped_nombre && <Linea izq="Huésped" der={r.huesped_nombre} />}
            {!esAnfitrion && r.anfitrion_nombre && <Linea izq="Anfitrión" der={r.anfitrion_nombre} />}
            <Linea izq="Reserva" der={`#${r.id}`} />
          </div>
          {esHuesped || esAnfitrion
            ? <Link to={enlacePublicacion(esHuesped ? "huesped" : "anfitrion", r.publicacion).to}>{esHuesped ? "Ver alojamiento" : "Ver publicación"}</Link>
            : <Link to={`/admin/publicaciones/${r.publicacion}`}>Ver publicación</Link>}
        </section>

        <div className="stack">
          {admin && (r.bloqueo || r.resolucion) && (
            <section className="card stack" style={{ gap: 8 }}>
              <h2 style={{ margin: 0 }}>Revisión</h2>
              <DatosRevision r={r} />
            </section>
          )}
          {admin && r.estado === "EN_REVISION" && (
            <>
              <AvisoPlazo r={r} />
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                <button className="btn btn-primary" onClick={() => resolver.abrir(r, true)}>Mantener</button>
                <button className="btn btn-danger" onClick={() => resolver.abrir(r, false)}>Cancelar con devolución</button>
              </div>
            </>
          )}
          {!admin && r.estado === "CANCELADA" && r.cancelacion && (
            <Alert tipo="info">
              {textoCancelada(r.cancelacion, esHuesped ? "huesped" : "anfitrion")}{" "}
              Motivo: {r.cancelacion.motivo.replace(/\.$/, "")}. Valor devuelto: <b>{pesos(r.cancelacion.valor_devolucion)}</b> ({Number(r.cancelacion.porcentaje_devolucion)} %).
            </Alert>
          )}
          {dev && esHuesped && (dev.cancelable ? (
            <Alert tipo={Number(dev.valor_devolucion) > 0 ? "info" : "warn"}>
              Faltan {dev.dias_anticipacion} {dev.dias_anticipacion === 1 ? "día" : "días"}. Si cancelas hoy te devolvemos{" "}
              <b>{pesos(dev.valor_devolucion)}</b> ({Number(dev.porcentaje_devolucion)} %).
            </Alert>
          ) : <Alert tipo="warn">{estaEnCurso(r) ? EN_CURSO_SIN_CANCELAR : "Esta reserva ya no se puede cancelar."}</Alert>)}

          <section className="card stack" style={{ gap: 8 }}>
            <h2 style={{ margin: 0 }}>Desglose del pago</h2>
            <Linea izq={`${pesos(d.precio_noche)} x ${d.noches} ${d.noches === 1 ? "noche" : "noches"}`} der={pesos(d.precio_base)} />
            {Number(d.descuento) > 0 && <Linea izq="Descuento por estancia larga" der={`-${pesos(d.descuento)}`} />}
            <Linea izq="Tarifa de limpieza" der={pesos(d.tarifa_limpieza)} />
            <Linea izq={`Tarifa de servicio (${Number(d.porcentaje_servicio)} %)`} der={pesos(d.tarifa_servicio)} />
            {d.adicionales.map((a) => <Linea key={a.id} izq={a.nombre ?? "Servicio adicional"} der={pesos(a.precio_aplicado)} />)}
            <hr style={{ border: 0, borderTop: "1px solid var(--border)", margin: "4px 0" }} />
            <Linea izq="Total" der={pesos(d.total)} fuerte />
            <p className="subtle" style={{ margin: 0 }}>Valores guardados al reservar.</p>
          </section>

          {r.politica_cancelacion && (
            <section className="card stack" style={{ gap: 8 }}>
              <h2 style={{ margin: 0 }}>Política de cancelación: {r.politica_cancelacion.nombre}</h2>
              {r.politica_cancelacion.tramos.map((t) => (
                <Linea key={t.dias_minimos} izq={textoTramo(t)} der={`${Number(t.porcentaje_devolucion)} %`} />
              ))}
            </section>
          )}

          {!esAnfitrion && <section className="card stack" style={{ gap: 8 }}>
            <h2 style={{ margin: 0 }}>Pago</h2>
            {r.pagos.length === 0 && <p className="muted" style={{ margin: 0 }}>Sin pagos registrados.</p>}
            {r.pagos.map((p) => (
              <div key={p.id} className="stack" style={{ gap: 2 }}>
                <Linea izq={`${TIPO_PAGO[p.tipo] ?? p.tipo} · ${ESTADO_PAGO[p.estado] ?? p.estado}`} der={pesos(p.monto)} />
                <span className="subtle">Referencia: {p.referencia_externa ?? "—"}</span>
              </div>
            ))}
          </section>}

          {esHuesped && r.cancelable && (
            <div><button className="btn btn-secondary" onClick={() => abrir(r)}><XCircle /> Cancelar</button></div>
          )}
        </div>
      </div>
      {ventana}
      {resolver.ventana}
    </Page>
  );
}

/* ---------------- HU-20 Reservas en revisión (Administrador, RF-D-ADM-01.2) ---------------- */
export function ReservasEnRevision() {
  const pendientes = useLista(misReservasApi.enRevision);
  const resueltas = useLista(misReservasApi.resueltas);
  const recargar = () => { pendientes.recargar(); resueltas.recargar(); };
  const { abrir, ventana } = useResolverReserva(recargar);
  const pestanas = [
    { clave: "pendientes", nombre: "Pendientes", vacia: "No hay reservas en revisión", lista: pendientes.lista ?? [] },
    { clave: "resueltas", nombre: "Resueltas", vacia: "Todavía no hay reservas resueltas", lista: resueltas.lista ?? [] },
  ];
  return (
    <Page req="RF-D-ADM-01.2 · HU-20">
      <div className="page-head"><div><h1>Reservas en revisión</h1><p>Reservas de publicaciones bloqueadas. Si nadie las resuelve antes de la llegada, se cancelan solas con devolución del 100 %.</p></div></div>
      {(pendientes.error || resueltas.error) && <Alert tipo="error">{pendientes.error || resueltas.error}</Alert>}
      <PestanasDeReservas pestanas={pestanas} cargada={!!pendientes.lista && !!resueltas.lista}
        tarjeta={(r) => <TarjetaConPortada key={r.id} r={r} vista="admin" onResolver={(mantener) => abrir(r, mantener)} />} />
      {ventana}
    </Page>
  );
}

/* ---------------- HU-16 Bandeja de avisos ---------------- */
export function Avisos() {
  const [datos, setDatos] = useState<{ no_leidas: number; notificaciones: NotificacionApi[] } | null>(null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => {
    notificacionesApi.bandeja().then((r) => setDatos(r.data)).catch((e) => setError(leerError(e).error));
  }, []);
  useEffect(cargar, [cargar]);
  const avisar = () => window.dispatchEvent(new Event("avisos-cambiaron"));  // actualiza la campana

  return (
    <Page req="RF-D-RES-04.1 · HU-16">
      <div className="page-head">
        <div><h1>Avisos</h1><p>{datos ? `${datos.no_leidas} sin leer` : "Cargando…"}</p></div>
        {!!datos?.no_leidas && (
          <button className="btn btn-secondary" onClick={async () => { await notificacionesApi.marcarTodas(); cargar(); avisar(); }}>
            <CheckCheck /> Marcar todos como leídos
          </button>
        )}
      </div>
      {error && <Alert tipo="error">{error}</Alert>}
      {datos && datos.notificaciones.length === 0 && <div className="card empty-state"><Inbox /><b>No tienes avisos</b></div>}
      <div className="stack" style={{ gap: 10 }}>
        {(datos?.notificaciones ?? []).map((n) => (
          <section key={n.id} className="card row-between" style={{ gap: 12, alignItems: "flex-start", borderLeft: n.leida ? undefined : "4px solid var(--accent)" }}>
            <div className="stack" style={{ gap: 4 }}>
              <span className="row" style={{ gap: 6, fontWeight: n.leida ? 400 : 700 }}><Bell size={15} /> {n.mensaje}</span>
              <span className="subtle">{fechaHora(n.fecha)}</span>
            </div>
            {!n.leida && (
              <button className="btn btn-ghost btn-sm" onClick={async () => { await notificacionesApi.marcarLeida(n.id); cargar(); avisar(); }}>
                Marcar leído
              </button>
            )}
          </section>
        ))}
      </div>
    </Page>
  );
}
