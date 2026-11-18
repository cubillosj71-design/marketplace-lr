import { CalendarDays, ChevronLeft, ChevronRight, Info, Lock, Unlock } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fechaLarga, isoDia } from "../data";
import { Page } from "../layout";
import { useStore, useToast } from "../store";
import { Alert, Badge } from "../ui";

const DOW = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

/* =========================================================
   CU-ALO-06 Bloquear o liberar fechas del calendario
   ========================================================= */
export function Calendario() {
  const { usuario, publicaciones, nochesOcupadas, bloquearFechas, liberarFechas, reservasConfirmadas, hoy, usuarios } = useStore();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const mias = publicaciones.filter((p) => p.anfitrionId === usuario!.id && p.estado !== "BLOQUEADA");
  const pubId = Number(params.get("pub")) || mias[0]?.id;
  const pub = mias.find((p) => p.id === pubId);

  const base = new Date(hoy + "T12:00:00");
  const [mes, setMes] = useState({ y: base.getFullYear(), m: base.getMonth() });
  const [sel, setSel] = useState<{ a: string; b?: string } | null>(null);
  const [error, setError] = useState("");

  const ocupadas = useMemo(() => (pub ? nochesOcupadas(pub.id) : new Set<string>()), [pub, nochesOcupadas]);
  const bloqueadas = new Set(pub?.bloqueos ?? []);

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
    const out: string[] = [];
    const d = new Date(a + "T12:00:00");
    while (isoDia(d) <= b!) { out.push(isoDia(d)); d.setDate(d.getDate() + 1); }
    return out;
  };
  const seleccion = new Set(rango());

  const clic = (f: string) => {
    setError("");
    if (f < hoy) return;
    if (!sel || sel.b) setSel({ a: f });
    else setSel({ a: sel.a, b: f });
  };

  const accion = (tipo: "bloquear" | "liberar") => {
    if (!pub || !sel) return;
    const fechas = rango();
    const r = tipo === "bloquear" ? bloquearFechas(pub.id, fechas) : liberarFechas(pub.id, fechas);
    if (!r.ok) {
      const choque = fechas.filter((f) => ocupadas.has(f));
      setError(`No se puede bloquear ${choque.length > 1 ? `del ${fechaLarga(choque[0]!)} al ${fechaLarga(choque[choque.length - 1]!)}` : `el ${fechaLarga(choque[0]!)}`}: ${choque.length > 1 ? "tienen" : "tiene"} una reserva CONFIRMADA.`);
      return;
    }
    toast(tipo === "bloquear" ? "Fechas marcadas como no disponibles" : "Fechas disponibles de nuevo");
    setSel(null);
  };

  const mover = (d: number) => setMes(({ y, m }) => { const n = new Date(y, m + d, 1); return { y: n.getFullYear(), m: n.getMonth() }; });
  const t0 = new Date(mes.y, mes.m, 1).toLocaleDateString("es-CO", { month: "long", year: "numeric" });
  const titulo = t0[0]!.toUpperCase() + t0.slice(1);
  const r = rango();
  const futuras = pub ? reservasConfirmadas(pub.id).filter((x) => x.salida >= hoy) : [];

  if (!mias.length)
    return <Page req="RF-D-ALO-02.2"><div className="card empty-state"><CalendarDays /><b>Aún no tienes publicaciones con calendario</b><Link className="btn btn-primary" to="/publicaciones/nueva">Crear publicación</Link></div></Page>;

  return (
    <Page req="RF-D-ALO-02.2 · CU-ALO-06 · HU-09">
      <div className="page-head">
        <div><h1>Calendario de disponibilidad</h1><p>Marca las fechas en que recibes y en las que no recibirás huéspedes.</p></div>
        <div className="field" style={{ minWidth: 300 }}>
          <span className="label">Alojamiento</span>
          <select className="select" value={pub?.id} onChange={(e) => { setParams({ pub: e.target.value }); setSel(null); setError(""); }}>
            {mias.map((p) => <option key={p.id} value={p.id}>{p.titulo}</option>)}
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
            <button className="btn btn-primary btn-block" disabled={!r.length} onClick={() => accion("bloquear")}><Lock /> Marcar como no disponible</button>
            <button className="btn btn-secondary btn-block" disabled={!r.length} onClick={() => accion("liberar")}><Unlock /> Marcar como disponible</button>
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
                  <li key={x.id}><CalendarDays color="var(--err)" />{fechaLarga(x.llegada)} al {fechaLarga(x.salida)} · {usuarios.find((u) => u.id === x.huespedId)?.nombre}</li>
                ))}
              </ul>
            ) : <p className="muted">Sin reservas próximas.</p>}
          </section>
        </aside>
      </div>
    </Page>
  );
}
