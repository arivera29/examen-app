import { FreehandElement, ShapeElement, TextElement } from './whiteboard.models';
import {
  constrainPoint,
  getBounds,
  hitTest,
  isDarkColor,
  renderBoardToCanvas,
  sanitizeElements,
  translateElement,
} from './whiteboard-renderer';
import { buildPdfFromCanvas, safeFileName } from './whiteboard-export';

function shape(partial: Partial<ShapeElement>): ShapeElement {
  return {
    id: 's',
    type: 'rect',
    x1: 10,
    y1: 10,
    x2: 110,
    y2: 60,
    stroke: '#000000',
    fill: null,
    width: 2,
    lineStyle: 'solid',
    opacity: 1,
    ...partial,
  };
}

const pen: FreehandElement = {
  id: 'p',
  type: 'pen',
  points: [0, 0, 100, 0, 100, 100],
  color: '#000000',
  width: 4,
  opacity: 1,
};

describe('whiteboard-renderer', () => {
  it('hit-tests freehand strokes near their segments only', () => {
    expect(hitTest(pen, 50, 2, 1)).toBeTrue();
    expect(hitTest(pen, 101, 50, 1)).toBeTrue();
    expect(hitTest(pen, 50, 50, 1)).toBeFalse();
  });

  it('never hit-tests eraser strokes', () => {
    expect(hitTest({ ...pen, type: 'eraser' }, 50, 0, 5)).toBeFalse();
  });

  it('hit-tests unfilled rectangles on the border and filled ones inside', () => {
    expect(hitTest(shape({}), 60, 35, 2)).toBeFalse();
    expect(hitTest(shape({}), 10, 35, 2)).toBeTrue();
    expect(hitTest(shape({ fill: '#ff0000' }), 60, 35, 2)).toBeTrue();
  });

  it('hit-tests ellipses using their outline', () => {
    const ellipse = shape({ type: 'ellipse', x1: 0, y1: 0, x2: 100, y2: 100 });
    expect(hitTest(ellipse, 100, 50, 2)).toBeTrue();
    expect(hitTest(ellipse, 50, 50, 2)).toBeFalse();
    expect(hitTest({ ...ellipse, fill: '#00ff00' }, 50, 50, 2)).toBeTrue();
  });

  it('hit-tests triangles with polygon containment when filled', () => {
    const triangle = shape({ type: 'triangle', x1: 0, y1: 0, x2: 100, y2: 100, fill: '#123456' });
    expect(hitTest(triangle, 50, 60, 1)).toBeTrue();
    expect(hitTest(triangle, 5, 5, 1)).toBeFalse();
  });

  it('hit-tests lines and arrows along the segment', () => {
    const arrow = shape({ type: 'arrow', x1: 0, y1: 0, x2: 100, y2: 100 });
    expect(hitTest(arrow, 50, 51, 1)).toBeTrue();
    expect(hitTest(arrow, 50, 80, 1)).toBeFalse();
  });

  it('computes bounds including stroke width and normalizes reversed shapes', () => {
    expect(getBounds(shape({ x1: 110, y1: 60, x2: 10, y2: 10 }))).toEqual({ x: 9, y: 9, w: 102, h: 52 });
    expect(getBounds(pen)).toEqual({ x: -2, y: -2, w: 104, h: 104 });
  });

  it('measures text bounds for multi-line text', () => {
    const text: TextElement = {
      id: 't',
      type: 'text',
      x: 5,
      y: 5,
      text: 'Hola\nmundo',
      color: '#000000',
      fontSize: 20,
      fontFamily: 'Arial',
      bold: false,
      italic: false,
      opacity: 1,
    };
    const bounds = getBounds(text);
    expect(bounds.h).toBe(50);
    expect(bounds.w).toBeGreaterThan(0);
    expect(hitTest(text, 10, 30, 0)).toBeTrue();
  });

  it('translates every element type without mutating the original', () => {
    const moved = translateElement(pen, 5, -5);
    expect(moved.points).toEqual([5, -5, 105, -5, 105, 95]);
    expect(pen.points).toEqual([0, 0, 100, 0, 100, 100]);
    const movedShape = translateElement(shape({}), 1, 2);
    expect([movedShape.x1, movedShape.y1, movedShape.x2, movedShape.y2]).toEqual([11, 12, 111, 62]);
  });

  it('constrains shapes to squares and lines to 45 degree steps', () => {
    expect(constrainPoint('rect', 0, 0, 50, 20)).toEqual({ x: 50, y: 50 });
    const snapped = constrainPoint('line', 0, 0, 100, 10);
    expect(Math.round(snapped.y)).toBe(0);
  });

  it('detects dark backgrounds', () => {
    expect(isDarkColor('#121212')).toBeTrue();
    expect(isDarkColor('#ffffff')).toBeFalse();
  });

  it('drops malformed elements when loading content', () => {
    const result = sanitizeElements([
      pen,
      { id: 'x', type: 'rect', x1: 'a' },
      null,
      { type: 'text', text: 'sin id' },
      shape({}),
    ]);
    expect(result.map((el) => el.id)).toEqual(['p', 's']);
  });

  it('renders the board with the background color and erases only ink', () => {
    const canvas = renderBoardToCanvas(
      [
        { ...pen, points: [10, 10, 90, 10], width: 10, color: '#ff0000' },
        { ...pen, id: 'e', type: 'eraser', points: [50, 0, 50, 20], width: 20 },
      ],
      100,
      40,
      '#0000ff',
    );
    const ctx = canvas.getContext('2d')!;
    const ink = ctx.getImageData(20, 10, 1, 1).data;
    const erased = ctx.getImageData(50, 10, 1, 1).data;
    expect([ink[0], ink[2]]).toEqual([255, 0]);
    expect([erased[0], erased[2]]).toEqual([0, 255]);
  });
});

describe('whiteboard-export', () => {
  it('builds a structurally valid single page PDF', async () => {
    const canvas = renderBoardToCanvas([pen], 200, 100, '#ffffff');
    const blob = buildPdfFromCanvas(canvas, {
      title: 'Pizarra de prueba ñ',
      background: '#ffffff',
      pageSize: 'a4',
      logicalWidth: 200,
      logicalHeight: 100,
    });
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const text = new TextDecoder('latin1').decode(bytes);

    expect(blob.type).toBe('application/pdf');
    expect(text.startsWith('%PDF-1.4')).toBeTrue();
    expect(text.trimEnd().endsWith('%%EOF')).toBeTrue();
    expect(text).toContain('/MediaBox [0 0 841.89 595.28]');

    const startxref = Number(/startxref\n(\d+)/.exec(text)![1]);
    expect(text.slice(startxref, startxref + 4)).toBe('xref');
    const offsets = [...text.slice(startxref).matchAll(/(\d{10}) 00000 n/g)].map((m) => Number(m[1]));
    expect(offsets.length).toBe(6);
    offsets.forEach((offset, index) => {
      expect(text.slice(offset, offset + `${index + 1} 0 obj`.length)).toBe(`${index + 1} 0 obj`);
    });
  });

  it('uses the board size as page size in fit mode', async () => {
    const canvas = renderBoardToCanvas([], 400, 800, '#ffffff');
    const blob = buildPdfFromCanvas(canvas, {
      title: 'x',
      background: '#ffffff',
      pageSize: 'fit',
      logicalWidth: 400,
      logicalHeight: 800,
    });
    const text = new TextDecoder('latin1').decode(new Uint8Array(await blob.arrayBuffer()));
    expect(text).toContain('/MediaBox [0 0 300 600]');
  });

  it('creates safe file names', () => {
    expect(safeFileName('Clase de matemáticas: álgebra/1', 'png')).toBe('Clase_de_matematicas_algebra1.png');
    expect(safeFileName('***', 'pdf')).toBe('pizarra.pdf');
  });
});
