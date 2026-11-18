import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

/**
 * Cliente HTTP de toda la aplicación.
 *
 * - El token de acceso vive solo en esta variable (memoria), nunca en
 *   localStorage: un script inyectado en la página podría leer localStorage y
 *   robar la sesión (ADR-005, C4 nivel 2).
 * - El token de renovación lo guarda el navegador en una cookie httpOnly que
 *   JavaScript no puede leer; withCredentials hace que viaje con las peticiones.
 * - Si una petición responde 401 porque el token de acceso venció, se renueva
 *   una vez y se repite la petición, sin que el usuario lo note.
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "/api/v1",
  withCredentials: true,
});

let tokenAcceso: string | null = null;
let alPerderSesion: () => void = () => {};

export function guardarTokenAcceso(token: string | null) {
  tokenAcceso = token;
}

/** El contexto de sesión registra aquí qué hacer cuando la sesión ya no se puede renovar. */
export function cuandoSePierdaLaSesion(accion: () => void) {
  alPerderSesion = accion;
}

api.interceptors.request.use((config) => {
  if (tokenAcceso) config.headers.Authorization = `Bearer ${tokenAcceso}`;
  return config;
});

// Rutas que no deben disparar una renovación automática (evita ciclos).
const RUTAS_DE_SESION = ["/identidad/token", "/identidad/token/renovar", "/identidad/salir"];

// Si varias peticiones fallan a la vez, todas esperan la misma renovación.
let renovacionEnCurso: Promise<string | null> | null = null;

export async function renovarSesion(): Promise<{ access: string; usuario: unknown } | null> {
  try {
    const { data } = await api.post("/identidad/token/renovar");
    guardarTokenAcceso(data.access);
    return data;
  } catch {
    guardarTokenAcceso(null);
    return null;
  }
}

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const original = error.config as (InternalAxiosRequestConfig & { _reintentada?: boolean }) | undefined;
  const esRutaDeSesion = RUTAS_DE_SESION.some((ruta) => original?.url?.startsWith(ruta));

  if (error.response?.status !== 401 || !original || original._reintentada || esRutaDeSesion) {
    throw error;
  }

  original._reintentada = true;
  renovacionEnCurso ??= renovarSesion()
    .then((datos) => datos?.access ?? null)
    .finally(() => {
      renovacionEnCurso = null;
    });
  const nuevo = await renovacionEnCurso;
  if (!nuevo) {
    alPerderSesion();
    throw error;
  }
  original.headers.Authorization = `Bearer ${nuevo}`;
  return api(original);
});
