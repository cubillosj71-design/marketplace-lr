import { Ban, CheckCircle2, ClipboardList, FileSpreadsheet, FileText, PauseCircle, PowerOff, ShieldAlert, UserRound, Users, Wallet, type LucideIcon } from "lucide-react";
import { useState, type ReactNode } from "react";
import { CIUDADES, ESTADO_TXT, ROL_TXT, TIPOS, cop, type EstadoPub, type Rol } from "../data";
import { Page } from "../layout";
import { useStore, useToast } from "../store";
import { descargarExcel, descargarPDF, type Reporte } from "../exportar";
import { Alert, Badge, Field } from "../ui";

/* Reportes del Administrador (RF-D-ADM-05.2 · HU-25 · BPMN-07).
   Cada descarga queda en el registro de acciones con nombre, fecha y hora (CA-25.2). */

const ESTADO_CUENTA_TXT = { ACTIVA: "Activa", DESACTIVADA: "Desactivada", RESTRINGIDA: "Restringida" } as const;
const VISTA_PUBLICADA = import.meta.env.VITE_ROUTER === "memory";
const fechaCorta = (iso?: string) =>
  iso ? new Date(iso + "T12:00:00").toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric" }).replace(".", "") : "Sin fecha";
const cant = (n: number, uno: string, varios = uno + "s") => `${n} ${n === 1 ? uno : varios}`;
const enPeriodo = (iso: string | undefined, desde: string, hasta: string) => !!iso && iso >= desde && iso <= hasta;

function Stat({ icon: Icon, v, label, bg, fg }: { icon: LucideIcon; v: ReactNode; label: string; bg: string; fg: string }) {
  return (
    <div className="card card-tight stat">
      <span className="ico" style={{ background: bg, color: fg }}><Icon /></span>
      <div><b>{v}</b><span>{label}</span></div>
    </div>
  );
}

/* Periodo + botones de descarga, comunes a los dos reportes */
function useDescarga(nombre: string) {
  const { usuario, hoy, registrarEvento } = useStore();
  const toast = useToast();
  const [desde, setDesde] = useState(`${hoy.slice(0, 4)}-01-01`);
  const [hasta, setHasta] = useState(`${hoy.slice(0, 4)}-12-31`);
  const [ocupado, setOcupado] = useState(false);
  const errorPeriodo = !desde || !hasta ? "Elige la fecha inicial y la final." : desde > hasta ? "La fecha inicial no puede ser posterior a la final." : "";
  const periodo = `${fechaCorta(desde)} al ${fechaCorta(hasta)}`;

  const descargar = async (formato: "PDF" | "Excel", armar: () => Reporte) => {
    if (errorPeriodo) return;
    setOcupado(true);
    try {
      const r = armar();
      if (formato === "PDF") descargarPDF(r); else await descargarExcel(r);
      registrarEvento("Reporte descargado", `${nombre} · ${formato} · ${periodo} · ${r.filas.length} registros`, "EXITO", { entidad: "Reporte" });
      toast(`${nombre} descargado en ${formato}`);
    } catch {
      registrarEvento("Reporte descargado", `${nombre} · ${formato} · no se pudo generar`, "FALLO", { entidad: "Reporte" });
      toast("No se pudo generar el reporte. Intenta de nuevo.", "err");
    } finally {
      setOcupado(false);
    }
  };

  const filtrosPeriodo = (
    <>
      <Field label="Desde"><input className="input" type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)} /></Field>
      <Field label="Hasta"><input className="input" type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} /></Field>
    </>
  );

  const botones = (armar: () => Reporte) => (
    <div className="row" style={{ gap: 10 }}>
      <button className="btn btn-secondary" disabled={!!errorPeriodo || ocupado} onClick={() => descargar("PDF", armar)}>
        <FileText size={18} /> Descargar PDF
      </button>
      <button className="btn btn-primary" disabled={!!errorPeriodo || ocupado} onClick={() => descargar("Excel", armar)}>
        <FileSpreadsheet size={18} /> Descargar Excel
      </button>
    </div>
  );

  return { desde, hasta, periodo, errorPeriodo, filtrosPeriodo, botones, generadoPor: usuario!.nombre };
}

function AvisoDescarga() {
  return (
    <>
      {VISTA_PUBLICADA && (
        <Alert tipo="info">En esta vista publicada el navegador bloquea las descargas. Para obtener el archivo, usa la versión del repositorio o el HTML independiente.</Alert>
      )}
    </>
  );
}

/* ---------------- Módulo Usuarios: Reporte de usuarios ---------------- */
export function ReporteUsuarios() {
  const { usuarios, restriccionVigente } = useStore();
  const d = useDescarga("Reporte de usuarios");
  const fechaHora = (iso: string) => new Date(iso).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
  const [rol, setRol] = useState<"" | Rol>("");
  const [estado, setEstado] = useState<"" | keyof typeof ESTADO_CUENTA_TXT>("");

  const lista = usuarios
    .filter((u) => enPeriodo(u.fechaRegistro, d.desde, d.hasta) && (!rol || u.rol === rol) && (!estado || u.estado === estado))
    .sort((a, b) => b.fechaRegistro.localeCompare(a.fechaRegistro));
  const porRol = (r: Rol) => lista.filter((u) => u.rol === r).length;
  const porEstado = (e: keyof typeof ESTADO_CUENTA_TXT) => lista.filter((u) => u.estado === e).length;

  const armar = (): Reporte => ({
    titulo: "Reporte de usuarios",
    periodo: d.periodo + (rol ? ` · Rol: ${ROL_TXT[rol]}` : "") + (estado ? ` · Estado: ${ESTADO_CUENTA_TXT[estado]}` : ""),
    generadoPor: d.generadoPor,
    resumen: [
      ["Usuarios registrados en el periodo", lista.length],
      ["Huéspedes", porRol("HUESPED")],
      ["Anfitriones", porRol("ANFITRION")],
      ["Administradores", porRol("ADMINISTRADOR")],
      ["Cuentas activas", porEstado("ACTIVA")],
      ["Cuentas desactivadas", porEstado("DESACTIVADA")],
      ["Cuentas restringidas", porEstado("RESTRINGIDA")],
    ],
    columnas: ["Nombre", "Correo", "Rol", "Teléfono", "Estado de la cuenta", "Motivo de restricción", "Fecha de registro", "Autorizó datos (Ley 1581)"],
    filas: lista.map((u) => [u.nombre, u.correo, ROL_TXT[u.rol], u.telefono, ESTADO_CUENTA_TXT[u.estado],
      restriccionVigente(u.id)?.motivo ?? "", fechaCorta(u.fechaRegistro), fechaHora(u.aceptaDatosEn)]),
    archivo: `reporte-usuarios_${d.desde}_${d.hasta}`,
  });

  return (
    <Page req="RF-D-ADM-05.2 · HU-25 · CA-25.2 · CA-25.3">
      <div className="page-head">
        <div><h1>Reporte de usuarios</h1><p>Usuarios registrados en el periodo que elijas, por rol y estado de la cuenta.</p></div>
        {d.botones(armar)}
      </div>
      <AvisoDescarga />
      <section className="card">
        <div className="grid-4 report-filtros">
          {d.filtrosPeriodo}
          <Field label="Rol">
            <select className="select" value={rol} onChange={(e) => setRol(e.target.value as "" | Rol)}>
              <option value="">Todos</option>
              {(Object.keys(ROL_TXT) as Rol[]).map((r) => <option key={r} value={r}>{ROL_TXT[r]}</option>)}
            </select>
          </Field>
          <Field label="Estado de la cuenta">
            <select className="select" value={estado} onChange={(e) => setEstado(e.target.value as typeof estado)}>
              <option value="">Todos</option>
              {(Object.keys(ESTADO_CUENTA_TXT) as (keyof typeof ESTADO_CUENTA_TXT)[]).map((k) => <option key={k} value={k}>{ESTADO_CUENTA_TXT[k]}</option>)}
            </select>
          </Field>
        </div>
        {d.errorPeriodo && <p className="error-text" role="alert" style={{ marginTop: 10 }}>{d.errorPeriodo}</p>}
      </section>

      <div className="grid-4">
        <Stat icon={Users} v={lista.length} label="Usuarios en el periodo" bg="#dff3ef" fg="#0f766e" />
        <Stat icon={UserRound} v={`${porRol("HUESPED")} / ${porRol("ANFITRION")} / ${porRol("ADMINISTRADOR")}`} label="Huésped / Anfitrión / Admin" bg="#e3ecfa" fg="#1e4a8a" />
        <Stat icon={PowerOff} v={porEstado("DESACTIVADA")} label="Cuentas desactivadas" bg="#f1f1ef" fg="#57534e" />
        <Stat icon={ShieldAlert} v={porEstado("RESTRINGIDA")} label="Cuentas restringidas" bg="#fbe1de" fg="#9b1c12" />
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {lista.length === 0 ? <div className="empty-state"><Users /><b>No hay usuarios registrados en ese periodo</b></div> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Usuario</th><th>Rol</th><th>Teléfono</th><th>Estado</th><th>Registro</th><th>Autorizó datos</th></tr></thead>
              <tbody>
                {lista.map((u) => (
                  <tr key={u.id}>
                    <td className="cell-2"><b>{u.nombre}</b><span className="subtle">{u.correo}</span></td>
                    <td>{ROL_TXT[u.rol]}</td>
                    <td>{u.telefono}</td>
                    <td>
                      <span className={`badge ${u.estado === "ACTIVA" ? "badge-ACTIVA" : u.estado === "RESTRINGIDA" ? "badge-BLOQUEADA" : "badge-PAUSADA"}`}>{ESTADO_CUENTA_TXT[u.estado].toUpperCase()}</span>
                      {restriccionVigente(u.id) && <span className="subtle" style={{ display: "block", marginTop: 4, maxWidth: 220 }}>{restriccionVigente(u.id)!.motivo}</span>}
                    </td>
                    <td>{fechaCorta(u.fechaRegistro)}</td>
                    <td className="subtle">{fechaHora(u.aceptaDatosEn)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <p className="subtle">La descarga queda en el registro de acciones con tu nombre, la fecha y la hora.</p>
    </Page>
  );
}

/* ---------------- Módulo Alojamientos: Reporte de publicaciones ---------------- */
export function ReportePublicaciones() {
  const { publicaciones, usuarios, reservas } = useStore();
  const d = useDescarga("Reporte de publicaciones");
  const [estado, setEstado] = useState<"" | EstadoPub>("");
  const [ciudad, setCiudad] = useState("");
  const [tipo, setTipo] = useState("");

  const nombre = (id: number) => usuarios.find((u) => u.id === id)?.nombre ?? "";
  // Los borradores solo los ve su dueño, igual que en "Todas las publicaciones"
  const lista = publicaciones
    .filter((p) => p.estado !== "BORRADOR" && enPeriodo(p.creada ?? p.actualizada, d.desde, d.hasta)
      && (!estado || p.estado === estado) && (!ciudad || p.ciudad === ciudad) && (!tipo || p.tipo === tipo))
    .sort((a, b) => a.id - b.id);

  // Reservas confirmadas o completadas con llegada en el periodo, sobre las publicaciones del reporte
  const reservasDe = (pubId: number) => reservas.filter((r) => r.publicacionId === pubId
    && (r.estado === "CONFIRMADA" || r.estado === "COMPLETADA") && enPeriodo(r.llegada, d.desde, d.hasta));
  // Se usan los valores fijados en cada reserva (total y tarifa de servicio), así un cambio de tarifa no los altera (CA-22.1)
  const filas = lista.map((p) => {
    const rs = reservasDe(p.id);
    return { p, reservas: rs.length, ingreso: rs.reduce((s, r) => s + r.total, 0), plataforma: rs.reduce((s, r) => s + r.tarifaServicio, 0) };
  });
  const n = (e: EstadoPub) => lista.filter((p) => p.estado === e).length;
  const totalReservas = filas.reduce((s, f) => s + f.reservas, 0);
  const totalIngreso = filas.reduce((s, f) => s + f.ingreso, 0);
  const totalPlataforma = filas.reduce((s, f) => s + f.plataforma, 0);

  const demanda = (clave: "ciudad" | "tipo") => {
    const m = new Map<string, { pubs: number; reservas: number }>();
    filas.forEach(({ p, reservas: r }) => {
      const k = (p[clave] as string) || "Sin dato";
      const v = m.get(k) ?? { pubs: 0, reservas: 0 };
      m.set(k, { pubs: v.pubs + 1, reservas: v.reservas + r });
    });
    return [...m.entries()].sort((a, b) => b[1].reservas - a[1].reservas || b[1].pubs - a[1].pubs);
  };
  const porCiudad = demanda("ciudad");
  const porTipo = demanda("tipo");

  const armar = (): Reporte => ({
    titulo: "Reporte de publicaciones",
    periodo: d.periodo + (estado ? ` · Estado: ${ESTADO_TXT[estado]}` : "") + (ciudad ? ` · Ciudad: ${ciudad}` : "") + (tipo ? ` · Tipo: ${tipo}` : ""),
    generadoPor: d.generadoPor,
    resumen: [
      ["Publicaciones en el periodo", lista.length],
      ["En revisión", n("PENDIENTE_REVISION")],
      ["Activas", n("ACTIVA")],
      ["Pausadas", n("PAUSADA")],
      ["Bloqueadas", n("BLOQUEADA")],
      ["Reservas confirmadas o completadas", totalReservas],
      ["Ingresos estimados brutos (COP)", cop(totalIngreso)],
      ["Ingresos de la plataforma, tarifa de servicio (COP)", cop(totalPlataforma)],
      ...porCiudad.map(([k, v]): [string, string] => [`Demanda en ${k}`, `${cant(v.reservas, "reserva")} · ${cant(v.pubs, "publicación", "publicaciones")}`]),
      ...porTipo.map(([k, v]): [string, string] => [`Demanda por tipo: ${k}`, `${cant(v.reservas, "reserva")} · ${cant(v.pubs, "publicación", "publicaciones")}`]),
    ],
    columnas: ["Código", "Título", "Anfitrión", "Ciudad", "Tipo", "Precio por noche", "Estado", "Reservas", "Ingreso bruto", "Ingreso plataforma", "Creada"],
    filas: filas.map(({ p, reservas: r, ingreso, plataforma }) => [p.id, p.titulo, nombre(p.anfitrionId), p.ciudad, p.tipo || "Sin tipo",
      p.precioNoche ?? "Sin precio", ESTADO_TXT[p.estado], r, ingreso, plataforma, fechaCorta(p.creada ?? p.actualizada)]),
    moneda: [5, 8, 9],
    archivo: `reporte-publicaciones_${d.desde}_${d.hasta}`,
  });

  return (
    <Page req="RF-D-ADM-05.2 · RF-D-ADM-05.1 · HU-25 · CA-25.1 · CA-25.2">
      <div className="page-head">
        <div><h1>Reporte de publicaciones</h1><p>Publicaciones creadas en el periodo, sus reservas, ingresos estimados y demanda por ciudad y tipo.</p></div>
        {d.botones(armar)}
      </div>
      <AvisoDescarga />
      <section className="card">
        <div className="report-filtros report-filtros-5">
          {d.filtrosPeriodo}
          <Field label="Estado">
            <select className="select" value={estado} onChange={(e) => setEstado(e.target.value as "" | EstadoPub)}>
              <option value="">Todos</option>
              {(["PENDIENTE_REVISION", "ACTIVA", "PAUSADA", "BLOQUEADA"] as EstadoPub[]).map((e) => <option key={e} value={e}>{ESTADO_TXT[e]}</option>)}
            </select>
          </Field>
          <Field label="Ciudad">
            <select className="select" value={ciudad} onChange={(e) => setCiudad(e.target.value)}>
              <option value="">Todas</option>
              {CIUDADES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Tipo">
            <select className="select" value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="">Todos</option>
              {TIPOS.map((t) => <option key={t}>{t}</option>)}
            </select>
          </Field>
        </div>
        {d.errorPeriodo && <p className="error-text" role="alert" style={{ marginTop: 10 }}>{d.errorPeriodo}</p>}
      </section>

      <div className="grid-4">
        <Stat icon={ClipboardList} v={lista.length} label="Publicaciones en el periodo" bg="#dff3ef" fg="#0f766e" />
        <Stat icon={CheckCircle2} v={n("ACTIVA")} label="Activas" bg="#dcf3e4" fg="#166534" />
        <Stat icon={PauseCircle} v={`${n("PAUSADA")} / ${n("BLOQUEADA")}`} label="Pausadas / Bloqueadas" bg="#e3ecfa" fg="#1e4a8a" />
        <Stat icon={Wallet} v={cop(totalIngreso)} label={`Ingreso bruto · plataforma ${cop(totalPlataforma)}`} bg="#fdf0c8" fg="#8a4b05" />
      </div>

      <div className="grid-2">
        {([["Demanda por ciudad", porCiudad], ["Demanda por tipo de alojamiento", porTipo]] as const).map(([t, filasD]) => (
          <section key={t} className="card" style={{ padding: 0, overflow: "hidden" }}>
            <h3 style={{ padding: "16px 18px 6px" }}>{t}</h3>
            <table className="table">
              <thead><tr><th>{t.endsWith("ciudad") ? "Ciudad" : "Tipo"}</th><th style={{ textAlign: "right" }}>Publicaciones</th><th style={{ textAlign: "right" }}>Reservas</th></tr></thead>
              <tbody>
                {filasD.length === 0 ? <tr><td colSpan={3} className="subtle">Sin datos en el periodo</td></tr> :
                  filasD.map(([k, v]) => <tr key={k}><td>{k}</td><td style={{ textAlign: "right" }}>{v.pubs}</td><td style={{ textAlign: "right" }}>{v.reservas}</td></tr>)}
              </tbody>
            </table>
          </section>
        ))}
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {lista.length === 0 ? <div className="empty-state"><Ban /><b>No hay publicaciones creadas en ese periodo</b></div> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Publicación</th><th>Anfitrión</th><th>Tipo</th><th>Precio/noche</th><th>Estado</th><th style={{ textAlign: "right" }}>Reservas</th><th style={{ textAlign: "right" }}>Ingreso bruto</th><th style={{ textAlign: "right" }}>Plataforma</th></tr></thead>
              <tbody>
                {filas.map(({ p, reservas: r, ingreso, plataforma }) => (
                  <tr key={p.id}>
                    <td className="cell-2"><b>{p.titulo}</b><span className="subtle">{p.ciudad} · #{p.id} · creada {fechaCorta(p.creada ?? p.actualizada)}</span></td>
                    <td>{nombre(p.anfitrionId)}</td>
                    <td>{p.tipo || "Sin tipo"}</td>
                    <td>{p.precioNoche ? cop(p.precioNoche) : "Sin precio"}</td>
                    <td><Badge estado={p.estado} /></td>
                    <td style={{ textAlign: "right" }}>{r}</td>
                    <td style={{ textAlign: "right" }}>{cop(ingreso)}</td>
                    <td style={{ textAlign: "right" }}>{cop(plataforma)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <p className="subtle">Ingreso bruto = total de cada reserva (precio base − descuento + limpieza + tarifa de servicio). Ingreso de la plataforma = tarifa de servicio fijada al confirmar la reserva. Cuenta las reservas confirmadas o completadas con llegada en el periodo. La descarga queda en el registro de acciones.</p>
    </Page>
  );
}
