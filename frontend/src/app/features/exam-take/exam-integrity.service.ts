import { Injectable, inject } from '@angular/core';
import { ApiService } from '../../core/services/api.service';

export type IntegrityEventType =
  | 'clipboard_copy'
  | 'clipboard_paste'
  | 'idle_suspicious'
  | 'ai_assist_suspected'
  | 'devtools_suspected'
  | 'right_click'
  | 'print_attempt'
  | 'shortcut_blocked';

export interface IntegrityViolation {
  eventType: IntegrityEventType;
  confidence: number;
  metadata?: Record<string, unknown>;
}

interface MousePoint {
  x: number;
  y: number;
  t: number;
}

/** Selectores/DOM típicos de extensiones de asistencia con IA o escritura. */
const AI_EXTENSION_SELECTORS = [
  '#chatgpt-sidebar',
  '#monica-content-root',
  '#merlin-root',
  '[data-grammarly-part]',
  'grammarly-extension',
  'grammarly-desktop-integration',
  '#loom-companion-mv3',
  '[class*="scribe-extension"]',
  '[id*="openai-chatgpt"]',
  '[class*="chatgpt-"]',
  'div[data-sid="sidebar"]',
];

@Injectable({ providedIn: 'root' })
export class ExamIntegrityService {
  private readonly api = inject(ApiService);

  private active = false;
  private attemptId: string | null = null;
  private cameraProctoringActive = false;
  private mouseEvents: MousePoint[] = [];
  private lastActivityAt = Date.now();
  private lastReportByType = new Map<string, number>();
  private mouseInterval?: ReturnType<typeof setInterval>;
  private idleInterval?: ReturnType<typeof setInterval>;
  private probeInterval?: ReturnType<typeof setInterval>;
  private onFraudDetected?: (message: string) => void;

  private readonly onMouseMove = (event: MouseEvent): void => {
    if (!this.active) return;
    this.lastActivityAt = Date.now();
    this.mouseEvents.push({ x: event.clientX, y: event.clientY, t: Date.now() });
    if (this.mouseEvents.length > 120) {
      this.mouseEvents = this.mouseEvents.slice(-60);
    }
  };

  private readonly onKeyActivity = (): void => {
    if (!this.active) return;
    this.lastActivityAt = Date.now();
  };

  private readonly onPointerDown = (): void => {
    if (!this.active) return;
    this.lastActivityAt = Date.now();
  };

  start(
    attemptId: string,
    options?: {
      cameraProctoringActive?: boolean;
      onFraudDetected?: (message: string) => void;
    }
  ): void {
    this.stop();
    this.active = true;
    this.attemptId = attemptId;
    this.cameraProctoringActive = Boolean(options?.cameraProctoringActive);
    this.onFraudDetected = options?.onFraudDetected;
    this.mouseEvents = [];
    this.lastActivityAt = Date.now();
    this.lastReportByType.clear();

    document.addEventListener('mousemove', this.onMouseMove, { passive: true });
    document.addEventListener('keydown', this.onKeyActivity, true);
    document.addEventListener('pointerdown', this.onPointerDown, true);

    // Con cámara el mouse ya viaja con el frame; sin cámara se analiza solo.
    if (!this.cameraProctoringActive) {
      this.mouseInterval = setInterval(() => this.flushMouseEvents(), 8000);
    }
    this.idleInterval = setInterval(() => this.checkIdle(), 15000);
    this.probeInterval = setInterval(() => {
      this.probeAiExtensions();
      this.probeDevTools();
    }, 12000);

    // Primera pasada temprana
    setTimeout(() => {
      this.probeAiExtensions();
      this.probeDevTools();
    }, 2500);
  }

  stop(): void {
    this.active = false;
    this.attemptId = null;
    this.onFraudDetected = undefined;
    document.removeEventListener('mousemove', this.onMouseMove);
    document.removeEventListener('keydown', this.onKeyActivity, true);
    document.removeEventListener('pointerdown', this.onPointerDown, true);
    if (this.mouseInterval) clearInterval(this.mouseInterval);
    if (this.idleInterval) clearInterval(this.idleInterval);
    if (this.probeInterval) clearInterval(this.probeInterval);
    this.mouseInterval = undefined;
    this.idleInterval = undefined;
    this.probeInterval = undefined;
    this.mouseEvents = [];
  }

  /** Consume y vacía el buffer de mouse (p. ej. cuando la cámara también lo envía). */
  consumeMouseEvents(): MousePoint[] {
    const events = [...this.mouseEvents];
    this.mouseEvents = [];
    return events;
  }

  reportViolation(
    violation: IntegrityViolation,
    options?: { notify?: boolean }
  ): void {
    if (!this.active || !this.attemptId) return;
    if (!this.canReport(violation.eventType)) return;

    const notify = options?.notify !== false;
    this.api
      .reportIntegrityEvent(this.attemptId, {
        event_type: violation.eventType,
        confidence: violation.confidence,
        metadata: violation.metadata ?? {},
      })
      .subscribe({
        next: (result) => {
          if (notify && result.fraud_detected) {
            this.onFraudDetected?.(this.messageForEvent(violation.eventType));
          }
        },
      });
  }

  private flushMouseEvents(): void {
    if (!this.active || !this.attemptId || this.cameraProctoringActive) return;
    if (this.mouseEvents.length < 8) return;
    if (!this.canReport('mouse_anomaly', 20000)) return;

    const payload = [...this.mouseEvents];
    this.mouseEvents = [];
    this.api.sendMouseIntegrity(this.attemptId, payload).subscribe({
      next: (result) => {
        if (result.fraud_detected) {
          this.onFraudDetected?.('Movimiento de puntero sospechoso detectado');
        }
      },
    });
  }

  private checkIdle(): void {
    if (!this.active) return;
    const idleMs = Date.now() - this.lastActivityAt;
    // Inactividad prolongada puede indicar consulta externa fuera del teclado/mouse.
    if (idleMs < 90_000) return;
    this.reportViolation({
      eventType: 'idle_suspicious',
      confidence: 0.58,
      metadata: { idle_ms: idleMs },
    });
  }

  private probeAiExtensions(): void {
    if (!this.active || typeof document === 'undefined') return;

    const matches: string[] = [];
    for (const selector of AI_EXTENSION_SELECTORS) {
      try {
        if (document.querySelector(selector)) {
          matches.push(selector);
        }
      } catch {
        // Selectores inválidos se ignoran
      }
    }

    const globalHints: string[] = [];
    const win = window as unknown as Record<string, unknown>;
    for (const key of Object.keys(win)) {
      const lower = key.toLowerCase();
      if (
        lower.includes('grammarly') ||
        lower.includes('chatgpt') ||
        lower.includes('monica') ||
        lower.includes('merlin') ||
        lower.includes('copilot')
      ) {
        globalHints.push(key);
      }
    }

    if (!matches.length && !globalHints.length) return;

    this.reportViolation({
      eventType: 'ai_assist_suspected',
      confidence: matches.length ? 0.88 : 0.72,
      metadata: {
        dom_matches: matches.slice(0, 8),
        global_hints: globalHints.slice(0, 8),
      },
    });
  }

  private probeDevTools(): void {
    if (!this.active) return;
    const widthGap = Math.abs(window.outerWidth - window.innerWidth);
    const heightGap = Math.abs(window.outerHeight - window.innerHeight);
    // Umbral alto para reducir falsos positivos por zoom/barras del SO.
    if (widthGap < 160 && heightGap < 160) return;

    this.reportViolation({
      eventType: 'devtools_suspected',
      confidence: 0.7,
      metadata: { width_gap: widthGap, height_gap: heightGap },
    });
  }

  private canReport(eventType: string, cooldownMs = 12000): boolean {
    const now = Date.now();
    const last = this.lastReportByType.get(eventType) ?? 0;
    if (now - last < cooldownMs) return false;
    this.lastReportByType.set(eventType, now);
    return true;
  }

  private messageForEvent(eventType: IntegrityEventType): string {
    switch (eventType) {
      case 'clipboard_copy':
        return 'Intento de copiar contenido del examen detectado';
      case 'clipboard_paste':
        return 'Intento de pegar contenido detectado';
      case 'idle_suspicious':
        return 'Inactividad prolongada detectada durante el examen';
      case 'ai_assist_suspected':
        return 'Posible extensión de asistencia con IA detectada';
      case 'devtools_suspected':
        return 'Posible uso de herramientas de desarrollador detectado';
      case 'right_click':
        return 'Menú contextual bloqueado y registrado';
      case 'print_attempt':
        return 'Intento de impresión detectado';
      case 'shortcut_blocked':
        return 'Atajo de teclado no permitido detectado';
      default:
        return 'Comportamiento sospechoso detectado';
    }
  }
}
