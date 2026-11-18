import { useId, type InputHTMLAttributes, type ReactNode } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  etiqueta: string;
  error?: string;
  ayuda?: string;
}

/** Campo de formulario con etiqueta, ayuda y error asociados para lectores de pantalla. */
export function Campo({ etiqueta, error, ayuda, ...props }: Props) {
  const id = useId();
  const idAyuda = `${id}-ayuda`;
  const idError = `${id}-error`;
  const descritoPor = [ayuda ? idAyuda : null, error ? idError : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="campo">
      <label htmlFor={id}>{etiqueta}</label>
      <input id={id} aria-invalid={Boolean(error)} aria-describedby={descritoPor} {...props} />
      {ayuda && (
        <small id={idAyuda} className="ayuda">
          {ayuda}
        </small>
      )}
      {error && (
        <small id={idError} className="error-campo" role="alert">
          {error}
        </small>
      )}
    </div>
  );
}

export function Aviso({ tipo, children }: { tipo: "error" | "exito" | "info"; children: ReactNode }) {
  return (
    <div className={`aviso aviso-${tipo}`} role={tipo === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}
