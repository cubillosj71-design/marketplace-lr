import { CalendarDays, ChevronLeft, ChevronRight, Info, Lock, Unlock } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { isAxiosError } from "axios";
import { anfitrionApi, leerError, misReservasApi, type PublicacionAdmin, type ReservaResumen } from "../api";
import { fechaLarga, isoDia } from "../data";
import { Page } from "../layout";
import { useToast } from "../store";
import { Alert, Badge } from "../ui";

const DOW = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const siguiente = (iso: string) => { const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() + 1); return isoDia(d); };

/** Noches de [inicio, fin): la noche de fin no se incluye (así guarda la API los periodos). */
function noches(inicio: string, fin: string): string[] {
  const out: string[] = [];
  for (let f = inicio; f < fin; f = siguiente(f)) out.push(f);
  return out;
}

/* =========================================================
   CU-ALO-06 Bloquear o liberar fechas del calendario (GET y POST /catalogo/publicaciones/{id}/calendario)
   ========================================================= */
export function Calendario() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const hoy = isoDia(new Date());
  const [mias, setMias] = useState<PublicacionAdmin[] | null>(null);
  const [reservas, setReservas] = useState<ReservaResumen[]>([]);
  const [ocupadas, setOcupadas] = useState<Set<string>>(new Set());
  const [bloqueadas, setBloqueadas] = useState<Set<string>>(new Set());
  const base = new Date(hoy + "T12:00:00");
  const [mes, setMes] = useState({ y: base.getFullYear(), m: base.getMonth() });
  const [sel, setSel] = useState<{ a: string; b?: string } | null>(null);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    anfitrionApi.mias().then((l) => setMias(l.filter((p) => p.estado !== "BLOQUEADA"))).catch((e) => setError(leerError(e).error));
    // Sin las reservas el calendario parecería libre: se avisa en vez de callar el error
    misReservasApi.deMisAlojamientos().then((r) => setReservas(r.data))
      .catch((e) => setError(`No se pudieron cargar las reservas de tus alojamientos: ${leerError(e).error}`));
  }, []);

  const pubId = Number(params.get("pub")) || mias?.[0]?.id;
  const pub = mias?.find((p) => p.id === pubId);
  const desde = isoDia(new Date(mes.y, mes.m, 1, 12));
  const hasta = isoDia(new Date(mes.y, mes.m + 1, 1, 12));

  const cargar = useCallback(() => {
    if (!pub) return;
    anfitrionApi.calendario(pub.id, desde, hasta)
      .then(({ data }) => {
        setOcupadas(new Set(data.noches_reservadas));
        setBloqueadas(new Set(data.periodos.filter((x) => !x.disponible).flatMap((x) => noches(x.fecha_inicio, x.fecha_fin))));
      })
      .catch((e) => setError(leerError(e).error));
  }, [pub, desde, hasta]);
  useEffect(cargar, [cargar]);

  const dias = useMemo(() => {
    const primero = new Date(mes.y, mes.m, 1, 12);
    const vacios = (primero.getDay() + 6) % 7; // semana desde el lunes
    const total = new Date(mes.y, mes.m + 1, 0).getDate();
    return [
      ...Array.from({ length: vacios }, () => null),
      ...Array.from({ length: total }, (_, i) => isoDia(new Date(mes.y, mes.m, i + 1, 12))),
    ];
  }, [mes]);

  const rango = (): string[] => {
    if (!sel) return [];
    const [a, b] = [sel.a, sel.b ?? sel.a].sort();
    return noches(a!, siguiente(b!));
  };
  const seleccion = new Set(rango());

  const clic = (f: string) => {
    setError("");
    if (f < hoy) return;
    if (!sel || sel.b) setSel({ a: f });
    else setSel({ a: sel.a, b: f });
  };

  const accion = async (tipo: "NO_DISPONIBLE" | "DISPONIBLE") => {
    const r = rango();
    if (!pub || !r.length) return;
    setGuardando(true);
    try {
      await anfitrionApi.modificarCalendario(pub.id, r[0]!, siguiente(r[r.length - 1]!), tipo);
      toast(tipo === "NO_DISPONIBLE" ? "Fechas marcadas como no disponibles" : "Fechas disponibles de nuevo");
      setSel(null);
      cargar();
    } catch (e) {
      // CA-09.2: no se bloquean noches con una reserva CONFIRMADA; la API manda cuáles
      const choque = isAxiosError(e) ? ((e.response?.data as { fechas?: string[] })?.fechas ?? []) : [];
      setError(choque.length
        ? `No se puede bloquear ${choque.length > 1 ? `del ${fechaLarga(choque[0]!)} al ${fechaLarga(choque[choque.length - 1]!)}` : `el ${fechaLarga(choque[0]!)}`}: ${choque.length > 1 ? "tienen" : "tiene"} una reserva confirmada.`
        : leerError(e).error);
    } finally {
      setGuardando(false);
    }
  };

  const mover = (d: number) => setMes(({ y, m }) => { const nd = new Date(y, m + d, 1); return { y: nd.getFullYear(), m: nd.getMonth() }; });
  const t0 = new Date(mes.y, mes.m, 1).toLocaleDateString("es-CO", { month: "long", year: "numeric" });
  const titulo = t0[0]!.toUpperCase() + t0.slice(1);
  const r = rango();
  const futuras = pub ? reservas.filter((x) => x.publicacion === pub.id && x.estado === "CONFIRMADA" && x.fecha_salida >= hoy) : [];

  if (!mias) return <Page req="RF-D-ALO-02.2"><p className="muted">{error || "Cargando…"}</p></Page>;
  if (!mias.length)
    return <Page req="RF-D-ALO-02.2"><div className="card empty-state"><CalendarDays /><b>Aún no tienes publicaciones con calendario</b><Link className="btn btn-primary" to="/publicaciones/nueva">Crear publicación</Link></div></Page>;

  return (
    <Page req="RF-D-ALO-02.2 · CU-ALO-06 · HU-09">
      <div className="page-head">
        <div><h1>Calendario de disponibilidad</h1><p>Marca las fechas en que recibes y en las que no recibirás huéspedes.</p></div>
        <div className="field" style={{ minWidth: 0, flex: "1 1 260px", maxWidth: 360 }}>
          <span className="label">Alojamiento</span>
          <select className="select" value={pub?.id} onChange={(e) => { setParams({ pub: e.target.value }); setSel(null); setError(""); }}>
            {mias.map((p) => <option key={p.id} value={p.id}>{p.titulo || "Sin título"}</option>)}
          </select>
        </div>
      </div>

      <div className="cal-wrap">
        <section className="card">
          <div className="cal-head">
            <button className="icon-btn" onClick={() => mover(-1)} aria-label="Mes anterior"><ChevronLeft /></button>
            <h2>{titulo}</h2>
            <button className="icon-btn" onClick={() => mover(1)} aria-label="Mes siguiente"><ChevronRight /></button>
          </div>
          <div className="cal-grid">
            {DOW.map((d) => <div key={d} className="cal-dow">{d}</div>)}
            {dias.map((f, i) => {
              if (!f) return <div key={"v" + i} className="day empty" />;
              const pasado = f < hoy;
              const occ = ocupadas.has(f);
              const blk = bloqueadas.has(f);
              const cls = ["day", pasado && "past", occ && "occupied", !occ && blk && "blocked", seleccion.has(f) && "sel", f === hoy && "today"].filter(Boolean).join(" ");
              const txt = pasado ? "Pasada" : occ ? "Ocupada" : blk ? "No disp." : "Disponible";
              return (
                <button key={f} className={cls} onClick={() => clic(f)} disabled={pasado} aria-pressed={seleccion.has(f)}
                  aria-label={`${fechaLarga(f)}: ${txt}`}>
                  <b>{Number(f.slice(8))}</b><small>{txt}</small>
                </button>
              );
            })}
          </div>
          <div className="legend">
            <span><i style={{ background: "#fff" }} />Disponible</span>
            <span><i style={{ background: "#eceeed" }} />No disponible</span>
            <span><i style={{ background: "#fde8e4", borderColor: "#f7c9c1" }} />Ocupada por reserva</span>
            <span><i style={{ background: "#fff", borderColor: "var(--accent)", boxShadow: "0 0 0 1px var(--accent)" }} />Seleccionada</span>
          </div>
        </section>

        <aside className="stack">
          <section className="card stack">
            <div className="row-between"><h3>Fechas seleccionadas</h3>{pub && <Badge estado={pub.estado} />}</div>
            {r.length ? (
              <p><b>{r.length === 1 ? fechaLarga(r[0]!) : `${fechaLarga(r[0]!)} – ${fechaLarga(r[r.length - 1]!)}`}</b> · {r.length} {r.length === 1 ? "noche" : "noches"}</p>
            ) : (
              <p className="muted">Haz clic en un día para empezar y en otro para cerrar el rango.</p>
            )}
            <button className="btn btn-primary btn-block" disabled={!r.length || guardando} onClick={() => accion("NO_DISPONIBLE")}><Lock /> Marcar como no disponible</button>
            <button className="btn btn-secondary btn-block" disabled={!r.length || guardando} onClick={() => accion("DISPONIBLE")}><Unlock /> Marcar como disponible</button>
            {error && <Alert tipo="error">{error}</Alert>}
            <p className="subtle" style={{ display: "flex", gap: 6 }}>
              <Info size={15} style={{ flex: "none", marginTop: 2 }} />
              Una reserva ocupa desde la llegada hasta la noche anterior a la salida; el día de salida puede recibir otra llegada.
            </p>
          </section>
          <section className="card stack">
            <h3>Próximas reservas confirmadas</h3>
            {futuras.length ? (
              <ul className="list-plain">
                {futuras.map((x) => (
                  <li key={x.id}><CalendarDays color="var(--err)" />{fechaLarga(x.fecha_llegada)} al {fechaLarga(x.fecha_salida)} · {x.huesped_nombre}</li>
                ))}
              </ul>
            ) : <p className="muted">Sin reservas próximas.</p>}
          </section>
        </aside>
      </div>
    </Page>
  );
}
