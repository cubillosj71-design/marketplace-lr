// Tipos, textos y formatos de la interfaz. Los datos vienen todos de la API (/api/v1).

export type Rol = "HUESPED" | "ANFITRION" | "ADMINISTRADOR";
export type EstadoPub = "BORRADOR" | "PENDIENTE_REVISION" | "ACTIVA" | "PAUSADA" | "BLOQUEADA";
export type AccionModeracion = "APROBAR" | "DEVOLVER" | "PAUSAR" | "REACTIVAR" | "BLOQUEAR" | "DESBLOQUEAR";

/** Imagen para mostrar: la ruta (URL) que guarda la API, o un color de relleno si no hay ruta. */
export interface Imagen { id: string; color: string; nombre: string; src?: string }

/** Nombres para mostrar. El acceso nunca se decide con el rol, sino con los permisos (apps/comun/rbac.py). */
export const ROL_TXT: Record<string, string> = {
  VISITANTE: "Visitante", HUESPED: "Huésped", ANFITRION: "Anfitrión", ADMINISTRADOR: "Administrador",
};
export const ESTADO_TXT: Record<EstadoPub, string> = {
  BORRADOR: "Borrador",
  PENDIENTE_REVISION: "En revisión",
  ACTIVA: "Activa",
  PAUSADA: "Pausada",
  BLOQUEADA: "Bloqueada",
};
/** Estados de una reserva como los lee el cliente (el código interno no se muestra). */
export const RESERVA_TXT: Record<string, string> = {
  CONFIRMADA: "Confirmada", CANCELADA: "Cancelada", COMPLETADA: "Completada", EN_REVISION: "En revisión",
};

/** Descripción de cada permiso de la matriz (mismo nombre que en el backend). */
export const PERMISO_TXT: Record<string, string> = {
  "busqueda.ver": "Buscar alojamientos y ver su detalle",
  "cuenta.registrar": "Registrarse",
  "catalogo.ver": "Consultar ciudades, tipos, servicios y políticas",
  "reservas.cotizar": "Cotizar una estancia",
  "reservas.crear": "Reservar y pagar",
  "reservas.ver_propias": "Consultar sus reservas",
  "reservas.cancelar_propia": "Cancelar sus reservas",
  "perfil.gestionar": "Actualizar su perfil y su contraseña",
  "cuenta.desactivar": "Desactivar su cuenta",
  "notificaciones.ver": "Ver sus notificaciones",
  "publicaciones.gestionar_propias": "Crear, editar, enviar a revisión, pausar y reactivar sus publicaciones",
  "calendario.gestionar": "Administrar el calendario de sus alojamientos",
  "reservas.ver_de_mis_alojamientos": "Consultar las reservas de sus alojamientos",
  "publicaciones.moderar": "Aprobar, devolver, bloquear y modificar cualquier publicación",
  "reservas.resolver": "Resolver reservas EN_REVISION",
  "usuarios.ver": "Consultar las cuentas de usuario",
  "usuarios.restringir": "Restringir cuentas y quitar la restricción",
  "tarifa.configurar": "Configurar la tarifa de servicio",
  "auditoria.consultar": "Consultar el registro de acciones",
  "tablero.ver": "Ver el tablero",
  "reportes.descargar": "Descargar reportes (PDF o Excel)",
};

export const PALETA = [
  "linear-gradient(135deg,#2d7f74,#8fd3c4)",
  "linear-gradient(135deg,#c2410c,#f5a97f)",
  "linear-gradient(135deg,#1e4e8c,#93b8e8)",
  "linear-gradient(135deg,#6d5a2c,#e2c98c)",
  "linear-gradient(135deg,#4c2e6b,#c3a6e3)",
  "linear-gradient(135deg,#0e3b39,#4fa394)",
];

/** Imagen de pantalla a partir de la ruta que guarda la API. */
export const imagenDe = (ruta: string | null | undefined, i = 0, nombre = ""): Imagen =>
  ({ id: `${i}-${ruta ?? ""}`, nombre, color: PALETA[i % PALETA.length]!, src: ruta ?? undefined });

// ---------- formatos ----------
export const cop = (n: number | string | null | undefined) =>
  n == null || n === "" ? "—" : "$" + Math.round(Number(n)).toLocaleString("es-CO").replace(/,/g, ".");

export const iniciales = (nombre: string) =>
  nombre.split(" ").filter(Boolean).slice(0, 2).map((s) => s[0]!.toUpperCase()).join("");

export function isoDia(d: Date) {
  const z = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

/** "2026-12-05" -> "5 dic" */
export const fechaLarga = (iso: string) =>
  new Date(iso.slice(0, 10) + "T12:00:00").toLocaleDateString("es-CO", { day: "numeric", month: "short" }).replace(".", "");
