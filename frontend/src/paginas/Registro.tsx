import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Aviso, Campo } from "../componentes/Campo";
import { leerError, type ErrorApi } from "../errores";
import { identidad, type DatosRegistro } from "../identidad/api";

/** HU-01 Registrarse (CU-USU-01). */
export function Registro() {
  const navegar = useNavigate();
  const [datos, setDatos] = useState<DatosRegistro>({
    nombre_completo: "",
    correo: "",
    telefono: "",
    password: "",
    rol: "HUESPED",
    acepta_datos: false,
  });
  const [error, setError] = useState<ErrorApi | null>(null);
  const [enviando, setEnviando] = useState(false);

  function cambiar<K extends keyof DatosRegistro>(campo: K, valor: DatosRegistro[K]) {
    setDatos((anterior) => ({ ...anterior, [campo]: valor }));
    // Al corregir un campo, su error deja de mostrarse.
    setError((anterior) => {
      if (!anterior?.campos[campo]) return anterior;
      const { [campo]: _corregido, ...resto } = anterior.campos;
      return { ...anterior, campos: resto };
    });
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await identidad.registrar(datos);
      navegar("/iniciar-sesion", { state: { registrado: datos.correo } });
    } catch (e) {
      setError(leerError(e));
    } finally {
      setEnviando(false);
    }
  }

  const errorDe = (campo: string) => error?.campos[campo];

  return (
    <section className="tarjeta">
      <h1>Crea tu cuenta</h1>
      {error && <Aviso tipo="error">{error.mensaje}</Aviso>}
      <form onSubmit={enviar} noValidate>
        <fieldset className="selector-rol">
          <legend>¿Cómo vas a usar la plataforma?</legend>
          <label>
            <input type="radio" name="rol" checked={datos.rol === "HUESPED"} onChange={() => cambiar("rol", "HUESPED")} />
            <span>
              <strong>Huésped</strong>
              <small>Busco y reservo alojamientos</small>
            </span>
          </label>
          <label>
            <input type="radio" name="rol" checked={datos.rol === "ANFITRION"} onChange={() => cambiar("rol", "ANFITRION")} />
            <span>
              <strong>Anfitrión</strong>
              <small>Publico mis alojamientos</small>
            </span>
          </label>
        </fieldset>
        <Campo
          etiqueta="Nombre completo"
          autoComplete="name"
          required
          value={datos.nombre_completo}
          onChange={(e) => cambiar("nombre_completo", e.target.value)}
          error={errorDe("nombre_completo")}
        />
        <Campo
          etiqueta="Correo electrónico"
          type="email"
          autoComplete="email"
          required
          value={datos.correo}
          onChange={(e) => cambiar("correo", e.target.value)}
          error={errorDe("correo")}
        />
        <Campo
          etiqueta="Teléfono"
          type="tel"
          autoComplete="tel"
          required
          value={datos.telefono}
          onChange={(e) => cambiar("telefono", e.target.value)}
          error={errorDe("telefono")}
        />
        <Campo
          etiqueta="Contraseña"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          ayuda="Mínimo 8 caracteres."
          value={datos.password}
          onChange={(e) => cambiar("password", e.target.value)}
          error={errorDe("password")}
        />
        <label className="casilla">
          <input type="checkbox" checked={datos.acepta_datos} onChange={(e) => cambiar("acepta_datos", e.target.checked)} />
          <span>
            Autorizo a Inversiones LR a tratar mis datos personales para gestionar mi cuenta y mis reservas, conforme a la
            Ley 1581 de 2012. Puedo consultarlos, corregirlos o pedir su supresión en cualquier momento.
          </span>
        </label>
        {errorDe("acepta_datos") && (
          <small className="error-campo" role="alert">
            {errorDe("acepta_datos")}
          </small>
        )}
        <button type="submit" className="boton" disabled={enviando}>
          {enviando ? "Creando la cuenta…" : "Crear cuenta"}
        </button>
      </form>
      <p className="pie-tarjeta">
        ¿Ya tienes cuenta? <Link to="/iniciar-sesion">Inicia sesión</Link>
      </p>
    </section>
  );
}
