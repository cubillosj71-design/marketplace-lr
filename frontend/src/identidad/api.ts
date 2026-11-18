import { api } from "../api";

/** Llamadas a SRV-01 Identidad (sección 3.4 del diseño). */

export type Rol = "HUESPED" | "ANFITRION" | "ADMINISTRADOR";

export interface Usuario {
  id: number;
  nombre_completo: string;
  correo: string;
  telefono: string;
  rol: Rol;
  estado: "ACTIVA" | "DESACTIVADA" | "RESTRINGIDA";
  fecha_registro: string;
}

export interface Sesion {
  access: string;
  usuario: Usuario;
}

export interface DatosRegistro {
  nombre_completo: string;
  correo: string;
  telefono: string;
  password: string;
  rol: Exclude<Rol, "ADMINISTRADOR">;
  acepta_datos: boolean;
}

export const NOMBRE_ROL: Record<Rol, string> = {
  HUESPED: "Huésped",
  ANFITRION: "Anfitrión",
  ADMINISTRADOR: "Administrador",
};

export const identidad = {
  registrar: (datos: DatosRegistro) => api.post<{ mensaje: string; usuario: Usuario }>("/identidad/registro", datos),
  iniciarSesion: (correo: string, password: string) => api.post<Sesion>("/identidad/token", { correo, password }),
  salir: () => api.post("/identidad/salir"),
  solicitarRecuperacion: (correo: string) =>
    api.post<{ mensaje: string; enlace: string | null }>("/identidad/recuperacion", { correo }),
  verificarEnlace: (token: string) => api.get<{ valido: true }>(`/identidad/recuperacion/${encodeURIComponent(token)}`),
  restablecer: (token: string, password: string) =>
    api.post<{ mensaje: string }>(`/identidad/recuperacion/${encodeURIComponent(token)}`, { password }),
  perfil: () => api.get<Usuario>("/identidad/perfil"),
  actualizarPerfil: (cambios: Partial<Pick<Usuario, "nombre_completo" | "telefono">>) =>
    api.patch<Usuario>("/identidad/perfil", cambios),
  desactivar: () => api.post<{ mensaje: string }>("/identidad/perfil/desactivar"),
};
