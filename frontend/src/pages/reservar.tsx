import { CardElement, Elements, useElements, useStripe } from "@stripe/react-stripe-js";
import { loadStripe } from "@stripe/stripe-js";
import { isAxiosError } from "axios";
import { ArrowLeft, CalendarCheck, CreditCard, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { leerError, reservasApi, type CotizacionApi, type ReservaApi } from "../api";
import { cop } from "../data";
import { Page } from "../layout";
import { Alert } from "../ui";

/* Stripe en modo prueba solo si existe la llave pública (ADR-006). La llave secreta nunca llega al navegador. */
const LLAVE_PUBLICA = import.meta.env.VITE_STRIPE_PUBLIC_KEY as string | undefined;
const stripePromise = LLAVE_PUBLICA ? loadStripe(LLAVE_PUBLICA) : null;

const pesos = (v: string) => cop(Number(v));
const fechaLarga = (f: string) => new Date(f + "T12:00:00").toLocaleDateString("es-CO", { weekday: "short", day: "numeric", month: "long", year: "numeric" });

/** UUID v4 para la clave de idempotencia (RNF-P-FIA-02). crypto.randomUUID solo existe en contextos seguros. */
function nuevaClave(): string {
  const c: Crypto = globalThis.crypto;
  if (typeof c.randomUUID === "function") return c.randomUUID();
  const b = c.getRandomValues(new Uint8Array(16));
  b[6] = (b[6]! & 0x0f) | 0x40; b[8] = (b[8]! & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** Desglose de la cotización: noches × precio, descuento, limpieza, tarifa de servicio, adicionales y total (CA-12.1). */
function Desglose({ c }: { c: CotizacionApi }) {
  const fila = (etiqueta: string, valor: string, negativo = false) => (
    <li style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span>{etiqueta}</span><span>{negativo ? "− " : ""}{pesos(valor)}</span></li>
  );
  return (
    <ul className="list-plain stack" style={{ gap: 8 }}>
      {fila(`${pesos(c.precio_noche)} x ${c.noches} ${c.noches === 1 ? "noche" : "noches"}`, c.precio_base)}
      {Number(c.descuento) > 0 && fila("Descuento por estancia larga", c.descuento, true)}
      {fila("Tarifa de limpieza", c.tarifa_limpieza)}
      {fila(`Tarifa de servicio (${Number(c.porcentaje_servicio)} %)`, c.tarifa_servicio)}
      {c.adicionales.map((a) => <li key={a.id} style={{ display: "flex", justifyContent: "space-between" }}><span>{a.nombre ?? "Servicio adicional"}</span><span>{pesos(a.precio_aplicado)}</span></li>)}
      <li style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid var(--border)", paddingTop: 8, fontWeight: 700 }}>
        <span>Total</span><span>{pesos(c.total)}</span>
      </li>
    </ul>
  );
}

/** Pago con Stripe Elements: la tarjeta se tokeniza en el navegador y al backend solo llega el payment_method. */
function PagoStripe({ enviando, onPagar, onError }: { enviando: boolean; onPagar: (medio: string) => void; onError: (m: string) => void }) {
  const stripe = useStripe();
  const elements = useElements();
  const [preparando, setPreparando] = useState(false);
  const pagar = async () => {
    const tarjeta = elements?.getElement(CardElement);
    if (!stripe || !tarjeta) return;
    setPreparando(true);
    const { paymentMethod, error } = await stripe.createPaymentMethod({ type: "card", card: tarjeta });
    setPreparando(false);
    if (error || !paymentMethod) return onError(error?.message ?? "No se pudo leer la tarjeta.");
    onPagar(paymentMethod.id);
  };
  return (
    <div className="stack">
      <div className="input" style={{ padding: "12px 10px" }}><CardElement options={{ hidePostalCode: true }} /></div>
      <p className="subtle">Modo de prueba de Stripe: usa la tarjeta 4242 4242 4242 4242, cualquier fecha futura y cualquier CVC.</p>
      <button className="btn btn-primary btn-block" disabled={!stripe || enviando || preparando} onClick={pagar}>
        <CreditCard /> {enviando || preparando ? "Procesando pago…" : "Reservar y pagar"}
      </button>
    </div>
  );
}

/** Pago simulado (sin llave de Stripe): permite forzar un rechazo para la demostración (CA-13.3). */
function PagoSimulado({ enviando, onPagar }: { enviando: boolean; onPagar: (medio: string) => void }) {
  const [rechazar, setRechazar] = useState(false);
  return (
    <div className="stack">
      <Alert tipo="info">Pago simulado: no se cobra dinero real.</Alert>
      <label className="row" style={{ gap: 8 }}>
        <input type="checkbox" checked={rechazar} onChange={(e) => setRechazar(e.target.checked)} /> Forzar el rechazo del pago (demostración)
      </label>
      <button className="btn btn-primary btn-block" disabled={enviando} onClick={() => onPagar(rechazar ? "rechazar" : "simulado")}>
        <CreditCard /> {enviando ? "Procesando pago…" : "Reservar y pagar"}
      </button>
    </div>
  );
}

/* ---------------- HU-12 Cotización y HU-13 Reservar y pagar ---------------- */
export function CotizacionPage() {
  const { id } = useParams();
  const go = useNavigate();
  const [c, setC] = useState<CotizacionApi | null>(null);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [fechasOcupadas, setFechasOcupadas] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [reserva, setReserva] = useState<ReservaApi | null>(null);
  // Una clave por intento: si la petición se corta y se repite, el servidor reconoce la misma solicitud
  // y no cobra dos veces (CA-13.4). Después de un 402 o un 409 el siguiente intento lleva clave nueva.
  const clave = useRef<string | null>(null);

  useEffect(() => {
    setError(""); setFechasOcupadas(false);
    reservasApi.cotizacion(Number(id)).then((r) => setC(r.data)).catch((e) => setError(leerError(e).error));
  }, [id]);

  const pagar = async (medio: string) => {
    if (!c || enviando) return;
    setError(""); setAviso("");
    clave.current ??= nuevaClave();
    setEnviando(true);
    try {
      const { data } = await reservasApi.reservar({ cotizacion: c.id, clave_idempotencia: clave.current, medio_pago: medio });
      setReserva(data);
    } catch (e) {
      if (!isAxiosError(e) || !e.response) {
        setError("No hubo respuesta del servidor. Puedes intentar de nuevo: no se cobrará dos veces.");
        return;  // se conserva la clave para el reintento
      }
      clave.current = null;
      const d = e.response.data as { detalle?: string; cotizacion?: CotizacionApi };
      if (e.response.status === 409 && d.cotizacion) {  // el precio cambió: se muestra la cotización nueva
        setC(d.cotizacion);
        setAviso(d.detalle ?? "El precio cambió. Revisa la cotización nueva.");
        go(`/cotizacion/${d.cotizacion.id}`, { replace: true });
      } else if (e.response.status === 409) {  // CA-13.2: las fechas se ocuparon
        setFechasOcupadas(true);
        setError(d.detalle ?? "Las fechas ya no están disponibles.");
      } else {  // 402: pago rechazado (CA-13.3) u otro error
        setError(leerError(e).error);
      }
    } finally {
      setEnviando(false);
    }
  };

  if (!c) return <Page req="RF-D-RES-02.1 · HU-12">{error ? <Alert tipo="error">{error}</Alert> : <p className="muted">Cargando…</p>}</Page>;
  const volver = `/explorar/${c.publicacion}`;

  if (reserva)
    return (
      <Page req="RF-D-RES-02.2 · HU-13 · CA-13.1">
        <section className="card stack" style={{ maxWidth: 560 }}>
          <span className="ico-big" style={{ background: "var(--ok-soft, #e3f4ee)", color: "var(--ok)" }}><CalendarCheck /></span>
          <h1>Reserva confirmada</h1>
          <p>{c.publicacion_titulo}</p>
          <ul className="list-plain stack" style={{ gap: 6 }}>
            <li>Llegada: <b>{fechaLarga(reserva.fecha_llegada)}</b></li>
            <li>Salida: <b>{fechaLarga(reserva.fecha_salida)}</b></li>
            <li>Huéspedes: <b>{reserva.num_huespedes}</b></li>
            <li>Total pagado: <b>{pesos(reserva.total)}</b></li>
            {reserva.pagos[0]?.referencia_externa && <li className="subtle">Referencia del pago: {reserva.pagos[0].referencia_externa}</li>}
          </ul>
          <Alert tipo="ok">Estado: {reserva.estado}. Tus noches quedaron reservadas.</Alert>
          <Link className="btn btn-secondary" to="/explorar">Seguir explorando</Link>
        </section>
      </Page>
    );

  return (
    <Page req="RF-D-RES-02.1 · RF-D-RES-02.2 · HU-12 · HU-13">
      <Link to={volver} className="back"><ArrowLeft /> Volver al alojamiento</Link>
      <div className="page-head"><div><h1>Tu cotización</h1><p>{c.publicacion_titulo}</p></div></div>
      {aviso && <Alert tipo="warn">{aviso}</Alert>}
      <div className="detail-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,1.3fr) minmax(0,1fr)", gap: 20, alignItems: "start" }}>
        <section className="card stack">
          <h3>Estancia</h3>
          <p>{fechaLarga(c.fecha_llegada)} al {fechaLarga(c.fecha_salida)} · {c.num_huespedes} {c.num_huespedes === 1 ? "huésped" : "huéspedes"}</p>
          <h3>Desglose</h3>
          <Desglose c={c} />
          {c.vencida && <Alert tipo="warn">Esta cotización venció (dura 30 minutos). Al reservar se recalcula con los precios de hoy.</Alert>}
        </section>
        <aside className="card stack">
          <div className="card-title"><span className="ico"><ShieldCheck /></span><h3>Pago</h3></div>
          {c.reserva ? <Alert tipo="info">Esta cotización ya se usó en una reserva.</Alert> : stripePromise ? (
            <Elements stripe={stripePromise}>
              <PagoStripe enviando={enviando} onPagar={pagar} onError={setError} />
            </Elements>
          ) : <PagoSimulado enviando={enviando} onPagar={pagar} />}
          {error && <Alert tipo="error">{error}</Alert>}
          {fechasOcupadas && <Link className="btn btn-secondary btn-block" to={volver}>Elegir otras fechas</Link>}
        </aside>
      </div>
    </Page>
  );
}
