import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { cuandoSePierdaLaSesion, identidadApi, leerError, renovarSesion, type UsuarioApi } from "./api";

/**
 * Sesión real (HU-02, ADR-005). No hay datos locales: cada pantalla lee y escribe en la API.
 *
 * - El token de acceso vive solo en memoria (api.ts); nada va a localStorage ni a sessionStorage.
 * - Al cargar la página la sesión se recupera con POST /identidad/token/renovar y la cookie httpOnly.
 * - Al entrar y al recargar se piden los permisos (GET /identidad/permisos). Las rutas y el menú se deciden con
 *   ellos; el rol solo se muestra en pantalla.
 * - Si una petición responde 401 y no se puede renovar, la sesión se cierra y se avisa en "Ingresar".
 */

export type Resultado = { ok: true; msg?: string } | { ok: false; error: string; campo?: string };

export const SESION_TERMINADA = "Tu sesión terminó. Vuelve a iniciar sesión.";

interface Sesion {
  usuario: UsuarioApi | null;
  /** Permisos "modulo.accion" del usuario actual (o del Visitante sin sesión), según GET /identidad/permisos. */
  permisos: ReadonlySet<string>;
  tiene: (...permisos: string[]) => boolean;
  /** true mientras se recupera la sesión al cargar la página. */
  cargandoSesion: boolean;
  /** Mensaje para "Ingresar" cuando la sesión terminó sola (401 sin poder renovar). */
  avisoSesion: string;
  limpiarAviso: () => void;
  iniciarSesion: (correo: string, clave: string) => Promise<Resultado>;
  cerrarSesion: () => Promise<void>;
  /** Actualiza el usuario en pantalla con la respuesta de la API (perfil). */
  actualizarUsuario: (u: UsuarioApi) => void;
  /** La cuenta se desactivó: se olvida la sesión sin llamar a /salir (la API ya cerró todas). */
  olvidarSesion: () => void;
  /** Vuelve a pedir los permisos (el Administrador cambió la matriz de su propio rol, ADR-010). */
  recargarPermisos: () => Promise<void>;
}

const Ctx = createContext<Sesion | null>(null);

async function cargarPermisos(): Promise<Set<string>> {
  try { return new Set((await identidadApi.permisos()).data.permisos); } catch { return new Set(); }
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<UsuarioApi | null>(null);
  const [permisos, setPermisos] = useState<ReadonlySet<string>>(new Set());
  const [cargandoSesion, setCargandoSesion] = useState(true);
  const [avisoSesion, setAvisoSesion] = useState("");

  const abrir = useCallback(async (u: UsuarioApi) => {
    const p = await cargarPermisos();
    setPermisos(p);
    setUsuario(u);
  }, []);

  const olvidarSesion = useCallback(() => {
    setUsuario(null);
    cargarPermisos().then(setPermisos);  // vuelve a los del Visitante
  }, []);

  // Al cargar la página: si la cookie de renovación sigue vigente, se recupera la sesión.
  useEffect(() => {
    let activo = true;
    cuandoSePierdaLaSesion(() => {
      if (!activo) return;
      setAvisoSesion(SESION_TERMINADA);
      olvidarSesion();
    });
    renovarSesion()
      .then(async (s) => {
        if (!activo) return;
        if (s) await abrir(s.usuario);
        else setPermisos(await cargarPermisos());
      })
      .finally(() => { if (activo) setCargandoSesion(false); });
    return () => { activo = false; };
  }, [abrir, olvidarSesion]);

  const sesion = useMemo<Sesion>(() => ({
    usuario,
    permisos,
    tiene: (...ps) => ps.some((p) => permisos.has(p)),
    cargandoSesion,
    avisoSesion,
    limpiarAviso: () => setAvisoSesion(""),

    async iniciarSesion(correo, clave) {
      try {
        const s = await identidadApi.iniciarSesion(correo.trim(), clave);
        setAvisoSesion("");
        await abrir(s.usuario);
        return { ok: true, msg: s.aviso };
      } catch (e) {
        // CA-02.2: 401 "Correo o contraseña incorrectos". CA-02.3: 403 con el motivo de la restricción en el detalle.
        return { ok: false, ...leerError(e) };
      }
    },

    async cerrarSesion() {
      await identidadApi.salir().catch(() => {});
      setAvisoSesion("");
      olvidarSesion();
    },

    actualizarUsuario: (u) => setUsuario(u),
    olvidarSesion,
    recargarPermisos: async () => setPermisos(await cargarPermisos()),
  }), [usuario, permisos, cargandoSesion, avisoSesion, abrir, olvidarSesion]);

  // Mientras se recupera la sesión no se pintan las rutas: si no, las protegidas
  // mandarían a "Ingresar" antes de saber si había una sesión abierta.
  return (
    <Ctx.Provider value={sesion}>
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
