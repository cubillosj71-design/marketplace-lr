import { Download, FileSpreadsheet, FileText, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { adminApi, catalogoApi, leerError, type ItemCatalogo } from "../api";
import { ROL_TXT, type Rol } from "../data";
import { Page } from "../layout";
import { useToast } from "../store";
import { Alert, Field } from "../ui";
import { SelectorPeriodo, periodosRapidos } from "./admin";

/* HU-25 · RF-D-ADM-05.2: los archivos los genera el servidor con ReportLab y openpyxl (ADR-009), con las mismas
   consultas del tablero. Cada descarga queda en el registro de acciones antes de entregarse (CA-25.2). */

const REPORTES = [
  { tipo: "usuarios", nombre: "Usuarios", descripcion: "Registrados en el periodo, por rol y estado de la cuenta." },
  { tipo: "publicaciones", nombre: "Publicaciones", descripcion: "Creadas en el periodo, con sus reservas e ingresos." },
  { tipo: "reservas", nombre: "Reservas", descripcion: "Creadas en el periodo, con su estado, devolución, monto bruto e ingreso." },
  { tipo: "ingresos", nombre: "Ingresos estimados", descripcion: "Monto bruto e ingreso de la plataforma por mes." },
  { tipo: "demanda", nombre: "Demanda", descripcion: "Reservas y monto bruto por ciudad y por tipo de alojamiento." },
] as const;
type TipoReporte = (typeof REPORTES)[number]["tipo"];

export function Reportes() {
  const toast = useToast();
  const [busqueda] = useSearchParams();
  const inicial = periodosRapidos()[0]!;
  const [tipo, setTipo] = useState<TipoReporte>((REPORTES.find((r) => r.tipo === busqueda.get("tipo"))?.tipo) ?? "reservas");
  const [p, setP] = useState({ desde: inicial.desde, hasta: inicial.hasta });
  const [formato, setFormato] = useState<"pdf" | "xlsx">("pdf");
  const [filtros, setFiltros] = useState({ rol: "", estado_cuenta: "", estado: "", ciudad: "", tipo_alojamiento: "" });
  const [cat, setCat] = useState<{ ciudades: ItemCatalogo[]; tipos: ItemCatalogo[] }>({ ciudades: [], tipos: [] });
  const [error, setError] = useState("");
  const [descargando, setDescargando] = useState(false);

  useEffect(() => {
    Promise.all([catalogoApi.ciudades(), catalogoApi.tipos()]).then(([c, t]) => setCat({ ciudades: c.data, tipos: t.data })).catch(() => {});
  }, []);

  const descargar = async () => {
    setError("");
    setDescargando(true);
    const extra = tipo === "usuarios" ? { rol: filtros.rol || undefined, estado: filtros.estado_cuenta || undefined }
      : tipo === "publicaciones" ? { estado: filtros.estado || undefined, ciudad: filtros.ciudad || undefined, tipo: filtros.tipo_alojamiento || undefined }
        : {};
    try {
      const { blob, nombre } = await adminApi.reporte(tipo, { formato, desde: p.desde, hasta: p.hasta, ...extra });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = nombre;
      document.body.appendChild(a); a.click(); a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast(`Descargado: ${nombre}`);
    } catch (e) {
      setError(leerError(e).error);  // p. ej. "El periodo máximo es de 12 meses."
    } finally {
      setDescargando(false);
    }
  };
  const set = (k: keyof typeof filtros, v: string) => setFiltros({ ...filtros, [k]: v });

  return (
    <Page req="RF-D-ADM-05.2 · HU-25 · ADR-009 · periodo máximo de 12 meses">
      <div className="page-head"><div><h1>Reportes</h1><p>Elige el reporte, el periodo y el formato. El archivo lo genera el servidor con las mismas cifras del tablero.</p></div></div>
      <div className="detail-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1.3fr)", gap: 20, alignItems: "start" }}>
        <section className="card stack">
          <h3>Reporte</h3>
          <div className="stack" style={{ gap: 8 }}>
            {REPORTES.map((r) => (
              <label key={r.tipo} className="card card-tight row" style={{ gap: 10, cursor: "pointer", borderColor: tipo === r.tipo ? "var(--accent)" : undefined }}>
                <input type="radio" name="reporte" checked={tipo === r.tipo} onChange={() => setTipo(r.tipo)} />
                <span className="stack" style={{ gap: 2 }}><b>{r.nombre}</b><span className="subtle">{r.descripcion}</span></span>
              </label>
            ))}
          </div>
        </section>
        <section className="card stack">
          <h3>Periodo</h3>
          <SelectorPeriodo desde={p.desde} hasta={p.hasta} onCambio={(desde, hasta) => setP({ desde, hasta })} />
          {tipo === "usuarios" && (
            <div className="grid-2">
              <Field label="Rol"><select className="select" value={filtros.rol} onChange={(e) => set("rol", e.target.value)}>
                <option value="">Todos</option>{(Object.keys(ROL_TXT) as Rol[]).map((r) => <option key={r} value={r}>{ROL_TXT[r]}</option>)}
              </select></Field>
              <Field label="Estado de la cuenta"><select className="select" value={filtros.estado_cuenta} onChange={(e) => set("estado_cuenta", e.target.value)}>
                <option value="">Todos</option>{["ACTIVA", "DESACTIVADA", "RESTRINGIDA"].map((e) => <option key={e} value={e}>{e}</option>)}
              </select></Field>
            </div>
          )}
          {tipo === "publicaciones" && (
            <div className="grid-2">
              <Field label="Estado"><select className="select" value={filtros.estado} onChange={(e) => set("estado", e.target.value)}>
                <option value="">Todos</option>{["PENDIENTE_REVISION", "ACTIVA", "PAUSADA", "BLOQUEADA"].map((e) => <option key={e} value={e}>{e.replace("_", " ")}</option>)}
              </select></Field>
              <Field label="Ciudad"><select className="select" value={filtros.ciudad} onChange={(e) => set("ciudad", e.target.value)}>
                <option value="">Todas</option>{cat.ciudades.map((c) => <option key={c.id} value={c.nombre}>{c.nombre}</option>)}
              </select></Field>
              <Field label="Tipo"><select className="select" value={filtros.tipo_alojamiento} onChange={(e) => set("tipo_alojamiento", e.target.value)}>
                <option value="">Todos</option>{cat.tipos.map((t) => <option key={t.id} value={t.nombre}>{t.nombre}</option>)}
              </select></Field>
            </div>
          )}
          <h3>Formato</h3>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <button className={`btn ${formato === "pdf" ? "btn-primary" : "btn-secondary"}`} onClick={() => setFormato("pdf")}><FileText /> PDF</button>
            <button className={`btn ${formato === "xlsx" ? "btn-primary" : "btn-secondary"}`} onClick={() => setFormato("xlsx")}><FileSpreadsheet /> Excel</button>
          </div>
          {error && <Alert tipo="error">{error}</Alert>}
          <button className="btn btn-primary btn-block" disabled={descargando} onClick={descargar}>
            <Download /> {descargando ? "Generando…" : "Descargar"}
          </button>
          <p className="subtle row" style={{ gap: 6 }}><ShieldCheck size={15} /> La descarga queda en el registro de acciones con tu nombre, el reporte, el formato y el periodo.</p>
        </section>
      </div>
    </Page>
  );
}
