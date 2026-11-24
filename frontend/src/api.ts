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
 * - Si una petición responde 401 porque el access venció, se renueva una vez y se repite. Si no se
 *   puede renovar, la sesión se cierra y la aplicación lleva a "Ingresar" (HU-02).
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

/** Guarda el token de acceso en memoria (nunca en localStorage, ADR-005). Con null se olvida al cerrar sesión. */
export function guardarTokenAcceso(token: string | null) {
  tokenAcceso = token;
}

/** La sesión registra aquí qué hacer cuando ya no se puede renovar. */
export function cuandoSePierdaLaSesion(accion: () => void) {
  alPerderSesion = accion;
}

api.interceptors.request.use((config) => {
  if (tokenAcceso) config.headers.Authorization = `Bearer ${tokenAcceso}`;
  return config;
});

// Rutas que no se reintentan: las de sesión, y las públicas que se piden también sin sesión.
const RUTAS_DE_SESION = ["/identidad/token", "/identidad/salir", "/identidad/permisos"];

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const original = error.config as (InternalAxiosRequestConfig & { _reintentada?: boolean }) | undefined;
  const esRutaDeSesion = RUTAS_DE_SESION.some((ruta) => original?.url?.startsWith(ruta));
  if (error.response?.status !== 401 || !original || original._reintentada || esRutaDeSesion) throw error;

  original._reintentada = true;
  const nuevo = (await renovarSesion())?.access ?? null;
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

let renovacionEnCurso: Promise<SesionApi | null> | null = null;

/**
 * Renueva la sesión con la cookie `renovacion`. Las llamadas simultáneas comparten una sola petición.
 *
 * El backend rota la cookie y pone la anterior en la lista negra (ADR-005), así que renovar no es
 * idempotente: si dos peticiones salen a la vez con la misma cookie, la primera gana y la segunda
 * recibe 401 y cierra la sesión. Pasa al recargar la página (React.StrictMode ejecuta dos veces el
 * efecto que recupera la sesión) y cuando varias peticiones vencen juntas.
 */
export function renovarSesion(): Promise<SesionApi | null> {
  renovacionEnCurso ??= api
    .post<SesionApi>("/identidad/token/renovar")
    .then(({ data }) => {
      guardarTokenAcceso(data.access);
      return data;
    })
    .catch(() => {
      guardarTokenAcceso(null);
      return null;
    })
    .finally(() => { renovacionEnCurso = null; });
  return renovacionEnCurso;
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
    api.post<{ detalle: string }>("/identidad/recuperacion", { correo }),
  estadoEnlace: (token: string) =>
    api.get<{ estado: "valido" | "vencido" | "usado" | "inexistente" }>(`/identidad/recuperacion/${encodeURIComponent(token)}`),
  restablecer: (token: string, password: string) =>
    api.post(`/identidad/recuperacion/${encodeURIComponent(token)}`, { password }),
  actualizarPerfil: (cambios: Record<string, string | null>) => api.patch<UsuarioApi>("/identidad/perfil", cambios),
  desactivar: () => api.post("/identidad/perfil/desactivar"),
  /** GET /identidad/permisos: rol y permisos de quien llama (sin sesión, los del VISITANTE). */
  permisos: () => api.get<{ rol: string; permisos: string[] }>("/identidad/permisos"),
  /** GET /identidad/roles: la matriz completa de rbac.PERMISOS (solo el Administrador, usuarios.ver). */
  roles: () => api.get<{ roles: { rol: string; permisos: string[] }[] }>("/identidad/roles"),
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

export interface PoliticaApi {
  id: number; nombre: string; descripcion: string | null;
  tramos: { dias_minimos: number; dias_maximos: number | null; porcentaje_devolucion: string }[];
}

export const catalogoApi = {
  // En orden alfabético en español en todos los selectores (Explorar con y sin sesión, publicación, reportes)
  ciudades: () => api.get<ItemCatalogo[]>("/catalogo/ciudades")
    .then((r) => ({ ...r, data: [...r.data].sort((a, b) => a.nombre.localeCompare(b.nombre, "es", { sensitivity: "base" })) })),
  tipos: () => api.get<ItemCatalogo[]>("/catalogo/tipos-alojamiento"),
  servicios: () => api.get<ItemCatalogo[]>("/catalogo/servicios"),
  politicas: () => api.get<PoliticaApi[]>("/catalogo/politicas"),
};

/** "7 días o más antes de la llegada" para un tramo de la política. */
export function textoTramo(t: PoliticaApi["tramos"][number]) {
  if (t.dias_maximos == null) return `${t.dias_minimos} días o más antes de la llegada`;
  if (t.dias_minimos === 0) return `Menos de ${t.dias_maximos + 1} días antes`;
  return `Entre ${t.dias_minimos} y ${t.dias_maximos} días antes`;
}

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

/* ---------------- SRV-04 Reservas: consultar, cancelar y revisar (HU-14, HU-15, HU-20, HU-26) ---------------- */

export interface CancelacionApi {
  fecha: string; motivo: string; cancelada_por: number | null; automatica: boolean;
  cancelada_por_rol: "HUESPED" | "ADMINISTRADOR" | "AUTOMATICA";
  dias_anticipacion: number; porcentaje_devolucion: string; valor_devolucion: string;
}

export interface ReservaResumen {
  id: number; estado: "CONFIRMADA" | "CANCELADA" | "COMPLETADA" | "EN_REVISION"; publicacion: number;
  alojamiento: string | null; portada: string | null; ciudad: string | null; anfitrion: number | null; huesped: number;
  huesped_nombre: string | null; fecha_llegada: string; fecha_salida: string; noches: number; num_huespedes: number;
  total: string; cancelable: boolean; cancelacion: CancelacionApi | null; creada: string;
  // Solo en las respuestas del Administrador (Reservas en revisión, RF-D-ADM-01.2)
  anfitrion_nombre?: string | null; dias_para_llegada?: number;
  bloqueo?: { motivo: string | null; fecha: string } | null;
  resolucion?: { resultado: "MANTENIDA" | "CANCELADA_ADMINISTRADOR" | "CANCELADA_AUTOMATICA"; por: string | null; fecha: string | null;
    motivo?: string | null; valor_devolucion?: string | null } | null;
}

export interface SimulacionCancelacion {
  reserva: number; cancelable: boolean; dias_anticipacion: number; porcentaje_devolucion: string; valor_devolucion: string;
}

/** GET /reservas/{id}: el resumen más el desglose y la política guardados al reservar (MAL-34). */
export interface ReservaDetalleApi extends ReservaResumen {
  anfitrion_nombre: string | null;
  desglose: Omit<CotizacionApi, "id" | "publicacion" | "publicacion_titulo" | "fecha_llegada" | "fecha_salida" | "num_huespedes" | "creada" | "vence" | "vencida" | "reserva">;
  politica_cancelacion: { id: number; nombre: string; descripcion: string | null;
    tramos: { dias_minimos: number; dias_maximos: number | null; porcentaje_devolucion: string }[] } | null;
  devolucion_hoy: Omit<SimulacionCancelacion, "reserva"> | null;
  pagos: ReservaApi["pagos"];
}

export const misReservasApi = {
  mias: () => api.get<ReservaResumen[]>("/reservas/mias"),
  deMisAlojamientos: () => api.get<ReservaResumen[]>("/reservas/de-mis-alojamientos"),
  detalle: (id: number) => api.get<ReservaDetalleApi>(`/reservas/${id}`),
  simularCancelacion: (id: number) => api.get<SimulacionCancelacion>(`/reservas/${id}/cancelar`),
  cancelar: (id: number, motivo: string) => api.post<ReservaResumen>(`/reservas/${id}/cancelar`, { motivo }),
  enRevision: () => api.get<ReservaResumen[]>("/admin/reservas", { params: { estado: "EN_REVISION" } }),
  resueltas: () => api.get<ReservaResumen[]>("/admin/reservas/resueltas"),
  detalleAdmin: (id: number) => api.get<ReservaDetalleApi>(`/admin/reservas/${id}`),
  resolver: (id: number, mantener: boolean, motivo?: string) =>
    api.post<ReservaResumen>(`/admin/reservas/${id}/resolver`, { mantener, ...(motivo ? { motivo } : {}) }),
};

/* ---------------- SRV-07 Notificaciones (HU-16) ---------------- */

export interface NotificacionApi {
  id: number; tipo: string; mensaje: string; entidad: string | null; entidad_id: number | null; leida: boolean; fecha: string;
}

export const notificacionesApi = {
  bandeja: () => api.get<{ no_leidas: number; notificaciones: NotificacionApi[] }>("/notificaciones"),
  marcarLeida: (id: number) => api.post<NotificacionApi>(`/notificaciones/${id}/leida`),
  marcarTodas: () => api.post<{ marcadas: number }>("/notificaciones/leidas"),
};

/* ---------------- Administración (MOD-09 y moderación, HU-19 a HU-25) ---------------- */

export interface RevisionApi {
  accion: "APROBAR" | "DEVOLVER" | "PAUSAR" | "REACTIVAR" | "BLOQUEAR" | "DESBLOQUEAR"; observacion: string | null; fecha: string;
  administrador?: number; administrador_nombre?: string;
}

export interface PublicacionAdmin {
  id: number; anfitrion: number; titulo: string; ciudad: number | null; ciudad_nombre: string | null;
  tipo_alojamiento: number | null; tipo_nombre: string | null; precio_noche: string | null;
  estado: "BORRADOR" | "PENDIENTE_REVISION" | "ACTIVA" | "PAUSADA" | "BLOQUEADA"; actualizada: string;
  imagen: string | null; ultima_revision: RevisionApi | null;
}

export interface PublicacionCompleta extends Omit<PublicacionAdmin, "imagen" | "ultima_revision"> {
  descripcion: string; ubicacion_textual: string; capacidad: number | null; tarifa_limpieza: string | null;
  descuento_porcentaje: string | null; descuento_min_noches: number | null; politica: number | null; politica_nombre: string | null;
  servicios: ItemCatalogo[]; servicios_adicionales: { id: number; nombre: string; precio: string }[];
  reglas: { descripcion: string; orden: number }[]; imagenes: { ruta: string; orden: number }[];
  revisiones: RevisionApi[]; faltantes: string[];
}

/** Lo que recibe POST y PATCH /catalogo/publicaciones (RF-D-ALO-01.1). */
export interface PublicacionEntrada {
  titulo: string; descripcion: string; ciudad: number | null; tipo_alojamiento: number | null; politica: number | null;
  ubicacion_textual: string; capacidad: number | null; precio_noche: number | null; tarifa_limpieza: number | null;
  descuento_porcentaje: number | null; descuento_min_noches: number | null; servicios: number[];
  servicios_adicionales: { nombre: string; precio: number }[]; reglas: string[]; imagenes: string[];
}

export interface CalendarioApi {
  publicacion: number;
  periodos: { fecha_inicio: string; fecha_fin: string; disponible: boolean; tipo: string }[];
  noches_reservadas: string[];
}

/* ---------------- SRV-02 Catálogo: publicaciones del anfitrión (HU-06 a HU-10) ---------------- */
export const anfitrionApi = {
  mias: () => todas<PublicacionAdmin>("/catalogo/mis-publicaciones", {}),
  publicacion: (id: number) => api.get<PublicacionCompleta>(`/catalogo/publicaciones/${id}`),
  crear: (d: PublicacionEntrada) => api.post<PublicacionCompleta>("/catalogo/publicaciones", d),
  actualizar: (id: number, d: Partial<PublicacionEntrada>) => api.patch<PublicacionCompleta>(`/catalogo/publicaciones/${id}`, d),
  enviarRevision: (id: number) => api.post<PublicacionCompleta>(`/catalogo/publicaciones/${id}/enviar-revision`),
  pausar: (id: number) => api.post<PublicacionCompleta>(`/catalogo/publicaciones/${id}/pausar`),
  reactivar: (id: number) => api.post<PublicacionCompleta>(`/catalogo/publicaciones/${id}/reactivar`),
  /** Solo BORRADOR y solo el anfitrión dueño. */
  eliminarBorrador: (id: number) => api.delete(`/catalogo/mis-publicaciones/${id}`),
  /** RF-D-ALO-02.2: la ruta se conserva en Catálogo, pero la atiende Reservas. */
  calendario: (id: number, desde: string, hasta: string) =>
    api.get<CalendarioApi>(`/catalogo/publicaciones/${id}/calendario`, { params: { desde, hasta } }),
  /** fecha_fin es exclusiva: el rango cubre las noches de fecha_inicio a fecha_fin - 1. */
  modificarCalendario: (id: number, fecha_inicio: string, fecha_fin: string, tipo: "DISPONIBLE" | "NO_DISPONIBLE") =>
    api.post<CalendarioApi>(`/catalogo/publicaciones/${id}/calendario`, { fecha_inicio, fecha_fin, tipo }),
};

export interface UsuarioAdmin extends UsuarioApi { motivo_restriccion: string | null; restriccion_hasta: string | null }

export interface EventoAuditoriaApi {
  id: number; fecha: string; actor_id: number | null; actor_nombre: string | null; actor_correo: string | null; actor_rol: string | null;
  accion: string; entidad: string | null; entidad_id: number | null; exitoso: boolean; detalle: Record<string, unknown> | null; ip: string | null;
}

export interface TableroApi {
  desde: string; hasta: string; usuarios_por_rol: Record<string, number>; publicaciones_activas: number;
  reservas_por_estado: Record<string, number>; reservas_total: number; ingresos: { bruto: string; plataforma: string };
  top_ciudades: { ciudad: string; reservas: number; monto_bruto: string }[];
  /** Solo los días con reservas (fecha de creación, hora de Colombia). */
  serie_diaria: { fecha: string; reservas: number; monto_bruto: string; ingreso_plataforma: string }[];
}

type Pagina<T> = { count: number; next: string | null; previous: string | null; results: T[] };

/** Recorre todas las páginas de una lista paginada de DRF. */
async function todas<T>(ruta: string, params: Record<string, unknown>): Promise<T[]> {
  const salida: T[] = [];
  for (let page = 1; ; page++) {
    const { data } = await api.get<Pagina<T>>(ruta, { params: { ...params, page } });
    salida.push(...data.results);
    if (!data.next) return salida;
  }
}

/** Una tarifa rige en [vigente_desde, vigente_hasta). La base (programada false) puede no tener fin; una programada
 *  reemplaza a la base en su rango. estado: la que se cobra ahora (VIGENTE), futura (PROGRAMADA), pasada (TERMINADA)
 *  o la base mientras una programada la reemplaza (EN_ESPERA). */
export interface TarifaApi {
  id: number; porcentaje: string; vigente_desde: string; vigente_hasta: string | null; programada: boolean;
  estado: "VIGENTE" | "PROGRAMADA" | "TERMINADA" | "EN_ESPERA"; administrador: number;
}

export const adminApi = {
  publicaciones: (estado?: string) => todas<PublicacionAdmin>("/admin/publicaciones", estado ? { estado } : {}),
  publicacion: (id: number) => api.get<PublicacionCompleta>(`/catalogo/publicaciones/${id}`),
  revisar: (id: number, accion: "APROBAR" | "DEVOLVER", observacion?: string) =>
    api.post<PublicacionCompleta>(`/admin/publicaciones/${id}/revision`, { accion, observacion }),
  bloquear: (id: number, motivo: string) => api.post<PublicacionCompleta>(`/admin/publicaciones/${id}/bloqueo`, { motivo }),
  desbloquear: (id: number) => api.delete<PublicacionCompleta>(`/admin/publicaciones/${id}/bloqueo`),
  pausar: (id: number) => api.post<PublicacionCompleta>(`/catalogo/publicaciones/${id}/pausar`),
  reactivar: (id: number) => api.post<PublicacionCompleta>(`/catalogo/publicaciones/${id}/reactivar`),
  usuarios: (rol?: string, q?: string) => api.get<UsuarioAdmin[]>("/admin/usuarios", { params: { rol: rol || undefined, q: q || undefined } }),
  restringir: (id: number, motivo: string, fecha_fin?: string | null) =>
    api.post(`/admin/usuarios/${id}/restriccion`, { motivo, ...(fecha_fin ? { fecha_fin } : {}) }),
  quitarRestriccion: (id: number) => api.delete(`/admin/usuarios/${id}/restriccion`),
  /** RF-D-ADM-03.1: con desde y hasta, el historial trae solo las tarifas vigentes en ese rango. */
  tarifa: (desde?: string, hasta?: string) =>
    api.get<{ porcentaje: string; base: string | null; historial: TarifaApi[] }>("/admin/tarifa-servicio", { params: { desde: desde || undefined, hasta: hasta || undefined } }),
  cambiarTarifa: (porcentaje: string) => api.put<TarifaApi>("/admin/tarifa-servicio", { porcentaje }),
  /** Tarifa para un rango de días (ambos incluidos) que reemplaza a la base en esas fechas. */
  programarTarifa: (porcentaje: string, desde: string, hasta: string) =>
    api.post<TarifaApi>("/admin/tarifa-servicio/programadas", { porcentaje, desde, hasta }),
  /** Solo antes de que empiece a regir. */
  cancelarTarifaProgramada: (id: number) => api.delete(`/admin/tarifa-servicio/programadas/${id}`),
  auditoria: (f: { usuario?: number; tipo?: string; desde?: string; hasta?: string; page?: number }) =>
    api.get<Pagina<EventoAuditoriaApi> & { tipos: { clave: string; nombre: string }[] }>("/admin/auditoria", { params: f }),
  tablero: (desde: string, hasta: string) => api.get<TableroApi>("/admin/tablero", { params: { desde, hasta } }),
  /** RF-D-ADM-05.2: el servidor genera el archivo (ADR-009). Devuelve el blob y el nombre de Content-Disposition. */
  async reporte(tipo: string, params: Record<string, string | undefined>) {
    try {
      const r = await api.get<Blob>(`/admin/reportes/${tipo}`, { params, responseType: "blob" });
      const disp = String(r.headers["content-disposition"] ?? "");
      const nombre = /filename="?([^";]+)"?/.exec(disp)?.[1] ?? `reporte-${tipo}.${params.formato ?? "pdf"}`;
      return { blob: r.data, nombre };
    } catch (e) {
      // Con responseType blob, el error JSON de la API también llega como Blob: se lee para mostrar el detalle
      if (isAxiosError(e) && e.response?.data instanceof Blob) {
        try { e.response.data = JSON.parse(await e.response.data.text()); } catch { /* no era JSON */ }
      }
      throw e;
    }
  },
};
