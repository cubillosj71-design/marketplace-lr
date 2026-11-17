import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  SEED_PUBLICACIONES, SEED_RESERVAS, SEED_USUARIOS, faltantesRevision, isoDia, nochesReserva,
  type EstadoPub, type Publicacion, type Reserva, type Rol, type TokenRecuperacion, type Usuario,
} from "./data";

interface DB {
  usuarios: Usuario[];
  publicaciones: Publicacion[];
  reservas: Reserva[];
  tokens: TokenRecuperacion[];
  eventos: Evento[];
  sesionId: number | null;
}

/** Registro de acciones (RNF de trazabilidad): inicios de sesión, accesos negados y cambios de estado. */
export interface Evento { id: number; fecha: string; quien: string; accion: string; detalle: string; resultado: "EXITO" | "FALLO" }

/** Cambios de estado de una publicación que puede pedir cada rol. */
const TRANSICIONES: Record<"ANFITRION" | "ADMINISTRADOR", [EstadoPub, EstadoPub][]> = {
  ANFITRION: [["ACTIVA", "PAUSADA"], ["PAUSADA", "ACTIVA"]],
  ADMINISTRADOR: [
    ["PENDIENTE_REVISION", "ACTIVA"], ["PENDIENTE_REVISION", "BORRADOR"],
    ["ACTIVA", "PAUSADA"], ["PAUSADA", "ACTIVA"],
    ["ACTIVA", "BLOQUEADA"], ["PAUSADA", "BLOQUEADA"], ["BLOQUEADA", "PAUSADA"],
  ],
};

const LLAVE = "alojamientos-lr-prototipo-v2";
const VIGENCIA_ENLACE_MS = 20 * 60 * 1000; // el enlace sirve una vez y por máximo 20 minutos

const semilla = (): DB => ({
  usuarios: SEED_USUARIOS.map((u) => ({ ...u })),
  publicaciones: SEED_PUBLICACIONES.map((p) => ({ ...p })),
  reservas: SEED_RESERVAS.map((r) => ({ ...r })),
  tokens: [],
  eventos: [],
  sesionId: null,
});

const cargar = (): DB => {
  try {
    const raw = localStorage.getItem(LLAVE);
    if (raw) return { ...semilla(), ...(JSON.parse(raw) as Partial<DB>) };
  } catch { /* sin almacenamiento: se usa la semilla */ }
  return semilla();
};

export type Resultado = { ok: true; msg?: string } | { ok: false; error: string; campo?: string };

interface Store extends DB {
  usuario: Usuario | null;
  hoy: string;
  // Usuarios
  iniciarSesion: (correo: string, clave: string) => Resultado;
  cerrarSesion: () => void;
  registrar: (d: { nombre: string; correo: string; telefono: string; clave: string; rol: Rol }) => Resultado;
  solicitarEnlace: (correo: string) => { ok: true; token: string } | { ok: false; error: string };
  estadoEnlace: (token: string) => "valido" | "vencido" | "usado" | "inexistente";
  vencerEnlace: (token: string) => void;
  restablecer: (token: string, clave: string) => Resultado;
  actualizarPerfil: (d: { nombre: string; telefono: string; ciudad: string }) => Resultado;
  cambiarClave: (actual: string, nueva: string) => Resultado;
  reservasPendientesDe: (u: Usuario) => Reserva[];
  desactivarCuenta: () => Resultado;
  // Alojamientos
  guardarPublicacion: (p: Publicacion) => Publicacion;
  enviarARevision: (id: number, recienGuardada?: Publicacion) => Resultado;
  cambiarEstado: (id: number, estado: EstadoPub, extra?: Partial<Publicacion>) => Resultado;
  reservasConfirmadas: (pubId: number) => Reserva[];
  nochesOcupadas: (pubId: number) => Set<string>;
  bloquearFechas: (pubId: number, fechas: string[]) => Resultado;
  liberarFechas: (pubId: number, fechas: string[]) => Resultado;
  visibleEnBusquedas: (p: Publicacion) => boolean;
  restablecerDatos: () => void;
  puedeModificar: (p: Publicacion) => boolean;
  registrarEvento: (accion: string, detalle: string, resultado?: Evento["resultado"]) => void;
}

const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [db, setDb] = useState<DB>(cargar);

  useEffect(() => {
    try { localStorage.setItem(LLAVE, JSON.stringify(db)); } catch { /* sin espacio o bloqueado */ }
  }, [db]);

  const usuario = db.usuarios.find((u) => u.id === db.sesionId) ?? null;
  const hoy = isoDia(new Date());

  const upd = useCallback((f: (d: DB) => DB) => setDb((d) => f(structuredClone(d))), []);

  const reservasConfirmadas = useCallback(
    (pubId: number) => db.reservas.filter((r) => r.publicacionId === pubId && r.estado === "CONFIRMADA"),
    [db.reservas],
  );

  const nochesOcupadas = useCallback(
    (pubId: number) => new Set(reservasConfirmadas(pubId).flatMap(nochesReserva)),
    [reservasConfirmadas],
  );

  const reservasPendientesDe = useCallback(
    (u: Usuario) => {
      const mias = new Set(db.publicaciones.filter((p) => p.anfitrionId === u.id).map((p) => p.id));
      return db.reservas.filter(
        (r) => r.estado === "CONFIRMADA" && r.salida >= hoy && (r.huespedId === u.id || mias.has(r.publicacionId)),
      );
    },
    [db.publicaciones, db.reservas, hoy],
  );

  const estadoEnlace = useCallback((token: string): "valido" | "vencido" | "usado" | "inexistente" => {
    const t = db.tokens.find((x) => x.token === token);
    if (!t) return "inexistente";
    if (t.usado) return "usado";
    if (Date.now() - t.creado > VIGENCIA_ENLACE_MS) return "vencido";
    return "valido";
  }, [db.tokens]);

  /** Agrega un evento al registro dentro de una actualización. */
  const anotar = (d: DB, quien: string, accion: string, detalle: string, resultado: Evento["resultado"]) => {
    d.eventos.unshift({ id: Date.now() + Math.random(), fecha: new Date().toISOString(), quien, accion, detalle, resultado });
    d.eventos = d.eventos.slice(0, 300);
  };
  const quien = usuario ? `${usuario.correo} (${usuario.rol})` : "Visitante";
  /** Solo el anfitrión dueño o un administrador pueden modificar una publicación (RF-D-ALO-02.1). */
  const puedeModificar = (p: Publicacion) =>
    !!usuario && (usuario.rol === "ADMINISTRADOR" || (usuario.rol === "ANFITRION" && p.anfitrionId === usuario.id));
  const negar = (detalle: string): Resultado => {
    upd((d) => { anotar(d, quien, "Acción no permitida", detalle, "FALLO"); return d; });
    return { ok: false, error: "No tienes permiso para esta acción." };
  };

  const store = useMemo<Store>(() => ({
    ...db,
    usuario,
    hoy,

    iniciarSesion(correo, clave) {
      const u = db.usuarios.find((x) => x.correo.toLowerCase() === correo.trim().toLowerCase());
      if (!u || u.clave !== clave) {
        upd((d) => { anotar(d, correo.trim() || "(sin correo)", "Inicio de sesión", "Correo o contraseña incorrectos", "FALLO"); return d; });
        return { ok: false, error: "Correo o contraseña incorrectos. Revisa los datos e inténtalo de nuevo." };
      }
      if (u.estado === "RESTRINGIDA") {
        upd((d) => { anotar(d, u.correo, "Inicio de sesión", "Cuenta restringida", "FALLO"); return d; });
        return { ok: false, error: "Tu cuenta está restringida por el administrador. No puedes iniciar sesión mientras la restricción esté vigente." };
      }
      const reactivada = u.estado === "DESACTIVADA";
      upd((d) => {
        const x = d.usuarios.find((y) => y.id === u.id)!;
        x.estado = "ACTIVA";
        d.sesionId = u.id;
        anotar(d, `${u.correo} (${u.rol})`, "Inicio de sesión", reactivada ? "Cuenta reactivada al ingresar" : "Ingreso correcto", "EXITO");
        return d;
      });
      return { ok: true, msg: reactivada ? "Tu cuenta se reactivó. ¡Bienvenido de nuevo!" : undefined };
    },

    cerrarSesion() { upd((d) => ({ ...d, sesionId: null })); },

    registrar({ nombre, correo, telefono, clave, rol }) {
      if (db.usuarios.some((u) => u.correo.toLowerCase() === correo.trim().toLowerCase()))
        return { ok: false, error: "Este correo ya está registrado.", campo: "correo" };
      upd((d) => {
        d.usuarios.push({
          id: Math.max(...d.usuarios.map((u) => u.id)) + 1,
          nombre: nombre.trim(), correo: correo.trim(), telefono: telefono.trim(), ciudad: "",
          rol, estado: "ACTIVA", clave,
        });
        return d;
      });
      return { ok: true };
    },

    solicitarEnlace(correo) {
      const u = db.usuarios.find((x) => x.correo.toLowerCase() === correo.trim().toLowerCase());
      if (!u) return { ok: false, error: "No encontramos una cuenta con ese correo." };
      const token = Math.random().toString(36).slice(2, 10);
      upd((d) => { d.tokens.push({ token, correo: u.correo, creado: Date.now(), usado: false }); return d; });
      return { ok: true, token };
    },

    estadoEnlace,

    vencerEnlace(token) {
      upd((d) => { const t = d.tokens.find((x) => x.token === token); if (t) t.creado -= 21 * 60 * 1000; return d; });
    },

    restablecer(token, clave) {
      const est = estadoEnlace(token);
      if (est !== "valido") return { ok: false, error: est === "usado" ? "Este enlace ya se usó." : "Este enlace venció. Solicita uno nuevo." };
      upd((d) => {
        const t = d.tokens.find((x) => x.token === token)!;
        t.usado = true;
        d.usuarios.find((u) => u.correo === t.correo)!.clave = clave;
        return d;
      });
      return { ok: true };
    },

    actualizarPerfil({ nombre, telefono, ciudad }) {
      if (!usuario) return { ok: false, error: "Sin sesión" };
      upd((d) => { Object.assign(d.usuarios.find((u) => u.id === usuario.id)!, { nombre, telefono, ciudad }); return d; });
      return { ok: true };
    },

    cambiarClave(actual, nueva) {
      if (!usuario) return { ok: false, error: "Sin sesión" };
      if (usuario.clave !== actual) return { ok: false, error: "La contraseña actual no es correcta.", campo: "actual" };
      upd((d) => { d.usuarios.find((u) => u.id === usuario.id)!.clave = nueva; return d; });
      return { ok: true };
    },

    reservasPendientesDe,

    desactivarCuenta() {
      if (!usuario) return { ok: false, error: "Sin sesión" };
      if (usuario.rol === "ADMINISTRADOR") return negar("Desactivar una cuenta de administrador");
      const pend = reservasPendientesDe(usuario);
      if (pend.length) return { ok: false, error: "Tienes reservas confirmadas pendientes." };
      upd((d) => { d.usuarios.find((u) => u.id === usuario.id)!.estado = "DESACTIVADA"; d.sesionId = null; anotar(d, quien, "Cuenta desactivada", "Por su titular", "EXITO"); return d; });
      return { ok: true };
    },

    guardarPublicacion(p) {
      const nueva = p.id === 0;
      const actual = db.publicaciones.find((x) => x.id === p.id);
      if (nueva ? usuario?.rol !== "ANFITRION" : !actual || !puedeModificar(actual)) { negar(`Guardar «${p.titulo}»`); return p; }
      const guardada: Publicacion = {
        ...p,
        id: nueva ? Math.max(0, ...db.publicaciones.map((x) => x.id)) + 1 : p.id,
        actualizada: hoy,
      };
      upd((d) => {
        if (nueva) d.publicaciones.unshift(guardada);
        else d.publicaciones[d.publicaciones.findIndex((x) => x.id === p.id)] = guardada;
        anotar(d, quien, nueva ? "Publicación creada" : "Publicación editada", `«${guardada.titulo}» (${guardada.estado})`, "EXITO");
        return d;
      });
      return guardada;
    },

    enviarARevision(id, recienGuardada) {
      const p = recienGuardada ?? db.publicaciones.find((x) => x.id === id);
      if (!p) return { ok: false, error: "No existe" };
      if (usuario?.rol !== "ANFITRION" || p.anfitrionId !== usuario.id) return negar(`Enviar a revisión «${p.titulo}»`);
      const f = faltantesRevision(p);
      if (f.length) return { ok: false, error: "Falta: " + f.join(", ") + "." };
      upd((d) => { const x = d.publicaciones.find((y) => y.id === id)!; x.estado = "PENDIENTE_REVISION"; x.observacion = undefined; anotar(d, quien, "Cambio de estado", `«${x.titulo}»: BORRADOR → PENDIENTE_REVISION`, "EXITO"); return d; });
      return { ok: true };
    },

    cambiarEstado(id, estado, extra) {
      const p = db.publicaciones.find((y) => y.id === id);
      if (!p || !usuario || usuario.rol === "HUESPED" || !puedeModificar(p)) return negar(`Cambiar a ${estado} la publicación ${id}`);
      const ok = TRANSICIONES[usuario.rol].some(([a, b]) => a === p.estado && b === estado);
      if (!ok) return negar(`«${p.titulo}»: ${p.estado} → ${estado}`);
      upd((d) => {
        Object.assign(d.publicaciones.find((y) => y.id === id)!, { estado, ...extra });
        anotar(d, quien, "Cambio de estado", `«${p.titulo}»: ${p.estado} → ${estado}`, "EXITO");
        return d;
      });
      return { ok: true };
    },

    reservasConfirmadas,
    nochesOcupadas,

    bloquearFechas(pubId, fechas) {
      const pub = db.publicaciones.find((x) => x.id === pubId);
      if (!pub || usuario?.rol !== "ANFITRION" || pub.anfitrionId !== usuario.id) return negar(`Bloquear fechas de la publicación ${pubId}`);
      const occ = nochesOcupadas(pubId);
      const choque = fechas.filter((f) => occ.has(f));
      if (choque.length) return { ok: false, error: `No se puede bloquear ${choque.length === 1 ? "esa fecha" : "esas fechas"}: ${choque.length === 1 ? "tiene" : "tienen"} una reserva CONFIRMADA.` };
      upd((d) => { const p = d.publicaciones.find((x) => x.id === pubId)!; p.bloqueos = [...new Set([...p.bloqueos, ...fechas])].sort(); return d; });
      return { ok: true };
    },

    liberarFechas(pubId, fechas) {
      const pub = db.publicaciones.find((x) => x.id === pubId);
      if (!pub || usuario?.rol !== "ANFITRION" || pub.anfitrionId !== usuario.id) return negar(`Liberar fechas de la publicación ${pubId}`);
      upd((d) => { const p = d.publicaciones.find((x) => x.id === pubId)!; p.bloqueos = p.bloqueos.filter((f) => !fechas.includes(f)); return d; });
      return { ok: true };
    },

    visibleEnBusquedas(p) {
      const a = db.usuarios.find((u) => u.id === p.anfitrionId);
      return p.estado === "ACTIVA" && a?.estado === "ACTIVA";
    },

    restablecerDatos() { const s = semilla(); s.sesionId = db.sesionId; setDb(s); },

    puedeModificar,
    registrarEvento(accion, detalle, resultado = "FALLO") {
      upd((d) => { anotar(d, quien, accion, detalle, resultado); return d; });
    },
  }), [db, usuario, hoy, upd, reservasConfirmadas, nochesOcupadas, reservasPendientesDe, estadoEnlace]);

  return <Ctx.Provider value={store}>{children}</Ctx.Provider>;
}

export const useStore = () => {
  const s = useContext(Ctx);
  if (!s) throw new Error("StoreProvider ausente");
  return s;
};

// ---------- avisos (toasts) ----------
type Toast = { id: number; text: string; tipo: "ok" | "err" };
const ToastCtx = createContext<(text: string, tipo?: "ok" | "err") => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, tipo: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((t) => [...t, { id, text, tipo }]);
    setTimeout(() => setItems((t) => t.filter((x) => x.id !== id)), 3600);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.tipo}`}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              {t.tipo === "ok" ? <path d="M20 6 9 17l-5-5" /> : <><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></>}
            </svg>
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);
