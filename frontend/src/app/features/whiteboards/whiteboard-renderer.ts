import {
  Bounds,
  FreehandElement,
  HIGHLIGHTER_OPACITY,
  LineStyle,
  ShapeElement,
  TextElement,
  WhiteboardElement,
  isFreehand,
  isLinear,
  isShape,
} from './whiteboard.models';

type Ctx = CanvasRenderingContext2D;

const TEXT_LINE_HEIGHT = 1.25;
let measureCtx: Ctx | null = null;

function getMeasureCtx(): Ctx {
  if (!measureCtx) {
    measureCtx = document.createElement('canvas').getContext('2d')!;
  }
  return measureCtx;
}

export function textFont(el: Pick<TextElement, 'fontSize' | 'fontFamily' | 'bold' | 'italic'>): string {
  return `${el.italic ? 'italic ' : ''}${el.bold ? 'bold ' : ''}${el.fontSize}px ${el.fontFamily}`;
}

export function measureText(el: Pick<TextElement, 'text' | 'fontSize' | 'fontFamily' | 'bold' | 'italic'>): {
  w: number;
  h: number;
} {
  const ctx = getMeasureCtx();
  ctx.font = textFont(el);
  const lines = el.text.split('\n');
  const w = Math.max(...lines.map((line) => ctx.measureText(line || ' ').width));
  return { w, h: lines.length * el.fontSize * TEXT_LINE_HEIGHT };
}

export function normalizedBox(el: { x1: number; y1: number; x2: number; y2: number }): Bounds {
  return {
    x: Math.min(el.x1, el.x2),
    y: Math.min(el.y1, el.y2),
    w: Math.abs(el.x2 - el.x1),
    h: Math.abs(el.y2 - el.y1),
  };
}

function polygonFor(el: ShapeElement): [number, number][] {
  const { x, y, w, h } = normalizedBox(el);
  if (el.type === 'triangle') {
    return [
      [x + w / 2, y],
      [x + w, y + h],
      [x, y + h],
    ];
  }
  if (el.type === 'diamond') {
    return [
      [x + w / 2, y],
      [x + w, y + h / 2],
      [x + w / 2, y + h],
      [x, y + h / 2],
    ];
  }
  return [
    [x, y],
    [x + w, y],
    [x + w, y + h],
    [x, y + h],
  ];
}

function applyLineStyle(ctx: Ctx, style: LineStyle, width: number): void {
  if (style === 'dashed') {
    ctx.setLineDash([width * 4, width * 3]);
    ctx.lineCap = 'butt';
  } else if (style === 'dotted') {
    ctx.setLineDash([0.1, width * 2.5]);
    ctx.lineCap = 'round';
  } else {
    ctx.setLineDash([]);
    ctx.lineCap = 'round';
  }
}

function drawFreehand(ctx: Ctx, el: FreehandElement): void {
  const pts = el.points;
  if (pts.length < 2) return;
  ctx.globalAlpha = el.type === 'highlighter' ? HIGHLIGHTER_OPACITY : el.opacity;
  if (el.type === 'eraser') {
    ctx.globalCompositeOperation = 'destination-out';
    ctx.globalAlpha = 1;
  }
  ctx.strokeStyle = el.color;
  ctx.fillStyle = el.color;
  ctx.lineWidth = el.width;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.setLineDash([]);

  if (pts.length === 2) {
    ctx.beginPath();
    ctx.arc(pts[0], pts[1], el.width / 2, 0, Math.PI * 2);
    ctx.fill();
    return;
  }

  ctx.beginPath();
  ctx.moveTo(pts[0], pts[1]);
  if (pts.length === 4) {
    ctx.lineTo(pts[2], pts[3]);
  } else {
    // Curvas cuadráticas entre puntos medios para suavizar el trazo.
    for (let i = 2; i < pts.length - 2; i += 2) {
      const midX = (pts[i] + pts[i + 2]) / 2;
      const midY = (pts[i + 1] + pts[i + 3]) / 2;
      ctx.quadraticCurveTo(pts[i], pts[i + 1], midX, midY);
    }
    ctx.lineTo(pts[pts.length - 2], pts[pts.length - 1]);
  }
  ctx.stroke();
}

function drawArrowHead(ctx: Ctx, el: ShapeElement): void {
  const angle = Math.atan2(el.y2 - el.y1, el.x2 - el.x1);
  const size = Math.max(12, el.width * 3.5);
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.moveTo(el.x2, el.y2);
  ctx.lineTo(el.x2 - size * Math.cos(angle - Math.PI / 7), el.y2 - size * Math.sin(angle - Math.PI / 7));
  ctx.lineTo(el.x2 - size * Math.cos(angle + Math.PI / 7), el.y2 - size * Math.sin(angle + Math.PI / 7));
  ctx.closePath();
  ctx.fillStyle = el.stroke;
  ctx.fill();
}

function drawShape(ctx: Ctx, el: ShapeElement): void {
  ctx.globalAlpha = el.opacity;
  ctx.strokeStyle = el.stroke;
  ctx.lineWidth = el.width;
  ctx.lineJoin = 'round';
  applyLineStyle(ctx, el.lineStyle, el.width);

  if (isLinear(el.type)) {
    ctx.beginPath();
    ctx.moveTo(el.x1, el.y1);
    if (el.type === 'arrow') {
      // Acorta la línea para que no sobresalga de la punta.
      const angle = Math.atan2(el.y2 - el.y1, el.x2 - el.x1);
      const inset = Math.max(12, el.width * 3.5) * 0.6;
      const len = Math.hypot(el.x2 - el.x1, el.y2 - el.y1);
      const d = Math.min(inset, len);
      ctx.lineTo(el.x2 - d * Math.cos(angle), el.y2 - d * Math.sin(angle));
    } else {
      ctx.lineTo(el.x2, el.y2);
    }
    ctx.stroke();
    if (el.type === 'arrow') drawArrowHead(ctx, el);
    return;
  }

  ctx.beginPath();
  if (el.type === 'ellipse') {
    const { x, y, w, h } = normalizedBox(el);
    ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
  } else {
    const poly = polygonFor(el);
    ctx.moveTo(poly[0][0], poly[0][1]);
    for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
    ctx.closePath();
  }
  if (el.fill) {
    ctx.fillStyle = el.fill;
    ctx.fill();
  }
  if (el.width > 0) ctx.stroke();
}

function drawText(ctx: Ctx, el: TextElement): void {
  ctx.globalAlpha = el.opacity;
  ctx.fillStyle = el.color;
  ctx.font = textFont(el);
  ctx.textBaseline = 'top';
  const lineHeight = el.fontSize * TEXT_LINE_HEIGHT;
  const offset = (lineHeight - el.fontSize) / 2;
  el.text.split('\n').forEach((line, index) => {
    ctx.fillText(line, el.x, el.y + offset + index * lineHeight);
  });
}

export function drawElement(ctx: Ctx, el: WhiteboardElement): void {
  ctx.save();
  if (isFreehand(el)) drawFreehand(ctx, el);
  else if (isShape(el)) drawShape(ctx, el);
  else drawText(ctx, el);
  ctx.restore();
}

/**
 * Dibuja los elementos sobre una capa transparente. Los trazos de borrador
 * usan `destination-out`, por lo que solo borran tinta y nunca el fondo.
 */
export function renderLayer(
  layer: HTMLCanvasElement,
  elements: WhiteboardElement[],
  width: number,
  height: number,
  scale: number,
  hiddenId: string | null = null,
): void {
  const pxW = Math.max(1, Math.round(width * scale));
  const pxH = Math.max(1, Math.round(height * scale));
  if (layer.width !== pxW) layer.width = pxW;
  if (layer.height !== pxH) layer.height = pxH;
  const ctx = layer.getContext('2d')!;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, pxW, pxH);
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  for (const el of elements) {
    if (el.id !== hiddenId) drawElement(ctx, el);
  }
}

/** Renderiza la pizarra completa (fondo + elementos) en un canvas nuevo. */
export function renderBoardToCanvas(
  elements: WhiteboardElement[],
  width: number,
  height: number,
  background: string | null,
  scale = 1,
): HTMLCanvasElement {
  const layer = document.createElement('canvas');
  renderLayer(layer, elements, width, height, scale);
  const out = document.createElement('canvas');
  out.width = layer.width;
  out.height = layer.height;
  const ctx = out.getContext('2d')!;
  if (background) {
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, out.width, out.height);
  }
  ctx.drawImage(layer, 0, 0);
  return out;
}

export function getBounds(el: WhiteboardElement): Bounds {
  if (isFreehand(el)) {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (let i = 0; i < el.points.length; i += 2) {
      minX = Math.min(minX, el.points[i]);
      maxX = Math.max(maxX, el.points[i]);
      minY = Math.min(minY, el.points[i + 1]);
      maxY = Math.max(maxY, el.points[i + 1]);
    }
    const pad = el.width / 2;
    return { x: minX - pad, y: minY - pad, w: maxX - minX + pad * 2, h: maxY - minY + pad * 2 };
  }
  if (isShape(el)) {
    const box = normalizedBox(el);
    const pad = el.width / 2;
    return { x: box.x - pad, y: box.y - pad, w: box.w + pad * 2, h: box.h + pad * 2 };
  }
  const size = measureText(el);
  return { x: el.x, y: el.y, w: size.w, h: size.h };
}

function distToSegment(px: number, py: number, x1: number, y1: number, x2: number, y2: number): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const lenSq = dx * dx + dy * dy;
  let t = lenSq === 0 ? 0 : ((px - x1) * dx + (py - y1) * dy) / lenSq;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

function pointInPolygon(x: number, y: number, poly: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function nearPolygonEdge(x: number, y: number, poly: [number, number][], tol: number): boolean {
  for (let i = 0; i < poly.length; i++) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    if (distToSegment(x, y, x1, y1, x2, y2) <= tol) return true;
  }
  return false;
}

/** Indica si el punto (x, y) toca el elemento, con una tolerancia en unidades del lienzo. */
export function hitTest(el: WhiteboardElement, x: number, y: number, tolerance: number): boolean {
  if (el.type === 'eraser') return false;

  if (isFreehand(el)) {
    const tol = el.width / 2 + tolerance;
    const pts = el.points;
    if (pts.length === 2) return Math.hypot(x - pts[0], y - pts[1]) <= tol;
    for (let i = 0; i < pts.length - 2; i += 2) {
      if (distToSegment(x, y, pts[i], pts[i + 1], pts[i + 2], pts[i + 3]) <= tol) return true;
    }
    return false;
  }

  if (isShape(el)) {
    const tol = el.width / 2 + tolerance;
    if (isLinear(el.type)) return distToSegment(x, y, el.x1, el.y1, el.x2, el.y2) <= tol;
    if (el.type === 'ellipse') {
      const { x: bx, y: by, w, h } = normalizedBox(el);
      const rx = Math.max(w / 2, 0.5);
      const ry = Math.max(h / 2, 0.5);
      const d = Math.hypot((x - (bx + rx)) / rx, (y - (by + ry)) / ry);
      if (el.fill && d <= 1) return true;
      return Math.abs(d - 1) * Math.min(rx, ry) <= tol;
    }
    const poly = polygonFor(el);
    if (el.fill && pointInPolygon(x, y, poly)) return true;
    return nearPolygonEdge(x, y, poly, tol);
  }

  const b = getBounds(el);
  return x >= b.x - tolerance && x <= b.x + b.w + tolerance && y >= b.y - tolerance && y <= b.y + b.h + tolerance;
}

export function translateElement<T extends WhiteboardElement>(el: T, dx: number, dy: number): T {
  if (isFreehand(el)) {
    return { ...el, points: el.points.map((v, i) => (i % 2 === 0 ? v + dx : v + dy)) };
  }
  if (isShape(el)) {
    return { ...el, x1: el.x1 + dx, y1: el.y1 + dy, x2: el.x2 + dx, y2: el.y2 + dy };
  }
  return { ...el, x: (el as TextElement).x + dx, y: (el as TextElement).y + dy };
}

/** Restringe formas a proporción 1:1 y líneas a múltiplos de 45° (tecla Shift). */
export function constrainPoint(
  type: string,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): { x: number; y: number } {
  const dx = x2 - x1;
  const dy = y2 - y1;
  if (isLinear(type)) {
    const angle = Math.round(Math.atan2(dy, dx) / (Math.PI / 4)) * (Math.PI / 4);
    const len = Math.hypot(dx, dy);
    return { x: x1 + len * Math.cos(angle), y: y1 + len * Math.sin(angle) };
  }
  const size = Math.max(Math.abs(dx), Math.abs(dy));
  return { x: x1 + size * Math.sign(dx || 1), y: y1 + size * Math.sign(dy || 1) };
}

export function drawGrid(ctx: Ctx, width: number, height: number, background: string, step = 40): void {
  ctx.save();
  ctx.strokeStyle = isDarkColor(background) ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let x = step; x < width; x += step) {
    ctx.moveTo(x + 0.5, 0);
    ctx.lineTo(x + 0.5, height);
  }
  for (let y = step; y < height; y += step) {
    ctx.moveTo(0, y + 0.5);
    ctx.lineTo(width, y + 0.5);
  }
  ctx.stroke();
  ctx.restore();
}

export function isDarkColor(hex: string): boolean {
  const value = hex.replace('#', '');
  if (value.length !== 6) return false;
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 < 128;
}

/** Convierte el contenido guardado en elementos válidos, descartando entradas mal formadas. */
export function sanitizeElements(raw: unknown[]): WhiteboardElement[] {
  return (raw || []).filter((item): item is WhiteboardElement => {
    if (!item || typeof item !== 'object') return false;
    const el = item as Record<string, unknown>;
    if (typeof el['id'] !== 'string' || typeof el['type'] !== 'string') return false;
    if (['pen', 'highlighter', 'eraser'].includes(el['type'] as string)) return Array.isArray(el['points']);
    if (el['type'] === 'text') return typeof el['text'] === 'string';
    return ['x1', 'y1', 'x2', 'y2'].every((k) => typeof el[k] === 'number');
  });
}
