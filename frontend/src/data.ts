// Tipos y datos de ejemplo del prototipo (sin backend).
// Los nombres de estados y reglas siguen el SRS v3.5 y el modelo de datos de la fase de diseño.

export type Rol = "HUESPED" | "ANFITRION" | "ADMINISTRADOR";
/** Estado de la cuenta solo para mostrar: no es una columna, se deriva de `activa` y de una restricción vigente. */
export type EstadoCuenta = "ACTIVA" | "DESACTIVADA" | "RESTRINGIDA";
export type EstadoPub = "BORRADOR" | "PENDIENTE_REVISION" | "ACTIVA" | "PAUSADA" | "BLOQUEADA";
export type TipoAlojamiento = "Apartamento" | "Casa" | "Habitación" | "Cabaña";

export interface Usuario {
  id: number;
  nombre: string;
  correo: string;
  telefono: string;
  ciudad: string | null; // texto opcional (usuario.ciudad VARCHAR(80))
  rol: Rol;
  activa: boolean; // false solo si el usuario desactivó su cuenta
  restringida: boolean; // derivado de una RestriccionUsuario vigente
  clave: string;
  autorizacionDatos: string; // fecha y hora en que autorizó el tratamiento de datos (Ley 1581)
  fechaRegistro: string; // AAAA-MM-DD
}

export const estadoCuenta = (u: Pick<Usuario, "activa" | "restringida">): EstadoCuenta =>
  u.restringida ? "RESTRINGIDA" : u.activa ? "ACTIVA" : "DESACTIVADA";

/** RestriccionUsuario del diagrama de clases: la impone el Administrador. */
export interface RestriccionUsuario { id: number; usuarioId: number; motivo: string; fechaInicio: string; fechaFin?: string }

/** RevisionPublicacion: historial de moderación de cada publicación. */
export type AccionModeracion = "APROBAR" | "DEVOLVER" | "PAUSAR" | "REACTIVAR" | "BLOQUEAR" | "DESBLOQUEAR";
export interface RevisionPublicacion { id: number; publicacionId: number; adminId: number; accion: AccionModeracion; observacion?: string; fecha: string }

/** TarifaServicio: historial del porcentaje que cobra la plataforma (0 % a 30 %, RF-D-ADM-03.1). */
export interface TarifaServicio { porcentaje: number; vigenteDesde: string }

/** ReglaAlojamiento: cada regla es un registro con su orden. */
export interface ReglaAlojamiento { descripcion: string; orden: number }

export interface Adicional { nombre: string; precio: number }
export interface Imagen { id: string; color: string; nombre: string; src?: string }

export interface Publicacion {
  id: number;
  anfitrionId: number;
  titulo: string;
  descripcion: string;
  tipo: TipoAlojamiento | "";
  ciudad: string;
  ubicacion: string;
  capacidad: number | null;
  precioNoche: number | null;
  limpieza: number | null;
  descuentoPct: number | null;
  descuentoNoches: number | null;
  servicios: string[];
  adicionales: Adicional[];
  reglas: ReglaAlojamiento[];
  imagenes: Imagen[];
  politica: "Moderada" | "";
  estado: EstadoPub;
  bloqueos: string[]; // fechas AAAA-MM-DD marcadas como no disponibles por el anfitrión
  actualizada: string;
  creada?: string; // fecha de creación AAAA-MM-DD
}

export interface Reserva {
  id: number;
  publicacionId: number;
  huespedId: number;
  llegada: string; // ocupa desde la llegada hasta la noche anterior a la salida
  salida: string;
  numHuespedes: number;
  estado: "CONFIRMADA" | "CANCELADA" | "COMPLETADA" | "EN_REVISION";
  creada: string; // AAAA-MM-DD
  // Valores fijados al confirmar: un cambio posterior de la tarifa no los altera (CA-22.1)
  tarifaServicio: number;
  total: number;
}

export interface TokenRecuperacion { token: string; correo: string; creado: number; usado: boolean }

export const ROL_TXT: Record<Rol, string> = { HUESPED: "Huésped", ANFITRION: "Anfitrión", ADMINISTRADOR: "Administrador" };
export const ESTADO_TXT: Record<EstadoPub, string> = {
  BORRADOR: "Borrador",
  PENDIENTE_REVISION: "En revisión",
  ACTIVA: "Activa",
  PAUSADA: "Pausada",
  BLOQUEADA: "Bloqueada",
};

export const CIUDADES = ["Bogotá", "Medellín", "Cartagena", "Santa Marta", "Cali", "Guatapé", "Guatavita", "Villa de Leyva", "La Ceja"];
export const TIPOS: TipoAlojamiento[] = ["Apartamento", "Casa", "Habitación", "Cabaña"];
export const SERVICIOS = ["Wi-Fi", "Parqueadero", "Cocina", "TV", "Agua caliente", "Aire acondicionado", "Piscina", "Lavadora"];
export const POLITICA_MODERADA = [
  { tramo: "7 días o más antes de la llegada", devolucion: "100 %" },
  { tramo: "Entre 2 y 6 días antes", devolucion: "50 %" },
  { tramo: "Menos de 2 días antes", devolucion: "0 %" },
];
export const PALETA = [
  "linear-gradient(135deg,#2d7f74,#8fd3c4)",
  "linear-gradient(135deg,#c2410c,#f5a97f)",
  "linear-gradient(135deg,#1e4e8c,#93b8e8)",
  "linear-gradient(135deg,#6d5a2c,#e2c98c)",
  "linear-gradient(135deg,#4c2e6b,#c3a6e3)",
  "linear-gradient(135deg,#0e3b39,#4fa394)",
];

const img = (n: number, nombres: string[]): Imagen[] =>
  nombres.map((nombre, i) => ({ id: `i${n}-${i}`, nombre, color: PALETA[(n + i) % PALETA.length] }));

export const SEED_USUARIOS: Usuario[] = [
  { id: 1, nombre: "Laura Gómez", correo: "anfitrion@correo.com", telefono: "310 555 0182", ciudad: "Bogotá", rol: "ANFITRION", activa: true, restringida: false, clave: "Clave1234", fechaRegistro: "2026-03-14", autorizacionDatos: "2026-03-14T10:00:00" },
  { id: 2, nombre: "Carlos Ruiz", correo: "huesped@correo.com", telefono: "315 222 4410", ciudad: "Medellín", rol: "HUESPED", activa: true, restringida: false, clave: "Clave1234", fechaRegistro: "2026-05-02", autorizacionDatos: "2026-05-02T10:00:00" },
  { id: 3, nombre: "Admin LR", correo: "admin@inversioneslr.com", telefono: "601 555 0100", ciudad: "Bogotá", rol: "ADMINISTRADOR", activa: true, restringida: false, clave: "Clave1234", fechaRegistro: "2026-01-10", autorizacionDatos: "2026-01-10T10:00:00" },
  { id: 4, nombre: "Pedro Lara", correo: "pedro@correo.com", telefono: "300 410 7788", ciudad: "Bogotá", rol: "ANFITRION", activa: true, restringida: false, clave: "Clave1234", fechaRegistro: "2026-07-21", autorizacionDatos: "2026-07-21T10:00:00" },
  { id: 5, nombre: "Sofía Mejía", correo: "sofia@correo.com", telefono: "320 118 9034", ciudad: "Medellín", rol: "ANFITRION", activa: true, restringida: false, clave: "Clave1234", fechaRegistro: "2026-09-08", autorizacionDatos: "2026-09-08T10:00:00" },
  { id: 6, nombre: "Andrés Silva", correo: "restringido@correo.com", telefono: "311 902 3321", ciudad: "Bogotá", rol: "ANFITRION", activa: true, restringida: true, clave: "Clave1234", fechaRegistro: "2026-10-27", autorizacionDatos: "2026-10-27T10:00:00" },
];

const reglas = (...r: string[]): ReglaAlojamiento[] => r.map((descripcion, i) => ({ descripcion, orden: i + 1 }));

const base = (p: Partial<Publicacion> & Pick<Publicacion, "id" | "anfitrionId" | "titulo" | "estado">): Publicacion => ({
  descripcion: "",
  tipo: "",
  ciudad: "",
  ubicacion: "",
  capacidad: null,
  precioNoche: null,
  limpieza: null,
  descuentoPct: null,
  descuentoNoches: null,
  servicios: [],
  adicionales: [],
  reglas: [],
  imagenes: [],
  politica: "Moderada",
  bloqueos: [],
  actualizada: "2026-11-10",
  ...p,
});

export const SEED_PUBLICACIONES: Publicacion[] = [
  base({
    id: 101, creada: "2026-04-02", anfitrionId: 1, estado: "ACTIVA",
    titulo: "Apartamento con vista a Monserrate", tipo: "Apartamento", ciudad: "Bogotá",
    ubicacion: "La Candelaria, a 3 cuadras del Chorro de Quevedo",
    descripcion: "Apartamento luminoso de dos habitaciones con vista a los cerros, cocina equipada y balcón.",
    capacidad: 4, precioNoche: 220000, limpieza: 50000, descuentoPct: 10, descuentoNoches: 7,
    servicios: ["Wi-Fi", "Parqueadero", "Cocina", "Agua caliente"],
    adicionales: [{ nombre: "Desayuno", precio: 25000 }, { nombre: "Traslado al aeropuerto", precio: 70000 }],
    reglas: reglas("No fumar", "Sin fiestas", "Silencio después de las 10 p. m."),
    imagenes: img(1, ["Sala", "Habitación", "Vista"]),
    bloqueos: ["2026-12-12", "2026-12-13", "2026-12-14"],
  }),
  base({
    id: 102, creada: "2026-05-18", anfitrionId: 1, estado: "PAUSADA",
    titulo: "Cabaña El Roble", tipo: "Cabaña", ciudad: "Guatavita", ubicacion: "Vereda El Roble, km 4",
    descripcion: "Cabaña de madera junto al embalse, con chimenea y zona de fogata.",
    capacidad: 5, precioNoche: 310000, limpieza: 60000,
    servicios: ["Wi-Fi", "Parqueadero", "Cocina"], reglas: reglas("Mascotas pequeñas permitidas"),
    imagenes: img(2, ["Fachada", "Chimenea"]),
  }),
  base({
    id: 103, creada: "2026-06-30", anfitrionId: 1, estado: "PENDIENTE_REVISION",
    titulo: "Habitación cerca al centro", tipo: "Habitación", ciudad: "Bogotá", ubicacion: "Calle 19 con carrera 4",
    descripcion: "Habitación privada con baño, a 10 minutos del centro histórico. Incluye Wi-Fi y agua caliente.",
    capacidad: 2, precioNoche: 95000, limpieza: 20000,
    servicios: ["Wi-Fi", "Agua caliente"], reglas: reglas("Llegada desde las 3:00 p. m."),
    imagenes: img(3, ["Habitación", "Baño", "Escritorio", "Edificio"]),
  }),
  base({
    id: 104, creada: "2026-08-12", anfitrionId: 1, estado: "BORRADOR",
    titulo: "Casa familiar en Villa de Leyva", tipo: "Casa", ciudad: "Villa de Leyva",
    ubicacion: "Vereda El Roble, a 5 min de la plaza",
    descripcion: "Casa de dos pisos a 5 minutos de la plaza principal, con patio y zona BBQ.",
    capacidad: 6, limpieza: 60000, servicios: ["Wi-Fi", "Parqueadero", "Cocina"],
    adicionales: [{ nombre: "Desayuno", precio: 25000 }],
    reglas: reglas("No fumar", "Mascotas pequeñas permitidas"), politica: "",
  }),
  base({
    id: 105, creada: "2026-10-05", anfitrionId: 1, estado: "BLOQUEADA",
    titulo: "Loft Chapinero", tipo: "Apartamento", ciudad: "Bogotá", ubicacion: "Chapinero Alto",
    descripcion: "Loft moderno con terraza.", capacidad: 2, precioNoche: 180000, limpieza: 40000,
    servicios: ["Wi-Fi", "TV"], imagenes: img(5, ["Loft"]),
  }),
  base({
    id: 201, creada: "2026-08-01", anfitrionId: 4, estado: "PENDIENTE_REVISION",
    titulo: "Estudio Usaquén", tipo: "Apartamento", ciudad: "Bogotá", ubicacion: "Usaquén, cerca del parque",
    descripcion: "Estudio para dos con cocineta.", capacidad: 2, precioNoche: 150000, limpieza: 30000,
    servicios: ["Wi-Fi", "Cocina"], imagenes: img(6, ["Estudio", "Cocineta"]),
  }),
  base({
    id: 301, creada: "2026-09-15", anfitrionId: 5, estado: "ACTIVA",
    titulo: "Cabaña del Lago", tipo: "Cabaña", ciudad: "Guatapé", ubicacion: "Orilla del embalse, sector La Piedra",
    descripcion: "Cabaña con muelle propio y kayak.", capacidad: 5, precioNoche: 280000, limpieza: 60000,
    servicios: ["Wi-Fi", "Parqueadero", "Cocina"], imagenes: img(7, ["Muelle", "Sala"]),
  }),
  base({
    id: 302, creada: "2026-10-01", anfitrionId: 5, estado: "ACTIVA",
    titulo: "Casa campestre La Ceja", tipo: "Casa", ciudad: "La Ceja", ubicacion: "Vía La Ceja – La Unión, km 2",
    descripcion: "Casa campestre con jardín amplio y BBQ.", capacidad: 8, precioNoche: 390000, limpieza: 80000,
    servicios: ["Wi-Fi", "Parqueadero", "Cocina", "Piscina"], imagenes: img(8, ["Jardín", "Piscina"]),
  }),
  base({
    id: 303, creada: "2026-11-03", anfitrionId: 5, estado: "ACTIVA",
    titulo: "Habitación Laureles", tipo: "Habitación", ciudad: "Medellín", ubicacion: "Laureles, circular 1",
    descripcion: "Habitación privada en casa familiar.", capacidad: 2, precioNoche: 110000, limpieza: 20000,
    servicios: ["Wi-Fi", "Agua caliente"], imagenes: img(9, ["Habitación"]),
  }),
  base({
    id: 304, creada: "2026-10-28", anfitrionId: 6, estado: "ACTIVA",
    titulo: "Apartamento El Poblado", tipo: "Apartamento", ciudad: "Medellín", ubicacion: "El Poblado",
    descripcion: "No aparece en búsquedas porque la cuenta del anfitrión está restringida.",
    capacidad: 3, precioNoche: 240000, limpieza: 40000, servicios: ["Wi-Fi"], imagenes: img(10, ["Sala"]),
  }),
];

export const SEED_TARIFAS: TarifaServicio[] = [{ porcentaje: 10, vigenteDesde: "2026-01-01T00:00:00" }];

export const SEED_RESTRICCIONES: RestriccionUsuario[] = [
  { id: 1, usuarioId: 6, motivo: "Reportes de huéspedes por cobros por fuera de la plataforma.", fechaInicio: "2026-11-02T09:00:00", fechaFin: "2026-12-31T23:59:00" },
];

const rev = (id: number, publicacionId: number, accion: AccionModeracion, fecha: string, observacion?: string): RevisionPublicacion =>
  ({ id, publicacionId, adminId: 3, accion, fecha, observacion });
export const SEED_REVISIONES: RevisionPublicacion[] = [
  rev(1, 101, "APROBAR", "2026-04-03T09:12:00"),
  rev(2, 102, "APROBAR", "2026-05-19T15:40:00"),
  rev(3, 104, "DEVOLVER", "2026-08-14T11:05:00", "Las fotos no corresponden al alojamiento. Sube fotos reales de la casa."),
  rev(4, 105, "APROBAR", "2026-10-06T10:20:00"),
  rev(5, 105, "BLOQUEAR", "2026-11-08T16:30:00", "La dirección publicada no coincide con la del alojamiento."),
  rev(6, 301, "APROBAR", "2026-09-16T08:50:00"),
  rev(7, 302, "APROBAR", "2026-10-02T14:15:00"),
  rev(8, 303, "APROBAR", "2026-11-04T09:30:00"),
  rev(9, 304, "APROBAR", "2026-10-29T17:00:00"),
];

/** Porcentaje vigente en una fecha, según el historial de TarifaServicio. */
export const tarifaVigente = (tarifas: TarifaServicio[], fecha: string): number => {
  const orden = [...tarifas].sort((a, b) => a.vigenteDesde.localeCompare(b.vigenteDesde));
  return (orden.filter((t) => t.vigenteDesde <= fecha).pop() ?? orden[0]).porcentaje;
};

/** Cotización (RF-D-RES, CA-12.1, CA-12.2): total = base - descuento + limpieza + tarifa de servicio. */
export const cotizar = (p: Publicacion, noches: number, pct: number) => {
  const precioBase = noches * (p.precioNoche ?? 0);
  const aplica = !!p.descuentoPct && !!p.descuentoNoches && noches >= p.descuentoNoches;
  const descuento = aplica ? Math.round(precioBase * p.descuentoPct! / 100) : 0;
  const limpieza = p.limpieza ?? 0;
  const tarifaServicio = Math.round((precioBase - descuento) * pct / 100);
  return { precioBase, descuento, limpieza, tarifaServicio, total: precioBase - descuento + limpieza + tarifaServicio };
};

const reserva = (id: number, publicacionId: number, llegada: string, salida: string, numHuespedes: number, creada: string): Reserva => {
  const p = SEED_PUBLICACIONES.find((x) => x.id === publicacionId)!;
  const base: Omit<Reserva, "tarifaServicio" | "total"> = { id, publicacionId, huespedId: 2, llegada, salida, numHuespedes, estado: "CONFIRMADA", creada };
  const c = cotizar(p, nochesReserva(base).length, tarifaVigente(SEED_TARIFAS, creada));
  return { ...base, tarifaServicio: c.tarifaServicio, total: c.total };
};

export const SEED_RESERVAS: Reserva[] = [
  reserva(9001, 101, "2026-11-20", "2026-11-23", 2, "2026-10-25"),
  reserva(9002, 101, "2026-12-05", "2026-12-09", 3, "2026-11-01"),
  reserva(9003, 301, "2026-12-20", "2026-12-22", 2, "2026-11-10"),
];

// ---------- utilidades ----------
export const cop = (n: number | null | undefined) =>
  n == null ? "—" : "$" + Math.round(n).toLocaleString("es-CO").replace(/,/g, ".");

export const iniciales = (nombre: string) =>
  nombre.split(" ").filter(Boolean).slice(0, 2).map((s) => s[0]!.toUpperCase()).join("");

export function isoDia(d: Date) {
  const z = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

/** Noches ocupadas por una reserva: desde la llegada hasta la noche anterior a la salida. */
export function nochesReserva(r: Pick<Reserva, "llegada" | "salida">): string[] {
  const out: string[] = [];
  const d = new Date(r.llegada + "T12:00:00");
  const fin = new Date(r.salida + "T12:00:00");
  while (d < fin) { out.push(isoDia(d)); d.setDate(d.getDate() + 1); }
  return out;
}

export const fechaLarga = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("es-CO", { day: "numeric", month: "short" }).replace(".", "");

/** Datos obligatorios para enviar a revisión (RF-D-ALO-01.2). Devuelve lo que falta. */
export const faltantesRevision = (p: Publicacion): string[] => {
  const f: string[] = [];
  if (!p.titulo.trim()) f.push("título");
  if (!p.descripcion.trim()) f.push("descripción");
  if (!p.ciudad) f.push("ciudad");
  if (!p.ubicacion.trim()) f.push("ubicación");
  if (!p.tipo) f.push("tipo de alojamiento");
  if (!p.capacidad || p.capacidad <= 0) f.push("capacidad mayor que 0");
  if (!p.precioNoche || p.precioNoche <= 0) f.push("precio por noche");
  if (p.limpieza == null) f.push("tarifa de limpieza");
  if (!p.reglas.some((r) => r.descripcion.trim())) f.push("al menos una regla del alojamiento");
  if (!p.politica) f.push("política de cancelación");
  if (p.imagenes.length === 0) f.push("al menos una imagen");
  return f;
};
