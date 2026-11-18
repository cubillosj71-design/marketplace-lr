import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { cuandoSePierdaLaSesion, guardarTokenAcceso, renovarSesion } from "../api";
import { identidad, type Usuario } from "../identidad/api";

interface ValorSesion {
  usuario: Usuario | null;
  /** true mientras se intenta recuperar la sesión al cargar la página. */
  cargando: boolean;
  iniciarSesion: (correo: string, password: string) => Promise<Usuario>;
  cerrarSesion: () => Promise<void>;
  actualizarUsuario: (usuario: Usuario) => void;
  /** Olvida la sesión en el navegador (por ejemplo, después de desactivar la cuenta). */
  olvidarSesion: () => void;
}

const SesionContext = createContext<ValorSesion | null>(null);

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);

  const olvidarSesion = useCallback(() => {
    guardarTokenAcceso(null);
    setUsuario(null);
  }, []);

  useEffect(() => {
    cuandoSePierdaLaSesion(olvidarSesion);
    // Al recargar la página, el token de acceso (en memoria) se pierde. Si la
    // cookie de renovación sigue vigente, se recupera la sesión sin pedir la
    // contraseña otra vez.
    renovarSesion()
      .then((datos) => setUsuario((datos?.usuario as Usuario) ?? null))
      .finally(() => setCargando(false));
  }, [olvidarSesion]);

  const iniciarSesion = useCallback(async (correo: string, password: string) => {
    const { data } = await identidad.iniciarSesion(correo, password);
    guardarTokenAcceso(data.access);
    setUsuario(data.usuario);
    return data.usuario;
  }, []);

  const cerrarSesion = useCallback(async () => {
    try {
      await identidad.salir();
    } finally {
      olvidarSesion();
    }
  }, [olvidarSesion]);

  const valor = useMemo(
    () => ({ usuario, cargando, iniciarSesion, cerrarSesion, actualizarUsuario: setUsuario, olvidarSesion }),
    [usuario, cargando, iniciarSesion, cerrarSesion, olvidarSesion],
  );

  return <SesionContext.Provider value={valor}>{children}</SesionContext.Provider>;
}

export function useSesion(): ValorSesion {
  const valor = useContext(SesionContext);
  if (!valor) throw new Error("useSesion debe usarse dentro de <ProveedorSesion>");
  return valor;
}
