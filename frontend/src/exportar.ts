import ExcelJS from "exceljs";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

/* Exportación de reportes (RF-D-ADM-05.2): el mismo contenido sale en PDF o en Excel. */
export interface Reporte {
  titulo: string;
  periodo: string;
  generadoPor: string;
  resumen: [string, string | number][];
  columnas: string[];
  filas: (string | number)[][];
  archivo: string; // sin extensión
  moneda?: number[]; // índices de columnas en pesos: número en Excel, formato COP en PDF
}

const pesos = (n: number) => "$" + Math.round(n).toLocaleString("es-CO");
const VERDE: [number, number, number] = [15, 118, 110];

function bajar(blob: Blob, nombre: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

const ahora = () => new Date().toLocaleString("es-CO", { dateStyle: "long", timeStyle: "short" });

export function descargarPDF(r: Reporte) {
  const doc = new jsPDF({ orientation: r.columnas.length > 6 ? "landscape" : "portrait", unit: "pt", format: "a4" });
  const ancho = doc.internal.pageSize.getWidth();
  doc.setFillColor(...VERDE);
  doc.rect(0, 0, ancho, 64, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.text("Alojamientos LR", 40, 30);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.text(r.titulo, 40, 48);
  doc.setTextColor(60, 60, 60);
  doc.setFontSize(10);
  doc.text(`Periodo: ${r.periodo}`, 40, 88);
  doc.text(`Generado por: ${r.generadoPor} · ${ahora()}`, 40, 103);

  autoTable(doc, {
    startY: 118,
    head: [["Resumen", "Valor"]],
    body: r.resumen.map(([k, v]) => [k, String(v)]),
    theme: "grid",
    headStyles: { fillColor: VERDE },
    styles: { fontSize: 9 },
    tableWidth: 280,
  });
  const y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 18;
  autoTable(doc, {
    startY: y,
    head: [r.columnas],
    body: r.filas.length ? r.filas.map((f) => f.map((v, i) => (r.moneda?.includes(i) && typeof v === "number" ? pesos(v) : String(v)))) : [[{ content: "Sin registros en el periodo", colSpan: r.columnas.length }]],
    theme: "striped",
    headStyles: { fillColor: VERDE },
    styles: { fontSize: 8.5 },
    didDrawPage: () => {
      const n = doc.getNumberOfPages();
      doc.setFontSize(8);
      doc.setTextColor(140, 140, 140);
      doc.text(`Página ${n}`, ancho - 70, doc.internal.pageSize.getHeight() - 20);
    },
  });
  bajar(doc.output("blob"), `${r.archivo}.pdf`);
}

export async function descargarExcel(r: Reporte) {
  const wb = new ExcelJS.Workbook();
  wb.creator = "Alojamientos LR";
  wb.created = new Date();

  const ws = wb.addWorksheet("Detalle", { views: [{ state: "frozen", ySplit: 1 }] });
  ws.addRow(r.columnas);
  r.filas.forEach((f) => ws.addRow(f));
  const cab = ws.getRow(1);
  cab.font = { bold: true, color: { argb: "FFFFFFFF" } };
  cab.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF0F766E" } };
  ws.columns.forEach((c, i) => {
    const largo = Math.max(r.columnas[i].length, ...r.filas.map((f) => String(f[i] ?? "").length + 3));
    c.width = Math.min(48, largo + 3);
  });
  (r.moneda ?? []).forEach((i) => { ws.getColumn(i + 1).numFmt = '"$"#,##0'; });
  ws.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: r.columnas.length } };

  const rs = wb.addWorksheet("Resumen");
  rs.addRow([r.titulo]).font = { bold: true, size: 14 };
  rs.addRow([`Periodo: ${r.periodo}`]);
  rs.addRow([`Generado por: ${r.generadoPor} · ${ahora()}`]);
  rs.addRow([]);
  const h = rs.addRow(["Indicador", "Valor"]);
  h.font = { bold: true, color: { argb: "FFFFFFFF" } };
  h.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF0F766E" } };
  r.resumen.forEach(([k, v]) => rs.addRow([k, v]));
  rs.getColumn(1).width = 42;
  rs.getColumn(2).width = 22;

  const buf = await wb.xlsx.writeBuffer();
  bajar(new Blob([buf], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }), `${r.archivo}.xlsx`);
}
