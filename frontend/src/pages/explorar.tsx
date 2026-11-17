import { ArrowLeft, Check, Lock, MapPin, Search, Users } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { CIUDADES, POLITICA_MODERADA, TIPOS, cop } from "../data";
import { Page } from "../layout";
import { useStore } from "../store";
import { Alert, ImageTile, Logo } from "../ui";

/** Barra superior para el Visitante (sin sesión). */
function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header className="public-top">
        <Link to="/explorar-publico" style={{ color: "var(--text)" }}><Logo /></Link>
        <div className="row right">
          <Link className="btn btn-ghost" to="/ingresar">Iniciar sesión</Link>
          <Link className="btn btn-primary" to="/registro">Registrarse</Link>
        </div>
      </header>
      {children}
    </div>
  );
}

/* Búsqueda básica: la búsqueda completa (fechas, filtros de precio) es del módulo RES. */
function Explorador({ base }: { base: string }) {
  const { publicaciones, visibleEnBusquedas } = useStore();
  const [ciudad, setCiudad] = useState("");
  const [tipo, setTipo] = useState("");
  const [hues, setHues] = useState(1);
  const lista = publicaciones.filter((p) =>
    visibleEnBusquedas(p) && (!ciudad || p.ciudad === ciudad) && (!tipo || p.tipo === tipo) && (p.capacidad ?? 0) >= hues);

  return (
    <Page req="RF-D-USU-02.1 · solo se muestran publicaciones ACTIVAS · la búsqueda completa es del módulo RES">
      <section className="public-hero">
        <div><h1>Explora alojamientos</h1><p>Solo aparecen publicaciones activas de anfitriones con cuenta activa.</p></div>
        <div className="search-bar">
          <select className="select" value={ciudad} onChange={(e) => setCiudad(e.target.value)} aria-label="Ciudad">
            <option value="">Todas las ciudades</option>{CIUDADES.map((c) => <option key={c}>{c}</option>)}
          </select>
          <select className="select" value={tipo} onChange={(e) => setTipo(e.target.value)} aria-label="Tipo">
            <option value="">Tipo: todos</option>{TIPOS.map((t) => <option key={t}>{t}</option>)}
          </select>
          <select className="select" value={hues} onChange={(e) => setHues(Number(e.target.value))} aria-label="Huéspedes">
            {[1, 2, 3, 4, 5, 6, 8].map((n) => <option key={n} value={n}>{n} {n === 1 ? "huésped" : "huéspedes"}</option>)}
          </select>
          <button className="btn btn-primary"><Search /> Buscar</button>
        </div>
      </section>
      <p className="muted">{lista.length} {lista.length === 1 ? "alojamiento" : "alojamientos"}</p>
      <div className="cards">
        {lista.map((p) => (
          <Link key={p.id} to={`${base}/${p.id}`} className="listing" style={{ color: "inherit", textDecoration: "none" }}>
            <div style={{ position: "relative" }}>
              <ImageTile img={p.imagenes[0]} />
              <span className="type">{p.tipo}</span>
            </div>
            <div className="body">
              <h3>{p.titulo}</h3>
              <span className="subtle" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><MapPin size={14} />{p.ciudad} · hasta {p.capacidad} huéspedes</span>
              <div className="price"><b>{cop(p.precioNoche)}</b> <span>/ noche</span></div>
            </div>
          </Link>
        ))}
      </div>
    </Page>
  );
}

function Detalle({ base, visitante }: { base: string; visitante: boolean }) {
  const { id } = useParams();
  const { publicaciones, visibleEnBusquedas, usuarios } = useStore();
  const p = publicaciones.find((x) => x.id === Number(id));
  if (!p || !visibleEnBusquedas(p))
    return <Page req="RF-D-RES-01.2"><div className="card empty-state"><Lock /><h2>Este alojamiento no está disponible</h2><Link className="btn btn-secondary" to={base}>Volver</Link></div></Page>;
  const anf = usuarios.find((u) => u.id === p.anfitrionId);
  return (
    <Page req="Detalle del alojamiento · la cotización y la reserva son del módulo RES">
      <Link to={base} className="back"><ArrowLeft /> Volver a explorar</Link>
      <div className="page-head"><div><h1>{p.titulo}</h1><p style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><MapPin size={15} />{p.ubicacion}, {p.ciudad}</p></div></div>
      <div style={{ display: "grid", gridTemplateColumns: p.imagenes.length <= 1 ? "1fr" : p.imagenes.length <= 3 ? "2fr 1fr" : "2fr 1fr 1fr", gridTemplateRows: p.imagenes.length <= 2 ? "310px" : "150px 150px", gap: 10 }} className="gallery">
        <ImageTile img={p.imagenes[0]} style={{ gridRow: "span 2" }} />
        {p.imagenes.slice(1, 5).map((im) => <ImageTile key={im.id} img={im} />)}
      </div>
      <div className="detail-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,1.6fr) minmax(0,1fr)", gap: 20, alignItems: "start" }}>
        <div className="stack">
          <section className="card stack">
            <div className="row" style={{ gap: 18 }}>
              <span className="row" style={{ gap: 6 }}><Users size={18} /> Hasta {p.capacidad} huéspedes</span>
              <span className="muted">{p.tipo}</span>
              <span className="muted">Anfitrión: {anf?.nombre}</span>
            </div>
            <p>{p.descripcion}</p>
            <div className="chips">{p.servicios.map((s) => <span key={s} className="svc"><Check />{s}</span>)}</div>
          </section>
          <section className="card stack">
            <h3>Reglas del alojamiento</h3><p>{p.reglas}</p>
            <h3>Política de cancelación: Moderada</h3>
            <ul className="list-plain">{POLITICA_MODERADA.map((t) => <li key={t.tramo}><b style={{ width: 52 }}>{t.devolucion}</b>{t.tramo}</li>)}</ul>
          </section>
        </div>
        <aside className="card stack">
          <div className="price"><b style={{ fontSize: 24 }}>{cop(p.precioNoche)}</b> <span>/ noche</span></div>
          <p className="subtle">Limpieza {cop(p.limpieza)}{p.descuentoPct ? ` · ${p.descuentoPct} % de descuento desde ${p.descuentoNoches} noches` : ""}</p>
          {p.adicionales.length > 0 && <ul className="list-plain">{p.adicionales.map((a) => <li key={a.nombre} style={{ justifyContent: "space-between", display: "flex" }}><span>{a.nombre}</span><span>{cop(a.precio)}</span></li>)}</ul>}
          {visitante ? (
            <>
              <Alert tipo="info">Para cotizar o reservar necesitas iniciar sesión como huésped.</Alert>
              <Link className="btn btn-primary btn-block" to="/ingresar">Iniciar sesión</Link>
            </>
          ) : (
            <>
              <button className="btn btn-primary btn-block" disabled>Cotizar estancia</button>
              <p className="subtle">La cotización y la reserva llegan con el módulo de Reservas (RES).</p>
            </>
          )}
        </aside>
      </div>
    </Page>
  );
}

export const Explorar = () => <Explorador base="/explorar" />;
export const ExplorarDetalle = () => <Detalle base="/explorar" visitante={false} />;
export const ExplorarPublico = () => <PublicShell><Explorador base="/explorar-publico" /></PublicShell>;
export const ExplorarPublicoDetalle = () => <PublicShell><Detalle base="/explorar-publico" visitante /></PublicShell>;
