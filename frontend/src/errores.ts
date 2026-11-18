import { isAxiosError } from "axios";

/** Error de la API ya listo para mostrar: un mensaje general y los errores por campo. */
export interface ErrorApi {
  codigo?: string;
  mensaje: string;
  campos: Record<string, string>;
}

/**
 * La API responde de dos formas:
 * - Reglas de negocio: { codigo, mensaje, campo? } (services.py de cada servicio).
 * - Validación de formato de DRF: { nombre_del_campo: ["mensaje", ...] }.
 * Esta función convierte cualquiera de las dos en un ErrorApi.
 */
export function leerError(error: unknown): ErrorApi {
  if (!isAxiosError(error) || !error.response) {
    return { mensaje: "No hay conexión con la plataforma. Intenta de nuevo en un momento.", campos: {} };
  }
  if (error.response.status === 429) {
    return { mensaje: "Hiciste demasiados intentos seguidos. Espera un minuto y vuelve a intentarlo.", campos: {} };
  }
  const datos = error.response.data as Record<string, unknown> | undefined;
  if (datos && typeof datos.mensaje === "string") {
    const codigo = datos.codigo as string | undefined;
    // Si el error es de un campo, el detalle se muestra junto al campo y arriba
    // solo un aviso general, para no repetir el mismo texto dos veces.
    if (typeof datos.campo === "string") {
      return { codigo, mensaje: "Revisa los datos marcados.", campos: { [datos.campo]: datos.mensaje } };
    }
    return { codigo, mensaje: datos.mensaje, campos: {} };
  }
  if (datos && typeof datos.detail === "string") {
    return { mensaje: datos.detail, campos: {} };
  }
  const campos: Record<string, string> = {};
  for (const [campo, valor] of Object.entries(datos ?? {})) {
    campos[campo] = Array.isArray(valor) ? String(valor[0]) : String(valor);
  }
  return { mensaje: "Revisa los datos marcados.", campos };
}
