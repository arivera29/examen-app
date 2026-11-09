/**
 * Exportación de pizarras a PNG y PDF sin dependencias externas.
 * El PDF se arma a mano: una página con la pizarra embebida como imagen JPEG (DCTDecode).
 */

export type PdfPageSize = 'a4' | 'fit';

const A4_SHORT = 595.28;
const A4_LONG = 841.89;
const PX_TO_PT = 0.75;

export function safeFileName(name: string, extension: string): string {
  const base =
    name
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-zA-Z0-9-_ ]+/g, '')
      .trim()
      .replace(/\s+/g, '_') || 'pizarra';
  return `${base}.${extension}`;
}

export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function canvasToPngBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('No se pudo generar el PNG'))), 'image/png');
  });
}

function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function hexToRgbOperands(hex: string): string {
  const value = hex.replace('#', '');
  const parse = (i: number) => (parseInt(value.slice(i, i + 2), 16) / 255).toFixed(4);
  return value.length === 6 ? `${parse(0)} ${parse(2)} ${parse(4)}` : '1 1 1';
}

/** Cadena PDF en UTF-16BE (hex) para admitir tildes y ñ en los metadatos. */
function pdfTextString(text: string): string {
  let hex = 'FEFF';
  for (let i = 0; i < text.length; i++) {
    hex += text.charCodeAt(i).toString(16).padStart(4, '0').toUpperCase();
  }
  return `<${hex}>`;
}

function fmt(n: number): string {
  return Number(n.toFixed(2)).toString();
}

/**
 * Construye un PDF de una página con la imagen del canvas.
 * - `a4`: página A4 (orientación según la pizarra) con la imagen centrada y márgenes.
 * - `fit`: página del mismo tamaño que la pizarra.
 */
export function buildPdfFromCanvas(
  canvas: HTMLCanvasElement,
  options: { title: string; background: string; pageSize: PdfPageSize; logicalWidth: number; logicalHeight: number },
): Blob {
  const jpeg = base64ToBytes(canvas.toDataURL('image/jpeg', 0.92).split(',')[1]);
  const landscape = options.logicalWidth >= options.logicalHeight;

  let pageW: number;
  let pageH: number;
  let drawW: number;
  let drawH: number;
  if (options.pageSize === 'fit') {
    pageW = options.logicalWidth * PX_TO_PT;
    pageH = options.logicalHeight * PX_TO_PT;
    drawW = pageW;
    drawH = pageH;
  } else {
    pageW = landscape ? A4_LONG : A4_SHORT;
    pageH = landscape ? A4_SHORT : A4_LONG;
    const margin = 24;
    const ratio = Math.min((pageW - margin * 2) / options.logicalWidth, (pageH - margin * 2) / options.logicalHeight);
    drawW = options.logicalWidth * ratio;
    drawH = options.logicalHeight * ratio;
  }
  const offsetX = (pageW - drawW) / 2;
  const offsetY = (pageH - drawH) / 2;

  const content =
    `q ${hexToRgbOperands(options.background)} rg 0 0 ${fmt(pageW)} ${fmt(pageH)} re f Q\n` +
    `q ${fmt(drawW)} 0 0 ${fmt(drawH)} ${fmt(offsetX)} ${fmt(offsetY)} cm /Im0 Do Q\n`;

  const encoder = new TextEncoder();
  const chunks: Uint8Array[] = [];
  const offsets: number[] = [];
  let length = 0;
  const push = (data: string | Uint8Array) => {
    const bytes = typeof data === 'string' ? encoder.encode(data) : data;
    chunks.push(bytes);
    length += bytes.length;
  };
  const startObject = (id: number) => {
    offsets[id] = length;
    push(`${id} 0 obj\n`);
  };

  push('%PDF-1.4\n');
  push(new Uint8Array([0x25, 0xe2, 0xe3, 0xcf, 0xd3, 0x0a]));

  startObject(1);
  push('<< /Type /Catalog /Pages 2 0 R >>\nendobj\n');

  startObject(2);
  push('<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n');

  startObject(3);
  push(
    `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${fmt(pageW)} ${fmt(pageH)}] ` +
      '/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>\nendobj\n',
  );

  startObject(4);
  push(
    `<< /Type /XObject /Subtype /Image /Width ${canvas.width} /Height ${canvas.height} ` +
      `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`,
  );
  push(jpeg);
  push('\nendstream\nendobj\n');

  const contentBytes = encoder.encode(content);
  startObject(5);
  push(`<< /Length ${contentBytes.length} >>\nstream\n`);
  push(contentBytes);
  push('endstream\nendobj\n');

  startObject(6);
  push(`<< /Title ${pdfTextString(options.title)} /Producer (Examen App - Pizarras) >>\nendobj\n`);

  const xrefOffset = length;
  let xref = `xref\n0 7\n0000000000 65535 f \n`;
  for (let id = 1; id <= 6; id++) {
    xref += `${offsets[id].toString().padStart(10, '0')} 00000 n \n`;
  }
  push(xref);
  push(`trailer\n<< /Size 7 /Root 1 0 R /Info 6 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`);

  return new Blob(chunks as BlobPart[], { type: 'application/pdf' });
}
