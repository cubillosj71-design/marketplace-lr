import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Gráficas del tablero, en SVG y sin librerías. Siguen la guía de visualización del equipo:
 * - una sola escala por gráfica (nunca dos ejes); dos medidas distintas van en dos gráficas;
 * - marcas delgadas con el extremo de datos redondeado y apoyado en la base, rejilla tenue;
 * - colores por categoría en orden fijo (paleta validada para daltonismo); el texto va en tinta, no en el color;
 * - cada gráfica tiene información al pasar el mouse y una vista en tabla (accesibilidad).
 */

/** Paleta por categoría, en orden fijo (validada: separación para daltonismo y visión normal sobre blanco). */
export const SERIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"] as const;

const TINTA = "var(--text)";
const TINTA_SUAVE = "var(--muted)";
const REJILLA = "#e8ecea";

function useAncho<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [ancho, setAncho] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setAncho(Math.floor(e!.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, ancho];
}

/** Escala "bonita" para el eje: 0, paso, 2·paso… hasta cubrir el máximo. */
function marcasEje(maximo: number, enteros: boolean, cuantas = 4): number[] {
  if (maximo <= 0) return [0, 1];
  const bruto = Math.max(enteros ? 1 : 0, maximo / cuantas);  // una cantidad de reservas no tiene decimales
  const potencia = 10 ** Math.floor(Math.log10(bruto));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * potencia).find((p) => p >= bruto) ?? bruto;
  const marcas: number[] = [];
  for (let v = 0; v <= maximo + paso * 0.001; v += paso) marcas.push(v);
  if (marcas[marcas.length - 1]! < maximo) marcas.push(marcas[marcas.length - 1]! + paso);
  return marcas;
}

function Tooltip({ x, y, children }: { x: number; y: number; children: ReactNode }) {
  return (
    <div role="status" style={{
      position: "absolute", left: x, top: y, transform: "translate(-50%, calc(-100% - 10px))", pointerEvents: "none",
      background: "var(--brand-950)", color: "#fff", padding: "8px 10px", borderRadius: 8, fontSize: 12.5,
      lineHeight: 1.35, whiteSpace: "nowrap", boxShadow: "0 6px 18px -8px rgba(0,0,0,.45)", zIndex: 2,
    }}>{children}</div>
  );
}

export interface Punto { etiqueta: string; detalle: string; valor: number }

/** Barras verticales de una sola serie en el tiempo (reservas o ingresos por día o por mes). */
export function SerieEnElTiempo({ puntos, formato, color = SERIE[0], alto = 220, nombre, enteros = false }: {
  puntos: Punto[]; formato: (v: number) => string; color?: string; alto?: number; nombre: string; enteros?: boolean;
}) {
  const [ref, ancho] = useAncho<HTMLDivElement>();
  const [activo, setActivo] = useState<number | null>(null);
  const izq = 64, der = 8, arriba = 12, abajo = 26;
  const marcas = marcasEje(Math.max(0, ...puntos.map((p) => p.valor)), enteros);
  const tope = marcas[marcas.length - 1]!;
  const w = Math.max(0, ancho - izq - der), h = alto - arriba - abajo;
  const col = puntos.length ? w / puntos.length : 0;
  const barra = Math.max(2, Math.min(28, col * 0.62));
  const y = (v: number) => arriba + h - (v / tope) * h;
  const cadaCuanto = Math.max(1, Math.ceil(puntos.length / Math.max(1, Math.floor(w / 56))));  // etiquetas que caben
  const todoEnCero = puntos.every((p) => p.valor === 0);

  return (
    <div ref={ref} style={{ position: "relative" }} onMouseLeave={() => setActivo(null)}>
      {ancho > 0 && (
        <svg width={ancho} height={alto} role="img" aria-label={`${nombre}: gráfica de barras`}>
          {marcas.map((m) => (
            <g key={m}>
              <line x1={izq} x2={izq + w} y1={y(m)} y2={y(m)} stroke={REJILLA} strokeWidth={1} />
              <text x={izq - 8} y={y(m)} dy="0.32em" textAnchor="end" fontSize={11.5} fill={TINTA_SUAVE}>{formato(m)}</text>
            </g>
          ))}
          {puntos.map((p, i) => {
            const cx = izq + col * i + col / 2;
            const alto_ = Math.max(0, y(0) - y(p.valor));
            const r = Math.min(4, barra / 2, alto_);
            return (
              <g key={p.detalle}>
                {activo === i && <rect x={izq + col * i} y={arriba} width={col} height={h} fill="var(--brand-50)" />}
                {alto_ > 0 && (
                  // extremo de datos redondeado (4px) y base recta apoyada en el eje
                  <path fill={color} d={`M${cx - barra / 2},${y(0)} V${y(p.valor) + r} Q${cx - barra / 2},${y(p.valor)} ${cx - barra / 2 + r},${y(p.valor)}
                    H${cx + barra / 2 - r} Q${cx + barra / 2},${y(p.valor)} ${cx + barra / 2},${y(p.valor) + r} V${y(0)} Z`} />
                )}
                {i % cadaCuanto === 0 && (
                  <text x={cx} y={alto - 8} textAnchor="middle" fontSize={11.5} fill={TINTA_SUAVE}>{p.etiqueta}</text>
                )}
                {/* zona de hover más grande que la barra: toda la columna */}
                <rect x={izq + col * i} y={arriba} width={col} height={h} fill="transparent"
                      onMouseEnter={() => setActivo(i)} onMouseMove={() => setActivo(i)} />
              </g>
            );
          })}
          <line x1={izq} x2={izq + w} y1={y(0)} y2={y(0)} stroke="#c9d1ce" strokeWidth={1} />
          {todoEnCero && <text x={izq + w / 2} y={arriba + h / 2} textAnchor="middle" fontSize={13} fill={TINTA_SUAVE}>Sin reservas en el periodo</text>}
        </svg>
      )}
      {activo !== null && puntos[activo] && (
        <Tooltip x={izq + col * activo + col / 2} y={y(puntos[activo]!.valor)}>
          <div style={{ opacity: 0.8 }}>{puntos[activo]!.detalle}</div>
          <b>{formato(puntos[activo]!.valor)}</b>
        </Tooltip>
      )}
    </div>
  );
}

export interface Parte { clave: string; nombre: string; valor: number; color: string }

/** Barra apilada de partes de un todo (reservas por estado), con leyenda que nombra, cuenta y da el porcentaje. */
export function PartesDelTodo({ partes, unidad }: { partes: Parte[]; unidad: [string, string] }) {
  const [activa, setActiva] = useState<string | null>(null);
  const total = partes.reduce((s, p) => s + p.valor, 0);
  const pct = (v: number) => (total ? Math.round((v / total) * 100) : 0);
  const visibles = partes.filter((p) => p.valor > 0);
  return (
    <div className="stack" style={{ gap: 12 }}>
      <div style={{ display: "flex", gap: 2, height: 14, borderRadius: 4, overflow: "hidden", background: total ? undefined : REJILLA }}
           role="img" aria-label={partes.map((p) => `${p.nombre}: ${p.valor}`).join(", ")}>
        {visibles.map((p) => (
          <div key={p.clave} title={`${p.nombre}: ${p.valor} (${pct(p.valor)} %)`}
               onMouseEnter={() => setActiva(p.clave)} onMouseLeave={() => setActiva(null)}
               style={{ flex: p.valor, background: p.color, opacity: activa && activa !== p.clave ? 0.35 : 1, transition: "opacity .15s" }} />
        ))}
      </div>
      <ul className="list-plain stack" style={{ gap: 8 }}>
        {partes.map((p) => (
          <li key={p.clave} className="row-between" onMouseEnter={() => setActiva(p.clave)} onMouseLeave={() => setActiva(null)}
              style={{ opacity: activa && activa !== p.clave ? 0.55 : 1 }}>
            <span className="row" style={{ gap: 8 }}>
              <span aria-hidden style={{ width: 10, height: 10, borderRadius: 3, background: p.color, flex: "none" }} />
              <span style={{ color: TINTA }}>{p.nombre}</span>
            </span>
            <span><b>{p.valor}</b> <span className="subtle">· {pct(p.valor)} %</span></span>
          </li>
        ))}
      </ul>
      <p className="subtle" style={{ margin: 0 }}>{total} {total === 1 ? unidad[0] : unidad[1]} en el periodo</p>
    </div>
  );
}

export interface Fila { nombre: string; valor: number; detalle?: string }

/** Barras horizontales de una sola serie (ciudades con más reservas, usuarios por rol). */
export function BarrasHorizontales({ filas, color = SERIE[0], vacio }: { filas: Fila[]; color?: string; vacio: string }) {
  const max = Math.max(1, ...filas.map((f) => f.valor));
  if (!filas.length || filas.every((f) => f.valor === 0)) return <p className="muted">{vacio}</p>;
  return (
    <ul className="list-plain stack" style={{ gap: 12 }}>
      {filas.map((f) => (
        <li key={f.nombre} className="stack" style={{ gap: 5 }} title={f.detalle ? `${f.nombre}: ${f.detalle}` : undefined}>
          <div className="row-between" style={{ width: "100%" }}><span style={{ color: TINTA }}>{f.nombre}</span>
            <span><b>{f.valor}</b>{f.detalle && <span className="subtle"> · {f.detalle}</span>}</span></div>
          <div style={{ width: "100%", height: 10, borderRadius: 4, background: "#f1f4f3" }}>
            <div style={{ width: `${(f.valor / max) * 100}%`, minWidth: f.valor ? 4 : 0, height: "100%", borderRadius: "0 4px 4px 0", background: color }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
