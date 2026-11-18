import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { cuandoSePierdaLaSesion, identidadApi, leerError, renovarSesion, type UsuarioApi } from "./api";
import {
  SEED_PUBLICACIONES, SEED_RESERVAS, SEED_RESTRICCIONES, SEED_REVISIONES, SEED_TARIFAS, SEED_USUARIOS,
  faltantesRevision, isoDia, nochesReserva, tarifaVigente,
  type AccionModeracion, type EstadoPub, type Publicacion, type Reserva, type RestriccionUsuario, type RevisionPublicacion,
  type Rol, type TarifaServicio, type TokenRecuperacion, type Usuario,
} from "./data";

interface DB {
  usuarios: Usuario[];
  publicaciones: Publicacion[];
  reservas: Reserva[];
  tokens: TokenRecuperacion[];
  restricciones: RestriccionUsuario[];
  revisiones: RevisionPublicacion[];
  tarifas: TarifaServicio[];
  eventos: Evento[];
  sesionId: number | null;
}

/** EventoAuditoria del diagrama de clases: inicios de sesión, accesos negados, cambios de estado y descargas.
 *  La IP la llena el backend; en el prototipo (sin servidor) queda vacía. */
export interface Evento {
  id: number; fecha: string; quien: string; accion: string;
  entidad?: string; entidadId?: number; detalle: string; resultado: "EXITO" | "FALLO"; ip: string | null;
}
type Entidad = { entidad: string; entidadId?: number };

/** Acción de moderación que corresponde a cada cambio de estado hecho por el Administrador. */
const ACCION_MODERACION: Record<string, AccionModeracion> = {
  "PENDIENTE_REVISION>ACTIVA": "APROBAR", "PENDIENTE_REVISION>BORRADOR": "DEVOLVER",
  "ACTIVA>PAUSADA": "PAUSAR", "PAUSADA>ACTIVA": "REACTIVAR",
  "ACTIVA>BLOQUEADA": "BLOQUEAR", "PAUSADA>BLOQUEADA": "BLOQUEAR", "BLOQUEADA>PAUSADA": "DESBLOQUEAR",
};

/** Cambios de estado de una publicación que puede pedir cada rol. */
const TRANSICIONES: Record<"ANFITRION" | "ADMINISTRADOR", [EstadoPub, EstadoPub][]> = {
  ANFITRION: [["ACTIVA", "PAUSADA"], ["PAUSADA", "ACTIVA"]],
  ADMINISTRADOR: [
    ["PENDIENTE_REVISION", "ACTIVA"], ["PENDIENTE_REVISION", "BORRADOR"],
    ["ACTIVA", "PAUSADA"], ["PAUSADA", "ACTIVA"],
    ["ACTIVA", "BLOQUEADA"], ["PAUSADA", "BLOQUEADA"], ["BLOQUEADA", "PAUSADA"],
  ],
};

// v4: el usuario ya no tiene "estado" sino activa/restringida (modelo relacional). Las copias v3 se descartan.
const LLAVE = "alojamientos-lr-prototipo-v4";

const semilla = (): DB => ({
  usuarios: SEED_USUARIOS.map((u) => ({ ...u })),
  publicaciones: SEED_PUBLICACIONES.map((p) => ({ ...p })),
  reservas: SEED_RESERVAS.map((r) => ({ ...r })),
  tokens: [],
  restricciones: SEED_RESTRICCIONES.map((r) => ({ ...r })),
  revisiones: SEED_REVISIONES.map((r) => ({ ...r })),
  tarifas: SEED_TARIFAS.map((t) => ({ ...t })),
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
  // Usuarios: van contra la API real (SRV-01 Identidad). El resto del prototipo sigue local.
  /** true mientras se recupera la sesión al cargar la página (cookie de renovación). */
  cargandoSesion: boolean;
  iniciarSesion: (correo: string, clave: string) => Promise<Resultado>;
  cerrarSesion: () => Promise<void>;
  registrar: (d: { nombre: string; correo: string; telefono: string; clave: string; rol: Rol; acepta: boolean }) => Promise<Resultado>;
  solicitarEnlace: (correo: string) => Promise<{ ok: true; token: string } | { ok: false; error: string }>;
  estadoEnlace: (token: string) => Promise<"valido" | "vencido" | "usado" | "inexistente">;
  restablecer: (token: string, clave: string) => Promise<Resultado>;
  actualizarPerfil: (d: { nombre: string; telefono: string; ciudad: string | null }) => Promise<Resultado>;
  restriccionVigente: (usuarioId: number) => RestriccionUsuario | undefined;
  cambiarClave: (actual: string, nueva: string) => Promise<Resultado>;
  reservasPendientesDe: (u: Usuario) => Reserva[];
  desactivarCuenta: () => Promise<Resultado>;
  // Alojamientos
  guardarPublicacion: (p: Publicacion) => Publicacion;
  enviarARevision: (id: number, recienGuardada?: Publicacion) => Resultado;
  cambiarEstado: (id: number, estado: EstadoPub, observacion?: string) => Resultado;
  revisionesDe: (pubId: number) => RevisionPublicacion[];
  ultimaRevision: (pubId: number) => RevisionPublicacion | undefined;
  tarifaActual: number;
  cambiarTarifa: (porcentaje: number) => Resultado;
  reservasConfirmadas: (pubId: number) => Reserva[];
  nochesOcupadas: (pubId: number) => Set<string>;
  bloquearFechas: (pubId: number, fechas: string[]) => Resultado;
  liberarFechas: (pubId: number, fechas: string[]) => Resultado;
  visibleEnBusquedas: (p: Publicacion) => boolean;
  restablecerDatos: () => void;
  puedeModificar: (p: Publicacion) => boolean;
  registrarEvento: (accion: string, detalle: string, resultado?: Evento["resultado"], ent?: Entidad) => void;
}

const Ctx = createContext<Store | null>(null);

/**
 * Copia local de la cuenta que entregó la API. El prototipo guarda publicaciones y
 * reservas en el navegador y las relaciona por el id local del usuario, así que la
 * cuenta de la API se busca por correo (o se agrega) y se marca como la sesión.
 * La contraseña ya no se guarda en el navegador: la verifica el servidor.
 */
/** "2026-11-18T05:41:00Z" (UTC, como lo manda la API) -> "2026-11-18T00:41:00" en hora local. */
const isoLocal = (fecha: string | null) => {
  if (!fecha) return "";
  const d = new Date(fecha);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19);
};

function sincronizarCuenta(d: DB, a: UsuarioApi, hoy: string): Usuario {
  let u = d.usuarios.find((x) => x.correo.toLowerCase() === a.correo.toLowerCase());
  if (!u) {
    u = {
      id: Math.max(0, ...d.usuarios.map((x) => x.id)) + 1, nombre: a.nombre_completo, correo: a.correo,
      telefono: a.telefono, ciudad: a.ciudad, rol: a.rol, activa: a.activa, restringida: a.restringida, clave: "",
      fechaRegistro: isoLocal(a.fecha_registro).slice(0, 10) || hoy, autorizacionDatos: isoLocal(a.autorizacion_datos),
    };
    d.usuarios.push(u);
  }
  Object.assign(u, {
    nombre: a.nombre_completo, telefono: a.telefono, ciudad: a.ciudad, rol: a.rol, activa: a.activa,
    restringida: a.restringida, autorizacionDatos: isoLocal(a.autorizacion_datos), clave: "",
  });
  return u;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  // La sesión no se toma del localStorage: se recupera con la cookie al cargar.
  const [db, setDb] = useState<DB>(() => ({ ...cargar(), sesionId: null }));
  const [cargandoSesion, setCargandoSesion] = useState(true);

  useEffect(() => {
    try { localStorage.setItem(LLAVE, JSON.stringify(db)); } catch { /* sin espacio o bloqueado */ }
  }, [db]);

  const usuario = db.usuarios.find((u) => u.id === db.sesionId) ?? null;
  const hoy = isoDia(new Date());

  const upd = useCallback((f: (d: DB) => DB) => setDb((d) => f(structuredClone(d))), []);

  /** Marca como sesión la cuenta que devolvió la API (login, renovación o perfil). */
  const abrirSesion = useCallback(
    (a: UsuarioApi) => upd((d) => { d.sesionId = sincronizarCuenta(d, a, isoDia(new Date())).id; return d; }),
    [upd],
  );
  const olvidarSesion = useCallback(() => upd((d) => ({ ...d, sesionId: null })), [upd]);

  // Al cargar la página: si la cookie de renovación sigue vigente, se recupera la sesión.
  useEffect(() => {
    let activo = true;
    cuandoSePierdaLaSesion(olvidarSesion);
    renovarSesion()
      .then((s) => { if (activo && s) abrirSesion(s.usuario); })
      .finally(() => { if (activo) setCargandoSesion(false); });
    return () => { activo = false; };
  }, [abrirSesion, olvidarSesion]);

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

  const estadoEnlace = useCallback(async (token: string) => {
    try { return (await identidadApi.estadoEnlace(token)).data.estado; } catch { return "inexistente" as const; }
  }, []);

  /** Agrega un evento al registro dentro de una actualización. */
  const anotar = (d: DB, quien: string, accion: string, detalle: string, resultado: Evento["resultado"], ent?: Entidad) => {
    d.eventos.unshift({ id: Date.now() + Math.random(), fecha: new Date().toISOString(), quien, accion, ...ent, detalle, resultado, ip: null });
    d.eventos = d.eventos.slice(0, 300);
  };
  const quien = usuario ? `${usuario.correo} (${usuario.rol})` : "Visitante";
  /** Solo el anfitrión dueño o un administrador pueden modificar una publicación (RF-D-ALO-02.1). */
  const puedeModificar = (p: Publicacion) =>
    !!usuario && (usuario.rol === "ADMINISTRADOR" || (usuario.rol === "ANFITRION" && p.anfitrionId === usuario.id));
  const negar = (detalle: string, ent?: Entidad): Resultado => {
    upd((d) => { anotar(d, quien, "Acción no permitida", detalle, "FALLO", ent); return d; });
    return { ok: false, error: "No tienes permiso para esta acción." };
  };

  const ahoraIso = () => new Date().toISOString().slice(0, 19);
  const restriccionVigente = (usuarioId: number) => {
    const t = ahoraIso();
    return db.restricciones.find((r) => r.usuarioId === usuarioId && r.fechaInicio <= t && (!r.fechaFin || r.fechaFin >= t));
  };
  const revisionesDe = (pubId: number) =>
    db.revisiones.filter((r) => r.publicacionId === pubId).sort((a, b) => b.fecha.localeCompare(a.fecha));
  const tarifaActual = tarifaVigente(db.tarifas, ahoraIso());
  const PUB = (id: number): Entidad => ({ entidad: "Publicacion", entidadId: id });
  const USU = (id: number): Entidad => ({ entidad: "Usuario", entidadId: id });

  const store = useMemo<Store>(() => ({
    ...db,
    usuario,
    hoy,

    cargandoSesion,

    async iniciarSesion(correo, clave) {
      try {
        const sesion = await identidadApi.iniciarSesion(correo.trim(), clave);
        abrirSesion(sesion.usuario);
        return { ok: true, msg: sesion.aviso };
      } catch (e) {
        return { ok: false, ...leerError(e) };
      }
    },

    async cerrarSesion() {
      await identidadApi.salir().catch(() => {});
      olvidarSesion();
    },

    async registrar({ nombre, correo, telefono, clave, rol, acepta }) {
      try {
        await identidadApi.registrar({ nombre_completo: nombre.trim(), correo: correo.trim(), telefono: telefono.trim(), password: clave, rol, acepta_datos: acepta });
        return { ok: true };
      } catch (e) {
        const r = leerError(e);
        // Nombres de campo de la API -> nombres del formulario
        const campos: Record<string, string> = { nombre_completo: "nombre", password: "clave", acepta_datos: "acepta" };
        return { ok: false, error: r.error, campo: r.campo ? campos[r.campo] ?? r.campo : undefined };
      }
    },

    async solicitarEnlace(correo) {
      try {
        const { data } = await identidadApi.solicitarRecuperacion(correo.trim());
        const token = data.enlace?.split("/restablecer/")[1];
        // Si el correo no existe, la API no lo revela: responde igual, solo que sin enlace.
        if (!token) return { ok: false, error: "No apareció un enlace para ese correo. Revisa que esté bien escrito." };
        return { ok: true, token };
      } catch (e) {
        return { ok: false, error: leerError(e).error };
      }
    },

    estadoEnlace,

    async restablecer(token, clave) {
      try {
        await identidadApi.restablecer(token, clave);
        return { ok: true };
      } catch (e) {
        return { ok: false, ...leerError(e) };
      }
    },

    async actualizarPerfil({ nombre, telefono, ciudad }) {
      try {
        const { data } = await identidadApi.actualizarPerfil({ nombre_completo: nombre.trim(), telefono: telefono.trim(), ciudad });
        abrirSesion(data);
        return { ok: true };
      } catch (e) {
        return { ok: false, ...leerError(e) };
      }
    },

    async cambiarClave(actual, nueva) {
      try {
        await identidadApi.actualizarPerfil({ password_actual: actual, password_nueva: nueva });
        return { ok: true };
      } catch (e) {
        const r = leerError(e);
        return { ok: false, error: r.error, campo: r.campo === "password_nueva" ? "nueva" : "actual" };
      }
    },

    reservasPendientesDe,
    restriccionVigente,

    async desactivarCuenta() {
      try {
        await identidadApi.desactivar();
        olvidarSesion();
        return { ok: true };
      } catch (e) {
        // CA-04.2: con reservas confirmadas pendientes la API responde 409 con el motivo.
        return { ok: false, ...leerError(e) };
      }
    },

    guardarPublicacion(p) {
      const nueva = p.id === 0;
      const actual = db.publicaciones.find((x) => x.id === p.id);
      if (nueva ? usuario?.rol !== "ANFITRION" : !actual || !puedeModificar(actual)) { negar(`Guardar «${p.titulo}»`, PUB(p.id)); return p; }
      const guardada: Publicacion = {
        ...p,
        id: nueva ? Math.max(0, ...db.publicaciones.map((x) => x.id)) + 1 : p.id,
        actualizada: hoy,
        creada: nueva ? hoy : (p.creada ?? actual?.creada),
      };
      upd((d) => {
        if (nueva) d.publicaciones.unshift(guardada);
        else d.publicaciones[d.publicaciones.findIndex((x) => x.id === p.id)] = guardada;
        anotar(d, quien, nueva ? "Publicación creada" : "Publicación editada", `«${guardada.titulo}» (${guardada.estado})`, "EXITO", PUB(guardada.id));
        return d;
      });
      return guardada;
    },

    enviarARevision(id, recienGuardada) {
      const p = recienGuardada ?? db.publicaciones.find((x) => x.id === id);
      if (!p) return { ok: false, error: "No existe" };
      if (usuario?.rol !== "ANFITRION" || p.anfitrionId !== usuario.id) return negar(`Enviar a revisión «${p.titulo}»`, PUB(id));
      const f = faltantesRevision(p);
      if (f.length) return { ok: false, error: "Falta: " + f.join(", ") + "." };
      upd((d) => { const x = d.publicaciones.find((y) => y.id === id)!; x.estado = "PENDIENTE_REVISION"; anotar(d, quien, "Cambio de estado", `«${x.titulo}»: BORRADOR → PENDIENTE_REVISION`, "EXITO", PUB(id)); return d; });
      return { ok: true };
    },

    cambiarEstado(id, estado, observacion) {
      const p = db.publicaciones.find((y) => y.id === id);
      if (!p || !usuario || usuario.rol === "HUESPED" || !puedeModificar(p)) return negar(`Cambiar a ${estado} la publicación ${id}`, PUB(id));
      const ok = TRANSICIONES[usuario.rol].some(([a, b]) => a === p.estado && b === estado);
      if (!ok) return negar(`«${p.titulo}»: ${p.estado} → ${estado}`, PUB(id));
      const accion = usuario.rol === "ADMINISTRADOR" ? ACCION_MODERACION[`${p.estado}>${estado}`] : undefined;
      if ((accion === "DEVOLVER" || accion === "BLOQUEAR") && !observacion?.trim())
        return { ok: false, error: accion === "DEVOLVER" ? "Escribe la observación para el anfitrión." : "Escribe el motivo del bloqueo." };
      upd((d) => {
        d.publicaciones.find((y) => y.id === id)!.estado = estado;
        if (accion) d.revisiones.push({
          id: Math.max(0, ...d.revisiones.map((r) => r.id)) + 1, publicacionId: id, adminId: usuario.id,
          accion, observacion: observacion?.trim() || undefined, fecha: ahoraIso(),
        });
        anotar(d, quien, "Cambio de estado", `«${p.titulo}»: ${p.estado} → ${estado}${accion ? ` (${accion})` : ""}`, "EXITO", PUB(id));
        return d;
      });
      return { ok: true };
    },

    revisionesDe,
    ultimaRevision: (pubId) => revisionesDe(pubId)[0],
    tarifaActual,

    cambiarTarifa(porcentaje) {
      if (usuario?.rol !== "ADMINISTRADOR") return negar("Cambiar la tarifa de servicio", { entidad: "TarifaServicio" });
      if (!Number.isFinite(porcentaje) || porcentaje < 0 || porcentaje > 30)
        return { ok: false, error: "El porcentaje debe estar entre 0 % y 30 %." };
      if (porcentaje === tarifaActual) return { ok: false, error: "Ese ya es el porcentaje vigente." };
      upd((d) => {
        d.tarifas.push({ porcentaje, vigenteDesde: ahoraIso() });
        anotar(d, quien, "Tarifa de servicio", `${tarifaActual} % → ${porcentaje} %`, "EXITO", { entidad: "TarifaServicio" });
        return d;
      });
      return { ok: true };
    },

    reservasConfirmadas,
    nochesOcupadas,

    bloquearFechas(pubId, fechas) {
      const pub = db.publicaciones.find((x) => x.id === pubId);
      if (!pub || usuario?.rol !== "ANFITRION" || pub.anfitrionId !== usuario.id) return negar(`Bloquear fechas de la publicación ${pubId}`, PUB(pubId));
      const occ = nochesOcupadas(pubId);
      const choque = fechas.filter((f) => occ.has(f));
      if (choque.length) return { ok: false, error: `No se puede bloquear ${choque.length === 1 ? "esa fecha" : "esas fechas"}: ${choque.length === 1 ? "tiene" : "tienen"} una reserva CONFIRMADA.` };
      upd((d) => { const p = d.publicaciones.find((x) => x.id === pubId)!; p.bloqueos = [...new Set([...p.bloqueos, ...fechas])].sort(); return d; });
      return { ok: true };
    },

    liberarFechas(pubId, fechas) {
      const pub = db.publicaciones.find((x) => x.id === pubId);
      if (!pub || usuario?.rol !== "ANFITRION" || pub.anfitrionId !== usuario.id) return negar(`Liberar fechas de la publicación ${pubId}`, PUB(pubId));
      upd((d) => { const p = d.publicaciones.find((x) => x.id === pubId)!; p.bloqueos = p.bloqueos.filter((f) => !fechas.includes(f)); return d; });
      return { ok: true };
    },

    visibleEnBusquedas(p) {
      const a = db.usuarios.find((u) => u.id === p.anfitrionId);
      // Visible si la cuenta del anfitrión está activa y sin restricción vigente (CA-04.3)
      return p.estado === "ACTIVA" && !!a?.activa && !restriccionVigente(a.id);
    },

    restablecerDatos() { const s = semilla(); s.sesionId = db.sesionId; setDb(s); },

    puedeModificar,
    registrarEvento(accion, detalle, resultado = "FALLO", ent) {
      upd((d) => { anotar(d, quien, accion, detalle, resultado, ent); return d; });
    },
  }), [db, usuario, hoy, upd, reservasConfirmadas, nochesOcupadas, reservasPendientesDe, estadoEnlace, cargandoSesion, abrirSesion, olvidarSesion]);

  // Mientras se recupera la sesión no se pintan las rutas: si no, las protegidas
  // mandarían a "Ingresar" antes de saber si había una sesión abierta.
  return (
    <Ctx.Provider value={store}>
      {cargandoSesion ? <p className="muted" style={{ textAlign: "center", padding: 48 }}>Cargando…</p> : children}
    </Ctx.Provider>
  );
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
