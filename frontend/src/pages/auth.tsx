import { ArrowLeft, Building2, Check, Circle, Clock, Compass, Copy, Eye, EyeOff, Luggage, ShieldCheck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { identidadApi, leerError } from "../api";
import type { Rol } from "../data";
import { AuthLayout, usePrimeraPantalla } from "../layout";
import { useStore, useToast } from "../store";
import { Alert, Field } from "../ui";

const correoValido = (c: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(c.trim());

function ClaveInput({ value, onChange, placeholder, autoComplete }: {
  value: string; onChange: (v: string) => void; placeholder?: string; autoComplete?: string;
}) {
  const [ver, setVer] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <input className="input" type={ver ? "text" : "password"} value={value} placeholder={placeholder}
        autoComplete={autoComplete} onChange={(e) => onChange(e.target.value)} style={{ paddingRight: 44 }} />
      <button type="button" className="link-btn" onClick={() => setVer(!ver)} aria-label={ver ? "Ocultar contraseña" : "Mostrar contraseña"}
        style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", color: "var(--muted)", display: "grid" }}>
        {ver ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
}

/* ---------------- CU-USU-02 Iniciar sesión ---------------- */
export function Login() {
  const { iniciarSesion, avisoSesion, limpiarAviso } = useStore();
  const toast = useToast();
  const go = useNavigate();
  const loc = useLocation();
  // volver: página a la que se regresa después de entrar (p. ej. el detalle que el visitante quería cotizar, CA-05.1)
  const aviso = (loc.state as { aviso?: string; correo?: string; volver?: string } | null) ?? {};
  const [correo, setCorreo] = useState(aviso.correo ?? "");
  const [clave, setClave] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const entrar = async () => {
    if (!correo.trim() || !clave) return setError("Escribe tu correo y tu contraseña.");
    setEnviando(true);
    const r = await iniciarSesion(correo, clave);
    setEnviando(false);
    // CA-02.2: "Correo o contraseña incorrectos". CA-02.3: cuenta restringida, con el motivo (lo trae el detalle)
    if (!r.ok) { setError(r.error); setClave(""); return; }
    if (r.msg) toast(r.msg);
    go(aviso.volver ?? "/inicio");
  };

  // El acceso del administrador solo llena el correo: la contraseña se escribe (HU-02).
  // Las demás cuentas de demostración se escriben a mano: el cliente no ve atajos de prueba.
  const demo = (c: string) => { setCorreo(c); setClave(""); setError(""); limpiarAviso(); };

  return (
    <AuthLayout>
      <div className="head">
        <h1>Bienvenido de nuevo</h1>
        <p>Ingresa con tu cuenta para continuar.</p>
      </div>
      {avisoSesion && !error && <Alert tipo="warn">{avisoSesion}</Alert>}
      {aviso.aviso && !avisoSesion && !error && <Alert tipo="ok">{aviso.aviso}</Alert>}
      {error && <Alert tipo="error">{error}</Alert>}
      <form className="stack" onSubmit={(e: FormEvent) => { e.preventDefault(); entrar(); }} noValidate>
        <Field label="Correo electrónico">
          <input className="input" type="email" autoComplete="email" placeholder="tu@correo.com" value={correo} onChange={(e) => setCorreo(e.target.value)} />
        </Field>
        <Field label="Contraseña">
          <ClaveInput value={clave} onChange={setClave} placeholder="Tu contraseña" autoComplete="current-password" />
        </Field>
        <div className="row-between">
          <Link to="/explorar-publico" className="subtle" style={{ fontWeight: 500, display: "inline-flex", gap: 6, alignItems: "center" }}>
            <Compass size={15} /> Explorar sin cuenta
          </Link>
          <Link to="/recuperar">¿Olvidaste tu contraseña?</Link>
        </div>
        <button className="btn btn-primary btn-block" type="submit" disabled={enviando}>{enviando ? "Ingresando…" : "Ingresar"}</button>
      </form>
      <p className="muted" style={{ textAlign: "center" }}>¿No tienes cuenta? <Link to="/registro">Regístrate</Link></p>
      <div className="demo-accounts">
        <span className="subtle">¿Administras la plataforma?</span>
        <div className="chips">
          <button className="demo-chip" onClick={() => demo("admin@inversioneslr.com")}><ShieldCheck /> Administrador</button>
        </div>
      </div>
    </AuthLayout>
  );
}

/** Después de ingresar, cada usuario llega a la primera pantalla que sus permisos le dejan abrir. */
export function Inicio() {
  const { usuario } = useStore();
  const primera = usePrimeraPantalla();
  return <Navigate to={usuario ? primera : "/ingresar"} replace />;
}

/* ---------------- CU-USU-01 Registrarse ---------------- */
async function registrar({ nombre, correo, telefono, clave, rol, acepta }: {
  nombre: string; correo: string; telefono: string; clave: string; rol: Rol; acepta: boolean;
}): Promise<{ ok: true } | { ok: false; error: string; campo?: string }> {
  try {
    await identidadApi.registrar({ nombre_completo: nombre.trim(), correo: correo.trim(), telefono: telefono.trim(), password: clave, rol, acepta_datos: acepta });
    return { ok: true };
  } catch (e) {
    const r = leerError(e);
    // Nombres de campo de la API -> nombres del formulario
    const campos: Record<string, string> = { nombre_completo: "nombre", password: "clave", acepta_datos: "acepta" };
    return { ok: false, error: r.error, campo: r.campo ? campos[r.campo] ?? r.campo : undefined };
  }
}

export function Registro() {
  const go = useNavigate();
  const [f, setF] = useState({ nombre: "", correo: "", telefono: "", clave: "", rol: "HUESPED" as Rol, acepta: false });
  const [err, setErr] = useState<Record<string, string>>({});
  const set = (k: keyof typeof f, v: string | boolean) => setF((x) => ({ ...x, [k]: v }));

  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    const er: Record<string, string> = {};
    if (!f.nombre.trim()) er.nombre = "Escribe tu nombre completo.";
    if (!correoValido(f.correo)) er.correo = "Escribe un correo válido.";
    if (!f.telefono.trim()) er.telefono = "Escribe tu teléfono.";
    if (f.clave.length < 8) er.clave = "La contraseña debe tener al menos 8 caracteres.";
    if (!f.acepta) er.acepta = "La autorización es obligatoria: sin ella no se crea la cuenta.";
    if (!Object.keys(er).length) {
      setEnviando(true);
      const r = await registrar(f);
      setEnviando(false);
      if (!r.ok) er[r.campo ?? "general"] = r.error;
      else return go("/ingresar", { state: { aviso: "Tu cuenta quedó creada. Ya puedes iniciar sesión.", correo: f.correo } });
    }
    setErr(er);
  };

  const roles: { v: Rol; t: string; d: string; icon: typeof Luggage }[] = [
    { v: "HUESPED", t: "Huésped", d: "Busco y reservo", icon: Luggage },
    { v: "ANFITRION", t: "Anfitrión", d: "Publico alojamientos", icon: Building2 },
  ];

  return (
    <AuthLayout>
      <div className="head">
        <h1>Crea tu cuenta</h1>
        <p>Elige cómo usarás la plataforma. Cada cuenta tiene un único rol.</p>
      </div>
      {err.general && <Alert tipo="error">{err.general}</Alert>}
      <form className="stack" onSubmit={enviar} noValidate>
        <div className="choice-group" role="radiogroup" aria-label="Rol">
          {roles.map((r) => (
            <button type="button" key={r.v} role="radio" aria-checked={f.rol === r.v}
              className={`choice ${f.rol === r.v ? "on" : ""}`} onClick={() => set("rol", r.v)}>
              <span className="ico"><r.icon size={18} /></span>
              <span style={{ textAlign: "left" }}><b>{r.t}</b><small>{r.d}</small></span>
            </button>
          ))}
        </div>
        <Field label="Nombre completo" error={err.nombre}>
          <input className="input" placeholder="Ej. Laura Gómez" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} />
        </Field>
        <div className="grid-2">
          <Field label="Correo electrónico" error={err.correo}>
            <input className="input" type="email" placeholder="tu@correo.com" value={f.correo} onChange={(e) => set("correo", e.target.value)} />
          </Field>
          <Field label="Teléfono" error={err.telefono}>
            <input className="input" inputMode="tel" placeholder="310 555 0182" value={f.telefono} onChange={(e) => set("telefono", e.target.value)} />
          </Field>
        </div>
        <Field label="Contraseña" error={err.clave} hint="Mínimo 8 caracteres.">
          <ClaveInput value={f.clave} onChange={(v) => set("clave", v)} placeholder="Mínimo 8 caracteres" autoComplete="new-password" />
        </Field>
        <div className="stack-sm">
          <label className="check">
            <input type="checkbox" checked={f.acepta} onChange={(e) => set("acepta", e.target.checked)} />
            <span>Autorizo el tratamiento de mis datos personales (Ley 1581 de 2012).</span>
          </label>
          {err.acepta && <span className="error-text">{err.acepta}</span>}
        </div>
        <button className="btn btn-primary btn-block" type="submit" disabled={enviando}>{enviando ? "Creando la cuenta…" : "Crear cuenta"}</button>
      </form>
      <p className="muted" style={{ textAlign: "center" }}>¿Ya tienes cuenta? <Link to="/ingresar">Inicia sesión</Link></p>
    </AuthLayout>
  );
}

/* ---------------- CU-USU-03 Recuperar contraseña ---------------- */
async function solicitarEnlace(correo: string): Promise<{ ok: true; token: string } | { ok: false; error: string }> {
  try {
    const { data } = await identidadApi.solicitarRecuperacion(correo.trim());
    const token = data.enlace?.split("/restablecer/")[1];
    // Si el correo no existe, la API no lo revela: responde igual, solo que sin enlace.
    if (!token) return { ok: false, error: "No apareció un enlace para ese correo. Revisa que esté bien escrito." };
    return { ok: true, token };
  } catch (e) {
    return { ok: false, error: leerError(e).error };
  }
}

export function Recuperar() {
  const toast = useToast();
  const [correo, setCorreo] = useState("");
  const [error, setError] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const enlace = !token ? "" : import.meta.env.VITE_ROUTER === "memory"
    ? `alojamientos-lr/restablecer/${token}`
    : `${location.origin}${location.pathname}#/restablecer/${token}`;

  return (
    <AuthLayout>
      <Link to="/ingresar" className="back"><ArrowLeft /> Volver a ingresar</Link>
      <div className="head">
        <h1>¿Olvidaste tu contraseña?</h1>
        <p>Escribe el correo de tu cuenta y te damos un enlace para definir una nueva.</p>
      </div>
      {!token ? (
        <form className="stack" noValidate onSubmit={async (e) => {
          e.preventDefault();
          if (!correoValido(correo)) return setError("Escribe un correo válido.");
          const r = await solicitarEnlace(correo);
          if (!r.ok) return setError(r.error);
          setError(""); setToken(r.token);
        }}>
          <Field label="Correo electrónico" error={error}>
            <input className="input" type="email" placeholder="tu@correo.com" value={correo} onChange={(e) => setCorreo(e.target.value)} />
          </Field>
          <button className="btn btn-primary btn-block" type="submit">Generar enlace</button>
        </form>
      ) : (
        <div className="stack">
          <Alert tipo="info">
            <b>Recuperación simulada.</b> Como la plataforma no envía correos, aquí tienes el enlace.
          </Alert>
          <div className="card card-tight stack-sm" style={{ boxShadow: "none" }}>
            <span className="label">Tu enlace</span>
            <code style={{ fontSize: 13, wordBreak: "break-all", color: "var(--brand-800)" }}>{enlace}</code>
            <span className="hint-text" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
              <Clock size={14} /> Vence en 20 minutos y sirve una sola vez.
            </span>
          </div>
          <div className="row">
            <Link className="btn btn-primary" to={`/restablecer/${token}`}>Abrir enlace</Link>
            <button className="btn btn-secondary" onClick={() => { navigator.clipboard?.writeText(enlace).catch(() => {}); toast("Enlace copiado"); }}>
              <Copy /> Copiar
            </button>
          </div>
        </div>
      )}
    </AuthLayout>
  );
}

/* ---------------- CU-USU-03 Definir nueva contraseña ---------------- */
export function Restablecer() {
  const { token = "" } = useParams();
  const go = useNavigate();
  const [clave, setClave] = useState("");
  const [conf, setConf] = useState("");
  const [error, setError] = useState("");
  const [est, setEst] = useState<"cargando" | "valido" | "vencido" | "usado" | "inexistente">("cargando");

  // El servidor dice si el enlace sirve apenas se abre (CA-03.2, CA-03.3).
  useEffect(() => {
    let activo = true;
    identidadApi.estadoEnlace(token)
      .then((r) => { if (activo) setEst(r.data.estado); })
      .catch(() => { if (activo) setEst("inexistente"); });
    return () => { activo = false; };
  }, [token]);
  const largo = clave.length >= 8;
  const iguales = clave.length > 0 && clave === conf;

  const Req = ({ ok, children }: { ok: boolean; children: string }) => (
    <span className={ok ? "ok" : ""}>{ok ? <Check /> : <Circle />}{children}</span>
  );

  return (
    <AuthLayout>
      <Link to="/ingresar" className="back"><ArrowLeft /> Volver a ingresar</Link>
      {est === "cargando" ? (
        <p className="muted" style={{ textAlign: "center" }}>Verificando el enlace…</p>
      ) : est !== "valido" ? (
        <>
          <div className="head"><h1>Este enlace ya no sirve</h1></div>
          <Alert tipo="error">
            {est === "usado" ? "Este enlace ya se usó una vez." : est === "vencido" ? "Este enlace venció: pasaron más de 20 minutos." : "Este enlace no existe."}
            {" "}Solicita uno nuevo.
          </Alert>
          <Link className="btn btn-primary btn-block" to="/recuperar">Solicitar un enlace nuevo</Link>
        </>
      ) : (
        <>
          <div className="head">
            <h1>Crea tu nueva contraseña</h1>
            <p>Úsala la próxima vez que ingreses.</p>
          </div>
          {error && <Alert tipo="error">{error}</Alert>}
          <form className="stack" noValidate onSubmit={async (e) => {
            e.preventDefault();
            if (!largo || !iguales) return setError("Revisa los requisitos de la contraseña.");
            try { await identidadApi.restablecer(token, clave); } catch (err) { return setError(leerError(err).error); }
            go("/ingresar", { state: { aviso: "Contraseña actualizada. Ingresa con la nueva." } });
          }}>
            <Field label="Nueva contraseña"><ClaveInput value={clave} onChange={setClave} autoComplete="new-password" /></Field>
            <Field label="Confirmar contraseña"><ClaveInput value={conf} onChange={setConf} autoComplete="new-password" /></Field>
            <div className="req-checks">
              <Req ok={largo}>Mínimo 8 caracteres</Req>
              <Req ok={iguales}>Las dos contraseñas coinciden</Req>
            </div>
            <button className="btn btn-primary btn-block" type="submit">Guardar y continuar</button>
          </form>
        </>
      )}
    </AuthLayout>
  );
}
