import {
  AfterViewInit,
  Component,
  ElementRef,
  HostListener,
  NgZone,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
} from '@angular/core';
import { NgStyle, NgTemplateOutlet } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatSliderModule } from '@angular/material/slider';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../../core/services/api.service';
import {
  BACKGROUND_PRESETS,
  COLOR_PRESETS,
  DEFAULT_TOOL_STYLE,
  DrawTool,
  FONT_FAMILIES,
  FreehandElement,
  LineStyle,
  ShapeElement,
  ShapeType,
  TextElement,
  ToolStyle,
  WhiteboardElement,
  createId,
  isFreehand,
  isLinear,
  isShape,
  isText,
} from '../whiteboard.models';
import {
  constrainPoint,
  drawElement,
  drawGrid,
  getBounds,
  hitTest,
  isDarkColor,
  measureText,
  renderBoardToCanvas,
  renderLayer,
  sanitizeElements,
  translateElement,
} from '../whiteboard-renderer';
import { PdfPageSize, buildPdfFromCanvas, canvasToPngBlob, downloadBlob, safeFileName } from '../whiteboard-export';

type SaveState = 'saved' | 'dirty' | 'saving' | 'error';
type PanelKind = 'pen' | 'highlighter' | 'eraser' | 'shape' | 'line' | 'text' | 'none';
type PointerMode = 'none' | 'draw' | 'shape' | 'move' | 'resize' | 'erase-object' | 'pan';

interface Snapshot {
  elements: string;
  background: string;
}

interface TextEditorState {
  x: number;
  y: number;
  value: string;
  editingId: string | null;
}

interface ToolDef {
  id: DrawTool;
  icon: string;
  label: string;
  shortcut: string;
}

const STYLE_STORAGE_KEY = 'whiteboard-tool-style';
const AUTOSAVE_DELAY_MS = 1500;
const HISTORY_LIMIT = 100;
const MIN_ZOOM = 0.1;
const MAX_ZOOM = 4;
const EXPORT_MAX_PIXELS = 16_000_000;

@Component({
  selector: 'app-whiteboard-editor',
  standalone: true,
  imports: [
    NgStyle,
    NgTemplateOutlet,
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatButtonToggleModule,
    MatDividerModule,
    MatIconModule,
    MatMenuModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatSliderModule,
    MatSnackBarModule,
    MatTooltipModule,
  ],
  templateUrl: './whiteboard-editor.component.html',
  styleUrl: './whiteboard-editor.component.scss',
})
export class WhiteboardEditorComponent implements OnInit, AfterViewInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);
  private readonly zone = inject(NgZone);

  @ViewChild('viewport') viewportRef?: ElementRef<HTMLDivElement>;
  @ViewChild('canvas') canvasRef?: ElementRef<HTMLCanvasElement>;
  @ViewChild('textInput') textInputRef?: ElementRef<HTMLTextAreaElement>;

  readonly colorPresets = COLOR_PRESETS;
  readonly backgroundPresets = BACKGROUND_PRESETS;
  readonly fontFamilies = FONT_FAMILIES;
  readonly lineStyles: { value: LineStyle; label: string }[] = [
    { value: 'solid', label: 'Continua' },
    { value: 'dashed', label: 'Discontinua' },
    { value: 'dotted', label: 'Punteada' },
  ];
  readonly drawingTools: ToolDef[] = [
    { id: 'select', icon: 'near_me', label: 'Seleccionar y mover', shortcut: 'V' },
    { id: 'pen', icon: 'edit', label: 'Lápiz', shortcut: 'P' },
    { id: 'highlighter', icon: 'border_color', label: 'Resaltador', shortcut: 'H' },
    { id: 'eraser', icon: 'eraser', label: 'Borrador', shortcut: 'E' },
    { id: 'text', icon: 'title', label: 'Texto', shortcut: 'T' },
  ];
  readonly shapeTools: ToolDef[] = [
    { id: 'line', icon: 'horizontal_rule', label: 'Línea', shortcut: 'L' },
    { id: 'arrow', icon: 'arrow_right_alt', label: 'Flecha', shortcut: 'A' },
    { id: 'rect', icon: 'crop_square', label: 'Rectángulo', shortcut: 'R' },
    { id: 'ellipse', icon: 'radio_button_unchecked', label: 'Elipse', shortcut: 'O' },
    { id: 'triangle', icon: 'change_history', label: 'Triángulo', shortcut: 'G' },
    { id: 'diamond', icon: 'crop_square', label: 'Rombo', shortcut: 'D' },
  ];

  whiteboardId = '';
  name = '';
  private savedName = '';
  background = '#ffffff';
  boardWidth = 1920;
  boardHeight = 1080;
  elements: WhiteboardElement[] = [];
  loading = true;

  tool: DrawTool = 'pen';
  style: ToolStyle = { ...DEFAULT_TOOL_STYLE };
  selectedId: string | null = null;
  showGrid = false;
  scale = 1;
  private fitMode = true;

  saveState: SaveState = 'saved';
  textEditor: TextEditorState | null = null;

  private undoStack: Snapshot[] = [];
  private redoStack: Snapshot[] = [];
  private pendingSnapshot: Snapshot | null = null;
  private lastStyleHistory = { id: '', at: 0 };

  private readonly layerCanvas = document.createElement('canvas');
  private readonly workCanvas = document.createElement('canvas');
  private hiddenId: string | null = null;
  private draft: WhiteboardElement | null = null;
  private pointerMode: PointerMode = 'none';
  private pointerStart = { x: 0, y: 0 };
  private originalElement: WhiteboardElement | null = null;
  private resizeHandle: 1 | 2 = 2;
  private changedDuringPointer = false;
  private hoverPoint: { x: number; y: number } | null = null;
  private panStart = { x: 0, y: 0, left: 0, top: 0 };

  private autosaveTimer: ReturnType<typeof setTimeout> | null = null;
  private changeVersion = 0;
  private saveInFlight = false;
  private resizeObserver?: ResizeObserver;

  ngOnInit(): void {
    this.restoreToolStyle();
    this.whiteboardId = this.route.snapshot.paramMap.get('id') ?? '';
    this.api.getWhiteboard(this.whiteboardId).subscribe({
      next: (whiteboard) => {
        this.name = whiteboard.name;
        this.savedName = whiteboard.name;
        this.background = whiteboard.background_color;
        this.boardWidth = whiteboard.width;
        this.boardHeight = whiteboard.height;
        this.elements = sanitizeElements(whiteboard.content);
        this.loading = false;
        setTimeout(() => this.fitToScreen());
      },
      error: (err) => {
        this.snackBar.open(err.error?.detail || 'No se pudo cargar la pizarra', 'Cerrar', { duration: 4000 });
        this.router.navigate(['/dashboard/whiteboards']);
      },
    });
  }

  ngAfterViewInit(): void {
    this.zone.runOutsideAngular(() => {
      this.resizeObserver = new ResizeObserver(() => {
        if (this.fitMode && !this.loading) this.zone.run(() => this.fitToScreen());
      });
      if (this.viewportRef) this.resizeObserver.observe(this.viewportRef.nativeElement);
    });
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
    if (this.autosaveTimer) clearTimeout(this.autosaveTimer);
    if (this.textEditor) this.commitText();
    if (this.saveState === 'dirty' || this.saveState === 'error') this.save(true);
  }

  // ---------------------------------------------------------------------------
  // Estado derivado para la plantilla
  // ---------------------------------------------------------------------------

  get selectedElement(): WhiteboardElement | null {
    return this.selectedId ? (this.elements.find((el) => el.id === this.selectedId) ?? null) : null;
  }

  get panelKind(): PanelKind {
    const selected = this.tool === 'select' ? this.selectedElement : null;
    const type = selected ? selected.type : this.tool;
    if (type === 'pen' || type === 'highlighter' || type === 'eraser' || type === 'text') return type;
    if (type === 'line' || type === 'arrow') return 'line';
    if (type === 'rect' || type === 'ellipse' || type === 'triangle' || type === 'diamond') return 'shape';
    return 'none';
  }

  get canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  get zoomPercent(): number {
    return Math.round(this.scale * 100);
  }

  get canvasCssWidth(): number {
    return this.boardWidth * this.scale;
  }

  get canvasCssHeight(): number {
    return this.boardHeight * this.scale;
  }

  get viewportIsDark(): boolean {
    return isDarkColor(this.background);
  }

  get cursorClass(): string {
    if (this.tool === 'select') return this.pointerMode === 'pan' ? 'cursor-grabbing' : 'cursor-default';
    if (this.tool === 'text') return 'cursor-text';
    if (this.tool === 'eraser') return 'cursor-none';
    return 'cursor-crosshair';
  }

  get saveLabel(): string {
    switch (this.saveState) {
      case 'saving':
        return 'Guardando…';
      case 'dirty':
        return 'Cambios sin guardar';
      case 'error':
        return 'Error al guardar';
      default:
        return 'Guardado';
    }
  }

  get textEditorStyle(): Record<string, string> {
    if (!this.textEditor) return {};
    const size = measureText({ ...this.style, fontSize: this.style.fontSize, text: this.textEditor.value || ' ' });
    return {
      left: `${this.textEditor.x * this.scale}px`,
      top: `${this.textEditor.y * this.scale}px`,
      width: `${(size.w + this.style.fontSize) * this.scale}px`,
      height: `${size.h * this.scale + 4}px`,
      'font-size': `${this.style.fontSize * this.scale}px`,
      'font-family': this.style.fontFamily,
      'font-weight': this.style.bold ? '700' : '400',
      'font-style': this.style.italic ? 'italic' : 'normal',
      color: this.style.textColor,
      opacity: String(this.style.opacity),
    };
  }

  // ---------------------------------------------------------------------------
  // Herramientas y estilos
  // ---------------------------------------------------------------------------

  setTool(tool: DrawTool): void {
    if (this.textEditor) this.commitText();
    this.tool = tool;
    if (tool !== 'select') this.selectedId = null;
    this.hoverPoint = null;
    this.render();
  }

  isShapeToolActive(): boolean {
    return this.shapeTools.some((t) => t.id === this.tool);
  }

  pickColor(field: 'strokeColor' | 'fillColor' | 'textColor' | 'highlighterColor', color: string): void {
    this.style[field] = color;
    if (field === 'fillColor') this.style.fillEnabled = true;
    this.onStyleChange();
  }

  setStyleValue(field: keyof ToolStyle, value: unknown): void {
    (this.style as unknown as Record<string, unknown>)[field] = value;
    this.onStyleChange();
  }

  onStyleChange(): void {
    this.persistToolStyle();
    if (this.textEditor) return;
    const selected = this.tool === 'select' ? this.selectedElement : null;
    if (!selected) return;
    const updated = this.applyStyleTo(selected);
    if (JSON.stringify(updated) === JSON.stringify(selected)) return;

    const now = Date.now();
    if (this.lastStyleHistory.id !== selected.id || now - this.lastStyleHistory.at > 800) {
      this.pushHistory();
    }
    this.lastStyleHistory = { id: selected.id, at: now };
    this.replaceElement(updated);
    this.invalidateLayer();
    this.markDirty();
  }

  private applyStyleTo(el: WhiteboardElement): WhiteboardElement {
    const s = this.style;
    if (isFreehand(el)) {
      if (el.type === 'highlighter') return { ...el, color: s.highlighterColor, width: s.highlighterWidth };
      if (el.type === 'pen') return { ...el, color: s.strokeColor, width: s.penWidth, opacity: s.opacity };
      return el;
    }
    if (isShape(el)) {
      return {
        ...el,
        stroke: s.strokeColor,
        fill: isLinear(el.type) ? null : s.fillEnabled ? s.fillColor : null,
        width: s.strokeWidth,
        lineStyle: s.lineStyle,
        opacity: s.opacity,
      };
    }
    return {
      ...el,
      color: s.textColor,
      fontSize: s.fontSize,
      fontFamily: s.fontFamily,
      bold: s.bold,
      italic: s.italic,
      opacity: s.opacity,
    };
  }

  private loadStyleFrom(el: WhiteboardElement): void {
    const s = this.style;
    if (isFreehand(el)) {
      if (el.type === 'highlighter') {
        s.highlighterColor = el.color;
        s.highlighterWidth = el.width;
      } else if (el.type === 'pen') {
        s.strokeColor = el.color;
        s.penWidth = el.width;
        s.opacity = el.opacity;
      }
    } else if (isShape(el)) {
      s.strokeColor = el.stroke;
      s.strokeWidth = el.width;
      s.lineStyle = el.lineStyle;
      s.opacity = el.opacity;
      if (!isLinear(el.type)) {
        s.fillEnabled = el.fill !== null;
        if (el.fill) s.fillColor = el.fill;
      }
    } else {
      s.textColor = el.color;
      s.fontSize = el.fontSize;
      s.fontFamily = el.fontFamily;
      s.bold = el.bold;
      s.italic = el.italic;
      s.opacity = el.opacity;
    }
  }

  private persistToolStyle(): void {
    try {
      localStorage.setItem(STYLE_STORAGE_KEY, JSON.stringify(this.style));
    } catch {
      // El almacenamiento local es opcional.
    }
  }

  private restoreToolStyle(): void {
    try {
      const raw = localStorage.getItem(STYLE_STORAGE_KEY);
      if (raw) this.style = { ...DEFAULT_TOOL_STYLE, ...JSON.parse(raw) };
    } catch {
      this.style = { ...DEFAULT_TOOL_STYLE };
    }
  }

  // ---------------------------------------------------------------------------
  // Renderizado
  // ---------------------------------------------------------------------------

  private get renderScale(): number {
    return Math.min(Math.max(this.scale * (window.devicePixelRatio || 1), 0.25), 3);
  }

  private invalidateLayer(): void {
    renderLayer(this.layerCanvas, this.elements, this.boardWidth, this.boardHeight, this.renderScale, this.hiddenId);
    this.render();
  }

  render(): void {
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas) return;
    const rs = this.renderScale;
    const pxW = Math.round(this.boardWidth * rs);
    const pxH = Math.round(this.boardHeight * rs);
    if (canvas.width !== pxW || canvas.height !== pxH) {
      canvas.width = pxW;
      canvas.height = pxH;
    }
    if (this.layerCanvas.width !== pxW || this.layerCanvas.height !== pxH) {
      renderLayer(this.layerCanvas, this.elements, this.boardWidth, this.boardHeight, rs, this.hiddenId);
    }

    const ctx = canvas.getContext('2d')!;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;
    ctx.fillStyle = this.background;
    ctx.fillRect(0, 0, pxW, pxH);
    if (this.showGrid) {
      ctx.setTransform(rs, 0, 0, rs, 0, 0);
      drawGrid(ctx, this.boardWidth, this.boardHeight, this.background);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
    }

    if (this.draft?.type === 'eraser') {
      // Vista previa del borrador: se aplica sobre una copia de la capa para no borrar el fondo.
      this.workCanvas.width = pxW;
      this.workCanvas.height = pxH;
      const work = this.workCanvas.getContext('2d')!;
      work.drawImage(this.layerCanvas, 0, 0);
      work.setTransform(rs, 0, 0, rs, 0, 0);
      drawElement(work, this.draft);
      ctx.drawImage(this.workCanvas, 0, 0);
    } else {
      ctx.drawImage(this.layerCanvas, 0, 0);
      if (this.draft) {
        ctx.setTransform(rs, 0, 0, rs, 0, 0);
        drawElement(ctx, this.draft);
      }
    }

    ctx.setTransform(rs, 0, 0, rs, 0, 0);
    this.drawSelectionOverlay(ctx);
    this.drawEraserCursor(ctx);
  }

  private drawSelectionOverlay(ctx: CanvasRenderingContext2D): void {
    if (this.tool !== 'select' || !this.selectedId) return;
    const el = this.draft && this.draft.id === this.selectedId ? this.draft : this.selectedElement;
    if (!el) return;
    const b = getBounds(el);
    const pad = 6 / this.scale;
    ctx.save();
    ctx.strokeStyle = '#1e88e5';
    ctx.lineWidth = 1.5 / this.scale;
    ctx.setLineDash([6 / this.scale, 4 / this.scale]);
    ctx.strokeRect(b.x - pad, b.y - pad, b.w + pad * 2, b.h + pad * 2);
    ctx.setLineDash([]);
    if (isShape(el)) {
      const size = 10 / this.scale;
      ctx.fillStyle = '#ffffff';
      for (const [hx, hy] of [
        [el.x1, el.y1],
        [el.x2, el.y2],
      ]) {
        ctx.fillRect(hx - size / 2, hy - size / 2, size, size);
        ctx.strokeRect(hx - size / 2, hy - size / 2, size, size);
      }
    }
    ctx.restore();
  }

  private drawEraserCursor(ctx: CanvasRenderingContext2D): void {
    if (this.tool !== 'eraser' || !this.hoverPoint) return;
    ctx.save();
    ctx.beginPath();
    ctx.arc(this.hoverPoint.x, this.hoverPoint.y, this.style.eraserSize / 2, 0, Math.PI * 2);
    ctx.lineWidth = 1.5 / this.scale;
    ctx.strokeStyle = this.viewportIsDark ? '#ffffff' : '#424242';
    ctx.setLineDash(this.style.eraserMode === 'object' ? [4 / this.scale, 3 / this.scale] : []);
    ctx.stroke();
    ctx.restore();
  }

  toggleGrid(): void {
    this.showGrid = !this.showGrid;
    this.render();
  }

  // ---------------------------------------------------------------------------
  // Zoom
  // ---------------------------------------------------------------------------

  fitToScreen(): void {
    const viewport = this.viewportRef?.nativeElement;
    if (!viewport) return;
    const availableW = Math.max(viewport.clientWidth - 32, 100);
    const availableH = Math.max(viewport.clientHeight - 32, 100);
    this.fitMode = true;
    this.applyScale(Math.min(availableW / this.boardWidth, availableH / this.boardHeight));
  }

  zoomBy(factor: number): void {
    this.fitMode = false;
    this.applyScale(this.scale * factor);
  }

  resetZoom(): void {
    this.fitMode = false;
    this.applyScale(1);
  }

  private applyScale(scale: number): void {
    this.scale = Math.min(Math.max(scale, MIN_ZOOM), MAX_ZOOM);
    this.invalidateLayer();
  }

  onWheel(event: WheelEvent): void {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    this.zoomBy(event.deltaY < 0 ? 1.1 : 1 / 1.1);
  }

  // ---------------------------------------------------------------------------
  // Interacción con el puntero
  // ---------------------------------------------------------------------------

  private toBoard(event: PointerEvent | MouseEvent): { x: number; y: number } {
    const rect = this.canvasRef!.nativeElement.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * this.boardWidth,
      y: ((event.clientY - rect.top) / rect.height) * this.boardHeight,
    };
  }

  private findElementAt(x: number, y: number, tolerance = 6 / this.scale): WhiteboardElement | null {
    for (let i = this.elements.length - 1; i >= 0; i--) {
      if (hitTest(this.elements[i], x, y, tolerance)) return this.elements[i];
    }
    return null;
  }

  onPointerDown(event: PointerEvent): void {
    if (event.button !== 0 || this.loading) return;
    if (this.textEditor) {
      this.commitText();
      if (this.tool !== 'text') return;
    }
    const p = this.toBoard(event);
    (event.target as HTMLElement).setPointerCapture(event.pointerId);
    this.pointerStart = p;
    this.changedDuringPointer = false;
    const s = this.style;

    switch (this.tool) {
      case 'select':
        this.startSelectInteraction(event, p);
        break;
      case 'pen':
      case 'highlighter':
        this.draft = {
          id: createId(),
          type: this.tool,
          points: [round(p.x), round(p.y)],
          color: this.tool === 'pen' ? s.strokeColor : s.highlighterColor,
          width: this.tool === 'pen' ? s.penWidth : s.highlighterWidth,
          opacity: this.tool === 'pen' ? s.opacity : 1,
        };
        this.pointerMode = 'draw';
        break;
      case 'eraser':
        if (s.eraserMode === 'object') {
          this.pendingSnapshot = this.snapshot();
          this.pointerMode = 'erase-object';
          this.eraseObjectsAt(p);
        } else {
          this.draft = {
            id: createId(),
            type: 'eraser',
            points: [round(p.x), round(p.y)],
            color: '#000000',
            width: s.eraserSize,
            opacity: 1,
          };
          this.pointerMode = 'draw';
        }
        break;
      case 'text': {
        event.preventDefault();
        const existing = this.findElementAt(p.x, p.y);
        if (existing && isText(existing)) this.openTextEditor(existing);
        else this.openTextEditor(null, p.x, p.y);
        break;
      }
      default:
        this.draft = {
          id: createId(),
          type: this.tool as ShapeType,
          x1: round(p.x),
          y1: round(p.y),
          x2: round(p.x),
          y2: round(p.y),
          stroke: s.strokeColor,
          fill: isLinear(this.tool) || !s.fillEnabled ? null : s.fillColor,
          width: s.strokeWidth,
          lineStyle: s.lineStyle,
          opacity: s.opacity,
        };
        this.pointerMode = 'shape';
    }
    this.render();
  }

  private startSelectInteraction(event: PointerEvent, p: { x: number; y: number }): void {
    const selected = this.selectedElement;
    if (selected && isShape(selected)) {
      const tol = 10 / this.scale;
      const handle =
        Math.hypot(p.x - selected.x2, p.y - selected.y2) <= tol
          ? 2
          : Math.hypot(p.x - selected.x1, p.y - selected.y1) <= tol
            ? 1
            : null;
      if (handle) {
        this.beginTransform(selected, 'resize');
        this.resizeHandle = handle;
        return;
      }
    }

    const hit = this.findElementAt(p.x, p.y);
    if (hit) {
      this.selectedId = hit.id;
      this.loadStyleFrom(hit);
      this.beginTransform(hit, 'move');
      return;
    }

    this.selectedId = null;
    const viewport = this.viewportRef!.nativeElement;
    this.panStart = { x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
    this.pointerMode = 'pan';
  }

  private beginTransform(el: WhiteboardElement, mode: 'move' | 'resize'): void {
    this.pendingSnapshot = this.snapshot();
    this.originalElement = el;
    this.draft = el;
    this.hiddenId = el.id;
    this.pointerMode = mode;
    renderLayer(this.layerCanvas, this.elements, this.boardWidth, this.boardHeight, this.renderScale, this.hiddenId);
  }

  onPointerMove(event: PointerEvent): void {
    const p = this.toBoard(event);
    if (this.tool === 'eraser') this.hoverPoint = p;

    switch (this.pointerMode) {
      case 'draw': {
        const draft = this.draft as FreehandElement;
        const pts = draft.points;
        const lastX = pts[pts.length - 2];
        const lastY = pts[pts.length - 1];
        if (Math.hypot(p.x - lastX, p.y - lastY) >= 1.5 / this.scale) {
          pts.push(round(p.x), round(p.y));
        }
        break;
      }
      case 'shape': {
        const draft = this.draft as ShapeElement;
        const target = event.shiftKey ? constrainPoint(draft.type, draft.x1, draft.y1, p.x, p.y) : p;
        draft.x2 = round(target.x);
        draft.y2 = round(target.y);
        break;
      }
      case 'move': {
        const dx = round(p.x - this.pointerStart.x);
        const dy = round(p.y - this.pointerStart.y);
        this.changedDuringPointer = this.changedDuringPointer || dx !== 0 || dy !== 0;
        this.draft = translateElement(this.originalElement!, dx, dy);
        break;
      }
      case 'resize': {
        const original = this.originalElement as ShapeElement;
        const anchorX = this.resizeHandle === 2 ? original.x1 : original.x2;
        const anchorY = this.resizeHandle === 2 ? original.y1 : original.y2;
        const target = event.shiftKey ? constrainPoint(original.type, anchorX, anchorY, p.x, p.y) : p;
        this.changedDuringPointer = true;
        this.draft =
          this.resizeHandle === 2
            ? { ...original, x2: round(target.x), y2: round(target.y) }
            : { ...original, x1: round(target.x), y1: round(target.y) };
        break;
      }
      case 'erase-object':
        this.eraseObjectsAt(p);
        break;
      case 'pan': {
        const viewport = this.viewportRef!.nativeElement;
        viewport.scrollLeft = this.panStart.left - (event.clientX - this.panStart.x);
        viewport.scrollTop = this.panStart.top - (event.clientY - this.panStart.y);
        return;
      }
      default:
        if (this.tool !== 'eraser') return;
    }
    this.render();
  }

  onPointerUp(): void {
    const mode = this.pointerMode;
    this.pointerMode = 'none';

    if (mode === 'draw' && this.draft) {
      this.commitNewElement(this.draft);
    } else if (mode === 'shape' && this.draft) {
      const shape = this.draft as ShapeElement;
      const tiny = Math.abs(shape.x2 - shape.x1) < 2 && Math.abs(shape.y2 - shape.y1) < 2;
      if (!tiny) this.commitNewElement(shape);
    } else if ((mode === 'move' || mode === 'resize') && this.draft) {
      if (this.changedDuringPointer && this.pendingSnapshot) {
        this.pushSnapshot(this.pendingSnapshot);
        this.replaceElement(this.draft);
        this.markDirty();
      }
    } else if (mode === 'erase-object' && this.changedDuringPointer && this.pendingSnapshot) {
      this.pushSnapshot(this.pendingSnapshot);
      this.markDirty();
    }

    this.draft = null;
    this.hiddenId = null;
    this.originalElement = null;
    this.pendingSnapshot = null;
    this.invalidateLayer();
  }

  onPointerLeave(): void {
    if (this.hoverPoint) {
      this.hoverPoint = null;
      this.render();
    }
  }

  onDoubleClick(event: MouseEvent): void {
    if (this.tool !== 'select') return;
    const p = this.toBoard(event);
    const hit = this.findElementAt(p.x, p.y);
    if (hit && isText(hit)) this.openTextEditor(hit);
  }

  private eraseObjectsAt(p: { x: number; y: number }): void {
    const tolerance = this.style.eraserSize / 2;
    const remaining = this.elements.filter((el) => !hitTest(el, p.x, p.y, tolerance));
    if (remaining.length !== this.elements.length) {
      this.elements = remaining;
      this.changedDuringPointer = true;
      renderLayer(this.layerCanvas, this.elements, this.boardWidth, this.boardHeight, this.renderScale);
    }
  }

  private commitNewElement(el: WhiteboardElement): void {
    this.pushHistory();
    this.elements = [...this.elements, el];
    this.markDirty();
  }

  private replaceElement(el: WhiteboardElement): void {
    this.elements = this.elements.map((item) => (item.id === el.id ? el : item));
  }

  // ---------------------------------------------------------------------------
  // Texto
  // ---------------------------------------------------------------------------

  private openTextEditor(existing: TextElement | null, x = 0, y = 0): void {
    if (existing) {
      this.loadStyleFrom(existing);
      this.textEditor = { x: existing.x, y: existing.y, value: existing.text, editingId: existing.id };
      this.hiddenId = existing.id;
      this.invalidateLayer();
    } else {
      this.textEditor = { x: round(x), y: round(y - (this.style.fontSize * 1.25) / 2), value: '', editingId: null };
    }
    setTimeout(() => {
      const input = this.textInputRef?.nativeElement;
      if (!input) return;
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    });
  }

  onTextKeydown(event: KeyboardEvent): void {
    event.stopPropagation();
    if (event.key === 'Escape' || (event.key === 'Enter' && (event.ctrlKey || event.metaKey))) {
      event.preventDefault();
      this.commitText();
    }
  }

  commitText(): void {
    const editor = this.textEditor;
    if (!editor) return;
    this.textEditor = null;
    this.hiddenId = null;
    const text = editor.value.replace(/\s+$/, '');
    const s = this.style;
    const existing = editor.editingId ? this.elements.find((el) => el.id === editor.editingId) : null;

    if (existing && isText(existing)) {
      if (!text) {
        this.pushHistory();
        this.elements = this.elements.filter((el) => el.id !== existing.id);
        this.selectedId = null;
        this.markDirty();
      } else {
        const updated: TextElement = {
          ...existing,
          text,
          color: s.textColor,
          fontSize: s.fontSize,
          fontFamily: s.fontFamily,
          bold: s.bold,
          italic: s.italic,
          opacity: s.opacity,
        };
        if (JSON.stringify(updated) !== JSON.stringify(existing)) {
          this.pushHistory();
          this.replaceElement(updated);
          this.markDirty();
        }
      }
    } else if (text) {
      this.commitNewElement({
        id: createId(),
        type: 'text',
        x: editor.x,
        y: editor.y,
        text,
        color: s.textColor,
        fontSize: s.fontSize,
        fontFamily: s.fontFamily,
        bold: s.bold,
        italic: s.italic,
        opacity: s.opacity,
      });
    }
    this.invalidateLayer();
  }

  // ---------------------------------------------------------------------------
  // Acciones sobre la selección y el lienzo
  // ---------------------------------------------------------------------------

  deleteSelected(): void {
    if (!this.selectedId) return;
    this.pushHistory();
    this.elements = this.elements.filter((el) => el.id !== this.selectedId);
    this.selectedId = null;
    this.invalidateLayer();
    this.markDirty();
  }

  duplicateSelected(): void {
    const selected = this.selectedElement;
    if (!selected) return;
    this.pushHistory();
    const copy = { ...translateElement(selected, 20, 20), id: createId() };
    this.elements = [...this.elements, copy];
    this.selectedId = copy.id;
    this.invalidateLayer();
    this.markDirty();
  }

  bringToFront(): void {
    this.reorderSelected(true);
  }

  sendToBack(): void {
    this.reorderSelected(false);
  }

  private reorderSelected(toFront: boolean): void {
    const selected = this.selectedElement;
    if (!selected) return;
    this.pushHistory();
    const others = this.elements.filter((el) => el.id !== selected.id);
    this.elements = toFront ? [...others, selected] : [selected, ...others];
    this.invalidateLayer();
    this.markDirty();
  }

  setBackground(color: string): void {
    if (!/^#[0-9a-fA-F]{6}$/.test(color) || color.toLowerCase() === this.background) return;
    this.pushHistory();
    this.background = color.toLowerCase();
    this.render();
    this.markDirty();
  }

  clearBoard(): void {
    if (!this.elements.length) return;
    if (!confirm('¿Borrar todo el contenido de la pizarra? Puedes deshacerlo con Ctrl+Z.')) return;
    this.pushHistory();
    this.elements = [];
    this.selectedId = null;
    this.invalidateLayer();
    this.markDirty();
  }

  // ---------------------------------------------------------------------------
  // Historial (deshacer / rehacer)
  // ---------------------------------------------------------------------------

  private snapshot(): Snapshot {
    return { elements: JSON.stringify(this.elements), background: this.background };
  }

  private pushHistory(): void {
    this.pushSnapshot(this.snapshot());
  }

  private pushSnapshot(snapshot: Snapshot): void {
    this.undoStack.push(snapshot);
    if (this.undoStack.length > HISTORY_LIMIT) this.undoStack.shift();
    this.redoStack = [];
  }

  private restore(snapshot: Snapshot): void {
    this.elements = JSON.parse(snapshot.elements);
    this.background = snapshot.background;
    if (this.selectedId && !this.elements.some((el) => el.id === this.selectedId)) this.selectedId = null;
    this.invalidateLayer();
    this.markDirty();
  }

  undo(): void {
    if (this.textEditor) this.commitText();
    const previous = this.undoStack.pop();
    if (!previous) return;
    this.redoStack.push(this.snapshot());
    this.restore(previous);
  }

  redo(): void {
    const next = this.redoStack.pop();
    if (!next) return;
    this.undoStack.push(this.snapshot());
    this.restore(next);
  }

  // ---------------------------------------------------------------------------
  // Guardado
  // ---------------------------------------------------------------------------

  onNameCommit(): void {
    const trimmed = this.name.trim();
    if (!trimmed) {
      this.name = this.savedName;
      return;
    }
    this.name = trimmed;
    if (trimmed !== this.savedName) this.markDirty();
  }

  private markDirty(): void {
    this.changeVersion++;
    this.saveState = 'dirty';
    if (this.autosaveTimer) clearTimeout(this.autosaveTimer);
    this.autosaveTimer = setTimeout(() => this.save(), AUTOSAVE_DELAY_MS);
  }

  save(silent = false): void {
    if (this.loading) return;
    if (this.textEditor) this.commitText();
    if (this.autosaveTimer) {
      clearTimeout(this.autosaveTimer);
      this.autosaveTimer = null;
    }
    if (this.saveInFlight) {
      // Se reintenta al terminar el guardado en curso.
      this.autosaveTimer = setTimeout(() => this.save(silent), 400);
      return;
    }

    const version = this.changeVersion;
    const name = this.name.trim() || this.savedName;
    this.saveInFlight = true;
    this.saveState = 'saving';
    this.api
      .updateWhiteboard(this.whiteboardId, {
        name,
        background_color: this.background,
        content: this.elements as unknown as Record<string, unknown>[],
        thumbnail: this.buildThumbnail(),
      })
      .subscribe({
        next: () => {
          this.saveInFlight = false;
          this.savedName = name;
          if (version === this.changeVersion) this.saveState = 'saved';
          else this.markDirty();
        },
        error: (err) => {
          this.saveInFlight = false;
          this.saveState = 'error';
          if (!silent) {
            this.snackBar.open(err.error?.detail || 'No se pudo guardar la pizarra', 'Cerrar', { duration: 4000 });
          }
        },
      });
  }

  private buildThumbnail(): string | null {
    try {
      const scale = Math.min(480 / this.boardWidth, 480 / this.boardHeight);
      const canvas = renderBoardToCanvas(this.elements, this.boardWidth, this.boardHeight, this.background, scale);
      return canvas.toDataURL('image/jpeg', 0.8);
    } catch {
      return null;
    }
  }

  // ---------------------------------------------------------------------------
  // Exportación
  // ---------------------------------------------------------------------------

  private exportScale(): number {
    const maxScale = Math.sqrt(EXPORT_MAX_PIXELS / (this.boardWidth * this.boardHeight));
    return Math.max(1, Math.min(2, maxScale));
  }

  async exportPng(transparent = false): Promise<void> {
    if (this.textEditor) this.commitText();
    try {
      const canvas = renderBoardToCanvas(
        this.elements,
        this.boardWidth,
        this.boardHeight,
        transparent ? null : this.background,
        this.exportScale(),
      );
      downloadBlob(await canvasToPngBlob(canvas), safeFileName(this.name, 'png'));
    } catch {
      this.snackBar.open('No se pudo exportar la imagen', 'Cerrar', { duration: 4000 });
    }
  }

  exportPdf(pageSize: PdfPageSize): void {
    if (this.textEditor) this.commitText();
    try {
      const canvas = renderBoardToCanvas(
        this.elements,
        this.boardWidth,
        this.boardHeight,
        this.background,
        this.exportScale(),
      );
      const pdf = buildPdfFromCanvas(canvas, {
        title: this.name,
        background: this.background,
        pageSize,
        logicalWidth: this.boardWidth,
        logicalHeight: this.boardHeight,
      });
      downloadBlob(pdf, safeFileName(this.name, 'pdf'));
    } catch {
      this.snackBar.open('No se pudo exportar el PDF', 'Cerrar', { duration: 4000 });
    }
  }

  // ---------------------------------------------------------------------------
  // Atajos de teclado
  // ---------------------------------------------------------------------------

  @HostListener('window:keydown', ['$event'])
  onKeydown(event: KeyboardEvent): void {
    const target = event.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
    if (document.querySelector('.cdk-overlay-container .mat-mdc-menu-panel, .mat-mdc-select-panel')) return;

    const key = event.key.toLowerCase();
    const mod = event.ctrlKey || event.metaKey;
    if (mod && key === 'z') {
      event.preventDefault();
      if (event.shiftKey) this.redo();
      else this.undo();
      return;
    }
    if (mod && key === 'y') {
      event.preventDefault();
      this.redo();
      return;
    }
    if (mod && key === 's') {
      event.preventDefault();
      this.save();
      return;
    }
    if (mod && key === 'd') {
      event.preventDefault();
      this.duplicateSelected();
      return;
    }
    if (mod || event.altKey) return;

    if ((key === 'delete' || key === 'backspace') && this.selectedId) {
      event.preventDefault();
      this.deleteSelected();
      return;
    }
    if (key === 'escape') {
      this.selectedId = null;
      this.render();
      return;
    }
    const tool = [...this.drawingTools, ...this.shapeTools].find((t) => t.shortcut.toLowerCase() === key);
    if (tool) this.setTool(tool.id);
  }

  @HostListener('window:beforeunload', ['$event'])
  onBeforeUnload(event: BeforeUnloadEvent): void {
    if (this.saveState === 'dirty' || this.saveState === 'saving' || this.saveState === 'error') {
      event.preventDefault();
      event.returnValue = '';
    }
  }
}

function round(value: number): number {
  return Math.round(value * 10) / 10;
}
