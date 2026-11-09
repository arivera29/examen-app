export type DrawTool =
  | 'select'
  | 'pen'
  | 'highlighter'
  | 'eraser'
  | 'line'
  | 'arrow'
  | 'rect'
  | 'ellipse'
  | 'triangle'
  | 'diamond'
  | 'text';

export type FreehandType = 'pen' | 'highlighter' | 'eraser';
export type ShapeType = 'line' | 'arrow' | 'rect' | 'ellipse' | 'triangle' | 'diamond';
export type LineStyle = 'solid' | 'dashed' | 'dotted';
export type EraserMode = 'stroke' | 'object';

export interface FreehandElement {
  id: string;
  type: FreehandType;
  /** Coordenadas aplanadas [x0, y0, x1, y1, ...] en unidades del lienzo. */
  points: number[];
  color: string;
  width: number;
  opacity: number;
}

export interface ShapeElement {
  id: string;
  type: ShapeType;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  stroke: string;
  /** Color de relleno; null = sin relleno. No aplica a líneas ni flechas. */
  fill: string | null;
  width: number;
  lineStyle: LineStyle;
  opacity: number;
}

export interface TextElement {
  id: string;
  type: 'text';
  x: number;
  y: number;
  text: string;
  color: string;
  fontSize: number;
  fontFamily: string;
  bold: boolean;
  italic: boolean;
  opacity: number;
}

export type WhiteboardElement = FreehandElement | ShapeElement | TextElement;

export interface Bounds {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface ToolStyle {
  strokeColor: string;
  fillColor: string;
  fillEnabled: boolean;
  strokeWidth: number;
  lineStyle: LineStyle;
  opacity: number;
  penWidth: number;
  highlighterColor: string;
  highlighterWidth: number;
  eraserSize: number;
  eraserMode: EraserMode;
  textColor: string;
  fontSize: number;
  fontFamily: string;
  bold: boolean;
  italic: boolean;
}

export const DEFAULT_TOOL_STYLE: ToolStyle = {
  strokeColor: '#1e1e1e',
  fillColor: '#90caf9',
  fillEnabled: false,
  strokeWidth: 3,
  lineStyle: 'solid',
  opacity: 1,
  penWidth: 3,
  highlighterColor: '#ffeb3b',
  highlighterWidth: 20,
  eraserSize: 24,
  eraserMode: 'stroke',
  textColor: '#1e1e1e',
  fontSize: 28,
  fontFamily: 'Roboto, Arial, sans-serif',
  bold: false,
  italic: false,
};

export const HIGHLIGHTER_OPACITY = 0.35;

export const COLOR_PRESETS = [
  '#1e1e1e',
  '#ffffff',
  '#9e9e9e',
  '#e53935',
  '#fb8c00',
  '#fdd835',
  '#43a047',
  '#00897b',
  '#1e88e5',
  '#3949ab',
  '#8e24aa',
  '#d81b60',
  '#6d4c41',
];

export const BACKGROUND_PRESETS = [
  { label: 'Blanco', value: '#ffffff' },
  { label: 'Marfil', value: '#fdf6e3' },
  { label: 'Gris claro', value: '#eceff1' },
  { label: 'Verde pizarra', value: '#2e4a3a' },
  { label: 'Azul noche', value: '#1a2433' },
  { label: 'Negro', value: '#121212' },
];

export const FONT_FAMILIES = [
  { label: 'Roboto', value: 'Roboto, Arial, sans-serif' },
  { label: 'Serif', value: 'Georgia, "Times New Roman", serif' },
  { label: 'Monoespaciada', value: '"Courier New", Consolas, monospace' },
  { label: 'Manuscrita', value: '"Comic Sans MS", "Segoe Print", cursive' },
];

export const CANVAS_SIZE_PRESETS = [
  { label: 'Panorámico 16:9 (1920 × 1080)', width: 1920, height: 1080 },
  { label: 'Estándar 4:3 (1600 × 1200)', width: 1600, height: 1200 },
  { label: 'A4 horizontal (1754 × 1240)', width: 1754, height: 1240 },
  { label: 'A4 vertical (1240 × 1754)', width: 1240, height: 1754 },
  { label: 'Cuadrado (1500 × 1500)', width: 1500, height: 1500 },
];

export function isFreehand(el: WhiteboardElement): el is FreehandElement {
  return el.type === 'pen' || el.type === 'highlighter' || el.type === 'eraser';
}

export function isShape(el: WhiteboardElement): el is ShapeElement {
  return (
    el.type === 'line' ||
    el.type === 'arrow' ||
    el.type === 'rect' ||
    el.type === 'ellipse' ||
    el.type === 'triangle' ||
    el.type === 'diamond'
  );
}

export function isText(el: WhiteboardElement): el is TextElement {
  return el.type === 'text';
}

export function isLinear(type: string): boolean {
  return type === 'line' || type === 'arrow';
}

export function createId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
