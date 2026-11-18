import axios, { AxiosError, isAxiosError, type InternalAxiosRequestConfig } from "axios";

/**
 * Cliente HTTP de la API REST (/api/v1).
 *
 * Sesión (ADR-005 y C4 nivel 2):
 * - El token de acceso vive solo en la variable `tokenAcceso` (memoria), nunca en
 *   localStorage: un script inyectado en la página podría leer localStorage y robar
 *   la sesión.
 * - El token de renovación lo guarda el navegador en la cookie httpOnly `renovacion`,
 *   que JavaScript no puede leer. withCredentials hace que viaje con las peticiones.
 * - Si una petición responde 401 porque el access venció, se renueva una vez y se repite.
 *
 * La ruta base es relativa: en desarrollo Vite reenvía /api a Django (vite.config.ts) y
 * en Render lo hace la regla de reescritura del sitio estático. Así el navegador ve un
 * solo origen y la cookie SameSite=Strict funciona sin configurar CORS con credenciales.
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

/** El store registra aquí qué hacer cuando la sesión ya no se puede renovar. */
export function cuandoSePierdaLaSesion(accion: () => void) {
  alPerderSesion = accion;
}

api.interceptors.request.use((config) => {
  if (tokenAcceso) config.headers.Authorization = `Bearer ${tokenAcceso}`;
  return config;
});

const RUTAS_DE_SESION = ["/identidad/token", "/identidad/salir"];
let renovacionEnCurso: Promise<string | null> | null = null;

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const original = error.config as (InternalAxiosRequestConfig & { _reintentada?: boolean }) | undefined;
  const esRutaDeSesion = RUTAS_DE_SESION.some((ruta) => original?.url?.startsWith(ruta));
  if (error.response?.status !== 401 || !original || original._reintentada || esRutaDeSesion) throw error;

  original._reintentada = true;
  // Si varias peticiones fallan a la vez, todas esperan la misma renovación.
  renovacionEnCurso ??= renovarSesion()
    .then((s) => s?.access ?? null)
    .finally(() => { renovacionEnCurso = null; });
  const nuevo = await renovacionEnCurso;
  if (!nuevo) { alPerderSesion(); throw error; }
  original.headers.Authorization = `Bearer ${nuevo}`;
  return api(original);
});

/* ---------------- SRV-01 Identidad (backend/API.md) ---------------- */

export interface UsuarioApi {
  id: number;
  correo: string;
  nombre_completo: string;
  telefono: string;
  ciudad: string | null; // texto opcional
  rol: "HUESPED" | "ANFITRION" | "ADMINISTRADOR";
  activa: boolean; // false solo si el usuario desactivó su cuenta
  restringida: boolean; // derivado: hay una RestriccionUsuario vigente (no es columna)
  autorizacion_datos: string | null; // fecha y hora de la autorización de datos (Ley 1581)
  fecha_registro: string | null;
}

export interface SesionApi {
  access: string;
  usuario: UsuarioApi;
  aviso?: string;
}

export async function renovarSesion(): Promise<SesionApi | null> {
  try {
    const { data } = await api.post<SesionApi>("/identidad/token/renovar");
    guardarTokenAcceso(data.access);
    return data;
  } catch {
    guardarTokenAcceso(null);
    return null;
  }
}

export const identidadApi = {
  async iniciarSesion(correo: string, password: string) {
    const { data } = await api.post<SesionApi>("/identidad/token", { correo, password });
    guardarTokenAcceso(data.access);
    return data;
  },
  async salir() {
    try { await api.post("/identidad/salir"); } finally { guardarTokenAcceso(null); }
  },
  registrar: (d: { nombre_completo: string; correo: string; telefono: string; password: string; rol: string; acepta_datos: boolean }) =>
    api.post<UsuarioApi>("/identidad/registro", d),
  solicitarRecuperacion: (correo: string) =>
    api.post<{ detalle: string; enlace?: string }>("/identidad/recuperacion", { correo }),
  estadoEnlace: (token: string) =>
    api.get<{ estado: "valido" | "vencido" | "usado" | "inexistente" }>(`/identidad/recuperacion/${encodeURIComponent(token)}`),
  restablecer: (token: string, password: string) =>
    api.post(`/identidad/recuperacion/${encodeURIComponent(token)}`, { password }),
  actualizarPerfil: (cambios: Record<string, string | null>) => api.patch<UsuarioApi>("/identidad/perfil", cambios),
  desactivar: () => api.post("/identidad/perfil/desactivar"),
};

/**
 * Convierte un error de la API en { error, campo }.
 * El backend responde {"detalle", "campo"?} en las reglas de negocio y
 * {"<campo>": ["mensaje"]} en la validación de formato de DRF.
 */
export function leerError(e: unknown): { error: string; campo?: string } {
  if (!isAxiosError(e) || !e.response) return { error: "No hay conexión con la plataforma. Intenta de nuevo en un momento." };
  if (e.response.status === 429) return { error: "Hiciste demasiados intentos seguidos. Espera un minuto y vuelve a intentarlo." };
  const d = e.response.data as Record<string, unknown> | undefined;
  if (d && typeof d.detalle === "string") return { error: d.detalle, campo: typeof d.campo === "string" ? d.campo : undefined };
  if (d && typeof d.detail === "string") return { error: d.detail };
  const [campo, valor] = Object.entries(d ?? {})[0] ?? [];
  if (campo) return { error: Array.isArray(valor) ? String(valor[0]) : String(valor), campo };
  return { error: "Ocurrió un error inesperado. Intenta de nuevo." };
}

/* ---------------- SRV-02 Catálogo: catálogos públicos ---------------- */

export interface ItemCatalogo { id: number; nombre: string }

export const catalogoApi = {
  ciudades: () => api.get<ItemCatalogo[]>("/catalogo/ciudades"),
  tipos: () => api.get<ItemCatalogo[]>("/catalogo/tipos-alojamiento"),
  servicios: () => api.get<ItemCatalogo[]>("/catalogo/servicios"),
};

/* ---------------- SRV-03 Búsqueda (pública) ---------------- */

export interface Calificacion { promedio: string | null; total: number }

export interface ResultadoBusqueda {
  id: number; titulo: string; ciudad_id: number; ciudad: string; tipo_alojamiento_id: number; tipo: string;
  capacidad: number; precio_noche: string; tarifa_limpieza: string; descuento_porcentaje: string | null;
  descuento_min_noches: number | null; servicios: number[]; imagen_principal: string | null; calificacion: Calificacion;
}

export interface Tramo { dias_minimos: number; dias_maximos: number | null; porcentaje_devolucion: string }

export interface DetallePublico {
  id: number; titulo: string; descripcion: string; anfitrion: number; anfitrion_nombre: string | null;
  ciudad: string; ubicacion_textual: string; tipo: string; capacidad: number; precio_noche: string; tarifa_limpieza: string;
  descuento_porcentaje: string | null; descuento_min_noches: number | null;
  servicios: ItemCatalogo[]; servicios_adicionales: { id: number; nombre: string; precio: string }[];
  reglas: { descripcion: string; orden: number }[]; imagenes: { ruta: string; orden: number }[];
  politica: { id: number; nombre: string; descripcion: string | null; tramos: Tramo[] } | null;
  calificacion: Calificacion; disponibilidad: { desde: string; hasta: string; noches_no_disponibles: string[] };
}

export interface FiltrosBusqueda {
  ciudad?: number; llegada?: string; salida?: string; huespedes?: number; tipo?: number;
  precio_min?: number; precio_max?: number; servicios?: number[];
}

export const busquedaApi = {
  buscar: (f: FiltrosBusqueda) => {
    const params: Record<string, string> = {};
    Object.entries(f).forEach(([k, v]) => {
      if (v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) return;
      params[k] = Array.isArray(v) ? v.join(",") : String(v);
    });
    return api.get<ResultadoBusqueda[]>("/busqueda/publicaciones", { params });
  },
  detalle: (id: number, desde?: string, hasta?: string) =>
    api.get<DetallePublico>(`/busqueda/publicaciones/${id}`, { params: { desde, hasta } }),
};

/* ---------------- SRV-04 Reservas: cotizar y reservar (HU-12, HU-13) ---------------- */

export interface CotizacionApi {
  id: number; publicacion: number; publicacion_titulo: string | null; fecha_llegada: string; fecha_salida: string;
  num_huespedes: number; noches: number; precio_noche: string; precio_base: string; descuento: string;
  tarifa_limpieza: string; porcentaje_servicio: string; tarifa_servicio: string;
  adicionales: { id: number; nombre: string | null; precio_aplicado: string }[]; total_adicionales: string; total: string;
  creada: string; vence: string; vencida: boolean; reserva: number | null;
}

export interface ReservaApi {
  id: number; estado: string; cotizacion: number; publicacion: number; fecha_llegada: string; fecha_salida: string;
  num_huespedes: number; total: string; clave_idempotencia: string;
  pagos: { id: number; tipo: string; monto: string; estado: string; referencia_externa: string | null }[];
}

export const reservasApi = {
  cotizar: (d: { publicacion: number; fecha_llegada: string; fecha_salida: string; num_huespedes: number; adicionales: number[] }) =>
    api.post<CotizacionApi>("/reservas/cotizaciones", d),
  cotizacion: (id: number) => api.get<CotizacionApi>(`/reservas/cotizaciones/${id}`),
  reservar: (d: { cotizacion: number; clave_idempotencia: string; medio_pago: string }) => api.post<ReservaApi>("/reservas", d),
};
