import {
  BarChart3, Bell, CalendarCheck, CalendarDays, CheckCircle2, ClipboardList, FileBarChart2, Percent, FileSpreadsheet, ChevronRight, ClipboardCheck, Compass, History, Home, KeyRound, LayoutList, LogOut,
  PlusCircle, ShieldCheck, Star, UserRound,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { adminApi, api, notificacionesApi } from "./api";
import { ROL_TXT, iniciales } from "./data";
import { LimiteDeError } from "./LimiteDeError";
import { useStore } from "./store";
import { ImageTile, Logo } from "./ui";

/* ---------- pantallas de acceso: panel de marca + formulario ---------- */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="auth">
      <aside className="auth-hero">
        <span className="blob b1" /><span className="blob b2" />
        <Link to="/" style={{ color: "inherit", position: "relative", zIndex: 1 }}><Logo /></Link>
        <div style={{ position: "relative", zIndex: 1 }}>
          <h1>Tu alojamiento ideal, a un clic.</h1>
          <p className="lead">Anfitriones y huéspedes conectados en un solo lugar, con disponibilidad al día y reglas claras.</p>
          <div className="hero-card" aria-hidden>
            <ImageTile img={{ id: "h", nombre: "", color: "linear-gradient(135deg,#2d7f74,#8fd3c4)", src: "/alojamientos/lago-muelle.jpg" }} />
            <div className="meta">
              <b>Cabaña del Lago</b>
              <div className="row" style={{ justifyContent: "space-between", marginTop: 4 }}>
                <span className="subtle">Guatapé · hasta 5 huéspedes</span>
                <span style={{ display: "inline-flex", gap: 4, alignItems: "center", fontSize: 13, fontWeight: 700 }}>
                  <Star size={14} fill="#f59e0b" color="#f59e0b" /> 4,9
                </span>
              </div>
            </div>
            <div className="hero-pill"><i><CheckCircle2 /></i>Reserva confirmada</div>
          </div>
        </div>
        <p className="hero-foot">Marketplace de alojamientos · Inversiones LR</p>
      </aside>
      <main className="auth-main"><div className="auth-box">{children}</div></main>
    </div>
  );
}

/* ---------- navegación por permisos (RF-D-USU-02.1) ---------- */
/** Cada opción declara el permiso que necesita, con el mismo nombre que en el backend (apps/comun/rbac.py).
 *  Sin permiso (null) basta con tener sesión. */
type Item = { to: string; label: string; icon: typeof Home; permiso: string | null; count?: number; end?: boolean };

const ALOJAMIENTOS: Item[] = [
  { to: "/explorar", label: "Explorar alojamientos", icon: Compass, permiso: "busqueda.ver" },
  { to: "/reservas", label: "Mis reservas", icon: CalendarCheck, permiso: "reservas.ver_propias" },
  { to: "/publicaciones", label: "Mis publicaciones", icon: LayoutList, permiso: "publicaciones.gestionar_propias", end: true },
  { to: "/publicaciones/nueva", label: "Nueva publicación", icon: PlusCircle, permiso: "publicaciones.gestionar_propias" },
  { to: "/calendario", label: "Calendario", icon: CalendarDays, permiso: "calendario.gestionar" },
  { to: "/reservas-alojamientos", label: "Reservas de mis alojamientos", icon: CalendarCheck, permiso: "reservas.ver_de_mis_alojamientos" },
  { to: "/admin/tablero", label: "Tablero", icon: BarChart3, permiso: "tablero.ver" },
  { to: "/admin/publicaciones", label: "Todas las publicaciones", icon: LayoutList, permiso: "publicaciones.moderar" },
  { to: "/admin/revision", label: "Pendientes de revisión", icon: ClipboardCheck, permiso: "publicaciones.moderar" },
  { to: "/admin/reservas", label: "Reservas en revisión", icon: ClipboardList, permiso: "reservas.resolver" },
  { to: "/admin/tarifa", label: "Tarifa de servicio", icon: Percent, permiso: "tarifa.configurar" },
  { to: "/admin/registro", label: "Registro de acciones", icon: History, permiso: "auditoria.consultar" },
  { to: "/admin/reportes", label: "Reportes", icon: FileSpreadsheet, permiso: "reportes.descargar" },
];
const USUARIOS: Item[] = [
  { to: "/perfil", label: "Mi perfil", icon: UserRound, permiso: "perfil.gestionar" },
  { to: "/perfil/contrasena", label: "Cambiar contraseña", icon: KeyRound, permiso: "perfil.gestionar" },
  { to: "/roles", label: "Roles y permisos", icon: ShieldCheck, permiso: "usuarios.ver" },
  { to: "/admin/usuarios", label: "Usuarios", icon: FileBarChart2, permiso: "usuarios.ver" },
];

/** Número de publicaciones pendientes de revisión, desde la API (solo con publicaciones.moderar). */
function usePendientes(activo: boolean) {
  const loc = useLocation();
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!activo) return;
    let vivo = true;
    adminApi.publicaciones("PENDIENTE_REVISION").then((l) => { if (vivo) setN(l.length); }).catch(() => {});
    return () => { vivo = false; };
  }, [activo, loc.pathname]);
  return n;
}

function useNav(): { titulo: string; items: Item[] }[] {
  const { usuario, tiene } = useStore();
  const pendientes = usePendientes(tiene("publicaciones.moderar"));
  if (!usuario) return [];
  const permitidos = (items: Item[]) => items
    .filter((it) => it.permiso === null || tiene(it.permiso))
    .map((it) => (it.to === "/admin/revision" ? { ...it, count: pendientes } : it));
  return [
    { titulo: "Alojamientos", items: permitidos(ALOJAMIENTOS) },
    { titulo: "Usuarios", items: permitidos(USUARIOS) },
  ].filter((g) => g.items.length);
}

/** Primera pantalla del menú que el usuario puede abrir: ahí llega al entrar. */
export function usePrimeraPantalla(): string {
  const { tiene } = useStore();
  return [...ALOJAMIENTOS, ...USUARIOS].find((it) => it.permiso !== null && tiene(it.permiso))?.to ?? "/perfil";
}

const MIGAS: [RegExp, string][] = [
  [/^\/perfil\/contrasena/, "Cambiar contraseña"],
  [/^\/perfil/, "Mi perfil"],
  [/^\/roles/, "Roles y permisos"],
  [/^\/explorar\/\d+/, "Detalle del alojamiento"],
  [/^\/explorar/, "Explorar alojamientos"],
  [/^\/publicaciones\/nueva/, "Nueva publicación"],
  [/^\/publicaciones\/\d+\/editar/, "Editar publicación"],
  [/^\/publicaciones\/\d+/, "Detalle de publicación"],
  [/^\/publicaciones/, "Mis publicaciones"],
  [/^\/calendario/, "Calendario de disponibilidad"],
  [/^\/admin\/revision\/\d+/, "Revisar publicación"],
  [/^\/admin\/publicaciones\/\d+/, "Detalle de publicación"],
  [/^\/admin\/tablero/, "Tablero"],
  [/^\/admin\/usuarios/, "Usuarios"],
  [/^\/admin\/reportes/, "Reportes"],
  [/^\/admin\/revision/, "Pendientes de revisión"],
  [/^\/admin\/publicaciones/, "Todas las publicaciones"],
  [/^\/admin\/registro/, "Registro de acciones"],
  [/^\/admin\/reservas/, "Reservas en revisión"],
  [/^\/reservas-alojamientos/, "Reservas de mis alojamientos"],
  [/^\/reservas/, "Mis reservas"],
  [/^\/cotizacion/, "Cotización"],
  [/^\/avisos/, "Avisos"],
  [/^\/admin\/tarifa/, "Tarifa de servicio"],
  [/^\/admin\/reportes\/usuarios/, "Reporte de usuarios"],
  [/^\/admin\/reportes\/publicaciones/, "Reporte de publicaciones"],
];

/** HU-16: campana con el número de avisos no leídos. Se actualiza al navegar, cada minuto y cuando la bandeja cambia. */
function Campana() {
  const loc = useLocation();
  const [noLeidas, setNoLeidas] = useState(0);
  useEffect(() => {
    let activo = true;
    const cargar = () => notificacionesApi.bandeja().then((r) => { if (activo) setNoLeidas(r.data.no_leidas); }).catch(() => {});
    cargar();
    const intervalo = window.setInterval(cargar, 60000);
    window.addEventListener("avisos-cambiaron", cargar);
    return () => { activo = false; window.clearInterval(intervalo); window.removeEventListener("avisos-cambiaron", cargar); };
  }, [loc.pathname]);
  return (
    <Link to="/avisos" className="btn btn-ghost btn-sm" aria-label={`Avisos: ${noLeidas} sin leer`} style={{ position: "relative" }}>
      <Bell />
      {noLeidas > 0 && (
        <span className="count" style={{ position: "absolute", top: -2, right: -2, minWidth: 18, height: 18, fontSize: 11, display: "grid", placeItems: "center",
          borderRadius: 999, background: "var(--err)", color: "#fff", padding: "0 4px" }}>{noLeidas > 99 ? "99+" : noLeidas}</span>
      )}
    </Link>
  );
}

export function AppLayout() {
  const { usuario, cerrarSesion } = useStore();
  const nav = useNav();
  const loc = useLocation();
  const go = useNavigate();
  // Sin sesión (o si se perdió por un 401 sin renovación) se va a "Ingresar"; el aviso lo muestra esa pantalla.
  if (!usuario) return <Navigate to="/ingresar" replace state={{ volver: loc.pathname + loc.search }} />;
  const miga = MIGAS.find(([r]) => r.test(loc.pathname))?.[1] ?? "";
  const seccion = loc.pathname.startsWith("/perfil") || loc.pathname.startsWith("/roles") || loc.pathname.startsWith("/admin/usuarios") ? "Usuarios"
    : loc.pathname.startsWith("/admin") ? "Administración" : "Alojamientos";

  const links = nav.flatMap((g) => g.items);
  const renderLink = (it: Item) => (
    <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
      <it.icon />{it.label}{!!it.count && <span className="count">{it.count}</span>}
    </NavLink>
  );

  return (
    <div className="app">
      <aside className="sidebar">
        <Logo />
        {nav.map((g) => (
          <nav key={g.titulo} className="nav-group" aria-label={g.titulo}>
            <span className="nav-title">{g.titulo}</span>
            {g.items.map(renderLink)}
          </nav>
        ))}
      </aside>
      <div className="main">
        <header className="topbar">
          <span className="topbar-logo"><Logo /></span>
          <div className="crumbs"><span>{seccion}</span><ChevronRight /><b>{miga}</b></div>
          <div className="user-chip">
            <Campana />
            <span className="avatar" aria-hidden>{iniciales(usuario.nombre_completo)}</span>
            <div className="who"><b>{usuario.nombre_completo}</b><span>{ROL_TXT[usuario.rol]}</span></div>
            <button className="btn btn-ghost btn-sm" onClick={async () => { await cerrarSesion(); go("/ingresar"); }}>
              <LogOut /> <span>Salir</span>
            </button>
          </div>
        </header>
        <nav className="mobile-nav" aria-label="Navegación">{links.map(renderLink)}</nav>
        <LimiteDeError reinicio={loc.pathname}><Outlet /></LimiteDeError>
      </div>
    </div>
  );
}

/** Contenido de una página con su etiqueta de trazabilidad al pie. */
export function Page({ req, children }: { req: string; children: ReactNode }) {
  return (
    <>
      <div className="content">{children}</div>
      <div className="req-tag">{req}</div>
    </>
  );
}

/** Protección por permiso (RF-D-USU-02.1). Sin sesión lleva a "Ingresar"; sin el permiso muestra el aviso.
 *  Con varios permisos basta tener uno, igual que RequierePermiso en el backend. */
export function ConPermiso({ permiso, api: rutaApi, children }: { permiso: string | string[]; api?: string; children: ReactNode }) {
  const { usuario, tiene } = useStore();
  const loc = useLocation();
  if (!usuario) return <Navigate to="/ingresar" replace state={{ volver: loc.pathname + loc.search }} />;
  if (!tiene(...(Array.isArray(permiso) ? permiso : [permiso]))) return <Denegado api={rutaApi} />;
  return <>{children}</>;
}

/** CA-05.2: el frontend no registra nada por su cuenta. Hace UN GET a la ruta de la API de la pantalla; el backend
 *  responde 403 y deja el intento en la auditoría con la ruta y el permiso que faltó. La respuesta no se usa. */
function useRegistrarIntento(rutaApi?: string) {
  const params = useParams();
  const hecho = useRef<string | null>(null);
  const ruta = rutaApi?.replace(/:(\w+)/g, (_, k: string) => encodeURIComponent(params[k] ?? "0"));
  useEffect(() => {
    if (!ruta || hecho.current === ruta) return;  // una sola petición por pantalla (también en StrictMode)
    hecho.current = ruta;
    api.get(ruta).catch(() => { /* 403 esperado: no se muestra nada de la respuesta */ });
  }, [ruta]);
}

/** Pantalla de acceso negado. */
export function Denegado({ titulo = "No tienes permiso para ver esta página", texto, api: rutaApi }: {
  titulo?: string; texto?: string; api?: string;
}) {
  useRegistrarIntento(rutaApi);
  return (
    <Page req="RF-D-USU-02.1 · HU-05">
      <div className="card empty-state">
        <ShieldCheck />
        <h2>{titulo}</h2>
        {texto && <p>{texto}</p>}
        <Link className="btn btn-secondary" to="/inicio">Volver al inicio</Link>
      </div>
    </Page>
  );
}
