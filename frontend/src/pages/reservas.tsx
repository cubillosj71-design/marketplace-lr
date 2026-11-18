import { Bell, CalendarCheck, CheckCheck, ClipboardCheck, Inbox, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  leerError, misReservasApi, notificacionesApi,
  type NotificacionApi, type ReservaResumen, type SimulacionCancelacion,
} from "../api";
import { cop } from "../data";
import { Page } from "../layout";
import { useToast } from "../store";
import { Alert, Field, Modal } from "../ui";

const pesos = (v: string) => cop(Number(v));
const fecha = (f: string) => new Date(f + "T12:00:00").toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
const fechaHora = (f: string) => new Date(f).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" }).replace(/\.$/, "");

const CLASE_ESTADO: Record<ReservaResumen["estado"], string> = {
  CONFIRMADA: "badge-ACTIVA", COMPLETADA: "badge-PENDIENTE_REVISION", CANCELADA: "badge-BLOQUEADA", EN_REVISION: "badge-PAUSADA",
};
const EstadoReserva = ({ estado }: { estado: ReservaResumen["estado"] }) =>
  <span className={`badge ${CLASE_ESTADO[estado]}`}>{estado.replace("_", " ")}</span>;

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

function TarjetaReserva({ r, verHuesped, children }: { r: ReservaResumen; verHuesped?: boolean; children?: React.ReactNode }) {
  return (
    <section className="card stack" style={{ gap: 10 }}>
      <div className="row-between" style={{ gap: 8, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0 }}>{r.alojamiento ?? `Alojamiento ${r.publicacion}`}</h3>
        <EstadoReserva estado={r.estado} />
      </div>
      <p className="muted" style={{ margin: 0 }}>
        {fecha(r.fecha_llegada)} al {fecha(r.fecha_salida)} · {r.noches} {r.noches === 1 ? "noche" : "noches"} · {r.num_huespedes} {r.num_huespedes === 1 ? "huésped" : "huéspedes"}
        {verHuesped && r.huesped_nombre ? ` · ${r.huesped_nombre}` : ""}
      </p>
      <p style={{ margin: 0 }}>Total: <b>{pesos(r.total)}</b></p>
      {r.cancelacion && (
        <Alert tipo="info">
          Cancelada el {fechaHora(r.cancelacion.fecha)}{r.cancelacion.automatica ? " por el sistema" : ""}.{" "}
          Motivo: {r.cancelacion.motivo.replace(/\.$/, "")}. Devolución: {pesos(r.cancelacion.valor_devolucion)} ({Number(r.cancelacion.porcentaje_devolucion)} %).
        </Alert>
      )}
      {children}
    </section>
  );
}

/* ---------------- HU-14 Mis reservas y HU-15 Cancelar ---------------- */
export function MisReservas() {
  const toast = useToast();
  const { lista, error, recargar } = useLista(misReservasApi.mias);
  const [cancelar, setCancelar] = useState<{ r: ReservaResumen; sim: SimulacionCancelacion | null } | null>(null);
  const [motivo, setMotivo] = useState("");
  const [errModal, setErrModal] = useState("");
  const [enviando, setEnviando] = useState(false);

  const abrir = async (r: ReservaResumen) => {
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
      recargar();
    } catch (e) { setErrModal(leerError(e).error); }
    finally { setEnviando(false); }
  };

  return (
    <Page req="RF-D-RES-02.3 · RF-D-RES-03.1 · HU-14 · HU-15">
      <div className="page-head"><div><h1>Mis reservas</h1><p>Tus reservas actuales y pasadas con su estado.</p></div></div>
      {error && <Alert tipo="error">{error}</Alert>}
      {lista && lista.length === 0 && <div className="card empty-state"><CalendarCheck /><b>Todavía no tienes reservas</b></div>}
      <div className="stack">
        {(lista ?? []).map((r) => (
          <TarjetaReserva key={r.id} r={r}>
            {r.cancelable && <div><button className="btn btn-secondary" onClick={() => abrir(r)}><XCircle /> Cancelar</button></div>}
          </TarjetaReserva>
        ))}
      </div>
      {cancelar && (
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
      )}
    </Page>
  );
}

/* ---------------- HU-26 Reservas de mis alojamientos ---------------- */
export function ReservasDeMisAlojamientos() {
  const { lista, error } = useLista(misReservasApi.deMisAlojamientos);
  const [filtro, setFiltro] = useState("");
  const visibles = (lista ?? []).filter((r) => !filtro || r.estado === filtro);
  return (
    <Page req="RF-D-RES-02.3 · HU-26">
      <div className="page-head"><div><h1>Reservas de mis alojamientos</h1><p>Las reservas de tus publicaciones, incluidas las canceladas.</p></div></div>
      <div className="row" style={{ gap: 8 }}>
        <select className="select" value={filtro} onChange={(e) => setFiltro(e.target.value)} aria-label="Estado" style={{ maxWidth: 240 }}>
          <option value="">Todos los estados</option>
          {["CONFIRMADA", "EN_REVISION", "COMPLETADA", "CANCELADA"].map((e) => <option key={e} value={e}>{e.replace("_", " ")}</option>)}
        </select>
      </div>
      {error && <Alert tipo="error">{error}</Alert>}
      {lista && visibles.length === 0 && <div className="card empty-state"><CalendarCheck /><b>No hay reservas para mostrar</b></div>}
      <div className="stack">{visibles.map((r) => <TarjetaReserva key={r.id} r={r} verHuesped />)}</div>
    </Page>
  );
}

/* ---------------- HU-20 Reservas en revisión (Administrador) ---------------- */
export function ReservasEnRevision() {
  const toast = useToast();
  const { lista, error, recargar } = useLista(misReservasApi.enRevision);
  const [cancelar, setCancelar] = useState<ReservaResumen | null>(null);
  const [motivo, setMotivo] = useState("");
  const [errModal, setErrModal] = useState("");
  const [enviando, setEnviando] = useState<number | null>(null);

  const resolver = async (r: ReservaResumen, mantener: boolean) => {
    if (!mantener && !motivo.trim()) return setErrModal("Escribe el motivo de la cancelación.");
    setEnviando(r.id);
    try {
      await misReservasApi.resolver(r.id, mantener, mantener ? undefined : motivo.trim());
      toast(mantener ? "La reserva vuelve a CONFIRMADA" : "Reserva cancelada con devolución del 100 %");
      setCancelar(null);
      recargar();
    } catch (e) {
      if (mantener) toast(leerError(e).error, "err"); else setErrModal(leerError(e).error);
    } finally { setEnviando(null); }
  };

  return (
    <Page req="RF-D-ADM-01.2 · HU-20">
      <div className="page-head"><div><h1>Reservas en revisión</h1><p>Reservas de publicaciones bloqueadas. Si nadie las resuelve antes de la llegada, se cancelan solas con devolución del 100 %.</p></div></div>
      {error && <Alert tipo="error">{error}</Alert>}
      {lista && lista.length === 0 && <div className="card empty-state"><ClipboardCheck /><b>No hay reservas en revisión</b></div>}
      <div className="stack">
        {(lista ?? []).map((r) => (
          <TarjetaReserva key={r.id} r={r} verHuesped>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-primary" disabled={enviando === r.id} onClick={() => resolver(r, true)}>Mantener</button>
              <button className="btn btn-danger" disabled={enviando === r.id} onClick={() => { setMotivo(""); setErrModal(""); setCancelar(r); }}>Cancelar con devolución</button>
            </div>
          </TarjetaReserva>
        ))}
      </div>
      {cancelar && (
        <Modal onClose={() => setCancelar(null)}>
          <h2>Cancelar la reserva</h2>
          <Alert tipo="info">Se devuelve el 100 %: <b>{pesos(cancelar.total)}</b>. El huésped y el anfitrión reciben un aviso.</Alert>
          <Field label="Motivo" error={errModal}>
            <textarea className="input" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </Field>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setCancelar(null)}>Volver</button>
            <button className="btn btn-primary" style={{ background: "var(--err)" }} disabled={enviando === cancelar.id} onClick={() => resolver(cancelar, false)}>
              Cancelar reserva
            </button>
          </div>
        </Modal>
      )}
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
