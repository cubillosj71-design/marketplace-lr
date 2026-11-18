import {
  CalendarDays, CheckCircle2, FileBarChart2, Percent, FileSpreadsheet, ChevronRight, ClipboardCheck, Compass, History, Home, KeyRound, LayoutList, LogOut,
  PlusCircle, RotateCcw, ShieldCheck, Star, UserRound,
} from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ROL_TXT, iniciales, type Rol } from "./data";
import { useStore, useToast } from "./store";
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
            <ImageTile img={{ id: "h", nombre: "", color: "linear-gradient(135deg,#2d7f74,#8fd3c4)" }} />
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
        <p className="hero-foot">Marketplace de alojamientos · Inversiones LR · Prototipo v1.0</p>
      </aside>
      <main className="auth-main"><div className="auth-box">{children}</div></main>
    </div>
  );
}

/* ---------- navegación por rol ---------- */
type Item = { to: string; label: string; icon: typeof Home; count?: number; end?: boolean };

function useNav(): { titulo: string; items: Item[] }[] {
  const { usuario, publicaciones } = useStore();
  if (!usuario) return [];
  const cuenta: Item[] = [
    { to: "/perfil", label: "Mi perfil", icon: UserRound },
    { to: "/perfil/contrasena", label: "Cambiar contraseña", icon: KeyRound },
    { to: "/roles", label: "Roles y permisos", icon: ShieldCheck },
  ];
  const porRol: Record<Rol, Item[]> = {
    HUESPED: [{ to: "/explorar", label: "Explorar alojamientos", icon: Compass }],
    ANFITRION: [
      { to: "/publicaciones", label: "Mis publicaciones", icon: LayoutList, end: true },
      { to: "/publicaciones/nueva", label: "Nueva publicación", icon: PlusCircle },
      { to: "/calendario", label: "Calendario", icon: CalendarDays },
    ],
    ADMINISTRADOR: [
      { to: "/admin/publicaciones", label: "Todas las publicaciones", icon: LayoutList },
      {
        to: "/admin/revision", label: "Pendientes de revisión", icon: ClipboardCheck,
        count: publicaciones.filter((p) => p.estado === "PENDIENTE_REVISION").length,
      },
      { to: "/admin/reportes/publicaciones", label: "Reporte de publicaciones", icon: FileSpreadsheet },
      { to: "/admin/tarifa", label: "Tarifa de servicio", icon: Percent },
      { to: "/admin/registro", label: "Registro de acciones", icon: History },
    ],
  };
  // El reporte de usuarios pertenece al módulo Usuarios y solo lo ve el Administrador
  const usuariosItems = usuario.rol === "ADMINISTRADOR"
    ? [...cuenta, { to: "/admin/reportes/usuarios", label: "Reporte de usuarios", icon: FileBarChart2 }]
    : cuenta;
  return [
    { titulo: "Alojamientos", items: porRol[usuario.rol] },
    { titulo: "Usuarios", items: usuariosItems },
  ];
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
  [/^\/admin\/revision/, "Pendientes de revisión"],
  [/^\/admin\/publicaciones/, "Todas las publicaciones"],
  [/^\/admin\/registro/, "Registro de acciones"],
  [/^\/admin\/tarifa/, "Tarifa de servicio"],
  [/^\/admin\/reportes\/usuarios/, "Reporte de usuarios"],
  [/^\/admin\/reportes\/publicaciones/, "Reporte de publicaciones"],
];

export function AppLayout() {
  const { usuario, cerrarSesion, restablecerDatos } = useStore();
  const toast = useToast();
  const nav = useNav();
  const loc = useLocation();
  const go = useNavigate();
  if (!usuario) return <Navigate to="/ingresar" replace />;
  const miga = MIGAS.find(([r]) => r.test(loc.pathname))?.[1] ?? "";
  const seccion = loc.pathname.startsWith("/perfil") || loc.pathname.startsWith("/roles") || loc.pathname.startsWith("/admin/reportes/usuarios") ? "Usuarios" : "Alojamientos";

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
        <div className="sidebar-foot">
          <b>Prototipo con datos de ejemplo</b>
          Los cambios se guardan solo en este navegador.
          <button
            className="btn btn-sm btn-ghost mt-8" style={{ color: "#cfe5df", paddingLeft: 0 }}
            onClick={() => { restablecerDatos(); toast("Datos de ejemplo restablecidos"); }}
          >
            <RotateCcw /> Restablecer datos
          </button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <span className="topbar-logo"><Logo /></span>
          <div className="crumbs"><span>{seccion}</span><ChevronRight /><b>{miga}</b></div>
          <div className="user-chip">
            <span className="avatar" aria-hidden>{iniciales(usuario.nombre)}</span>
            <div className="who"><b>{usuario.nombre}</b><span>{ROL_TXT[usuario.rol]}</span></div>
            <button className="btn btn-ghost btn-sm" onClick={async () => { await cerrarSesion(); go("/ingresar"); }}>
              <LogOut /> <span>Salir</span>
            </button>
          </div>
        </header>
        <nav className="mobile-nav" aria-label="Navegación">{links.map(renderLink)}</nav>
        <Outlet />
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

/** Protección por rol (RF-D-USU-02.1): quien no tiene el rol ve un aviso, no la función. */
export function SoloRol({ roles, children }: { roles: Rol[]; children: ReactNode }) {
  const { usuario } = useStore();
  if (!usuario) return <Navigate to="/ingresar" replace />;
  if (!roles.includes(usuario.rol)) return <Denegado titulo="No tienes permiso para esta función" />;
  return <>{children}</>;
}

/** Pantalla de acceso negado: además de avisar, deja el intento en el registro de acciones (CA-05.2). */
export function Denegado({ titulo, texto }: { titulo: string; texto?: string }) {
  const { usuario, registrarEvento } = useStore();
  const loc = useLocation();
  useEffect(() => { registrarEvento("Acceso negado", loc.pathname); }, [loc.pathname]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Page req="RF-D-USU-02.1 · HU-05 · CA-05.2">
      <div className="card empty-state">
        <ShieldCheck />
        <h2>{titulo}</h2>
        <p>{texto ?? `Tu rol (${usuario ? ROL_TXT[usuario.rol] : "Visitante"}) no puede usarla.`} El intento quedó registrado.</p>
        <Link className="btn btn-secondary" to="/">Volver al inicio</Link>
      </div>
    </Page>
  );
}

export function inicioPorRol(rol?: Rol) {
  if (rol === "ANFITRION") return "/publicaciones";
  if (rol === "ADMINISTRADOR") return "/admin/publicaciones";
  return "/explorar";
}
