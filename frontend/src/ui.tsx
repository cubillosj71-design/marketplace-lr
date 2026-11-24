import { AlertTriangle, CheckCircle2, ImageIcon, Info, X, XCircle } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { ESTADO_TXT, type EstadoPub, type Imagen } from "./data";

/** Campo de formulario con etiqueta, ayuda, marca de opcional y mensaje de error. */
export function Field({ label, opcional, error, hint, children, className = "" }: {
  label: string; opcional?: boolean; error?: string; hint?: string; children: ReactNode; className?: string;
}) {
  return (
    <label className={`field ${error ? "has-error" : ""} ${className}`}>
      <span className="label">{label}{opcional && <span className="opt"> (opcional)</span>}</span>
      {children}
      {error ? <span className="error-text">{error}</span> : hint ? <span className="hint-text">{hint}</span> : null}
    </label>
  );
}

/** Mensaje destacado de error, éxito, advertencia o información, con su ícono. */
export function Alert({ tipo, children }: { tipo: "error" | "ok" | "warn" | "info"; children: ReactNode }) {
  const Icon = { error: XCircle, ok: CheckCircle2, warn: AlertTriangle, info: Info }[tipo];
  return (
    <div className={`alert alert-${tipo}`} role={tipo === "error" ? "alert" : undefined}>
      <Icon />
      <div>{children}</div>
    </div>
  );
}

/** Etiqueta de color con el estado de una publicación en palabras ("En revisión", "Activa"). */
export const Badge = ({ estado }: { estado: EstadoPub }) => (
  <span className={`badge badge-${estado}`} >{ESTADO_TXT[estado]}</span>
);

/** Ventana modal: se cierra con Escape o al hacer clic fuera. */
export function Modal({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true">{children}</div>
    </div>
  );
}

/** Miniatura de una foto con etiqueta opcional y botón para quitarla; sin foto, muestra un fondo de color con un ícono. */
export function ImageTile({ img, etiqueta, onRemove, style }: {
  img?: Imagen; etiqueta?: string; onRemove?: () => void; style?: React.CSSProperties;
}) {
  return (
    <div className="img-ph" style={{ background: img?.color ?? "linear-gradient(135deg,#cfdcd8,#e8efec)", ...style }}>
      {img?.src ? <img src={img.src} alt={img.nombre} /> : <ImageIcon aria-hidden />}
      {etiqueta && <span className="tag">{etiqueta}</span>}
      {onRemove && (
        <button type="button" className="remove" onClick={onRemove} aria-label={`Quitar ${img?.nombre ?? "imagen"}`}>
          <X />
        </button>
      )}
    </div>
  );
}

/** Logo de Alojamientos LR (iniciales LR sobre fondo naranja). */
export const Logo = () => (
  <span className="logo"><span className="mark">LR</span>Alojamientos LR</span>
);

