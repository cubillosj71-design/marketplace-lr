import { AlertTriangle } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

/**
 * Límite de error (Error Boundary de React). Si un componente lanza una excepción al dibujarse, React desmonta
 * todo el árbol y la aplicación queda en blanco. Este límite atrapa la excepción, la deja en la consola del
 * navegador y muestra un aviso con salida, en lugar de la pantalla vacía.
 *
 * Los errores de la API no llegan aquí: cada pantalla los atrapa con leerError() y muestra el mensaje del backend.
 * Este límite es para lo que nadie previó (un dato nulo inesperado, un error de programación).
 *
 * - `reinicio`: cuando cambia (la ruta), el límite se limpia, así navegar a otra pantalla vuelve a funcionar.
 * - `completo`: límite de toda la aplicación; solo ofrece recargar, porque el layout también pudo fallar.
 */
export class LimiteDeError extends Component<{ children: ReactNode; reinicio?: string; completo?: boolean }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Error al mostrar la pantalla", error, info.componentStack);
  }

  componentDidUpdate(anteriores: { reinicio?: string }) {
    if (this.state.error && anteriores.reinicio !== this.props.reinicio) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="content">
        <div className="card empty-state" role="alert">
          <AlertTriangle />
          <h2>Algo salió mal al mostrar esta pantalla</h2>
          <p>{this.props.completo
            ? "Recarga la página para continuar. Si vuelve a pasar, inténtalo de nuevo en unos minutos."
            : "Puedes recargarla o ir a otra sección desde el menú. Tus datos guardados no se perdieron."}</p>
          <button className="btn btn-primary" onClick={() => window.location.reload()}>Recargar la página</button>
        </div>
      </div>
    );
  }
}
