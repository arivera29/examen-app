import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ExamIntegrityService, IntegrityEventType } from './exam-integrity.service';

@Injectable({ providedIn: 'root' })
export class ExamLockdownService {
  private readonly snackBar = inject(MatSnackBar);
  private readonly integrity = inject(ExamIntegrityService);
  private active = false;
  private lastWarning = 0;

  private readonly onCopy = (event: Event): void => this.blockClipboard(event, 'clipboard_copy');
  private readonly onCut = (event: Event): void => this.blockClipboard(event, 'clipboard_copy');
  private readonly onPaste = (event: Event): void => this.blockClipboard(event, 'clipboard_paste');
  private readonly onContextMenu = (event: Event): void => {
    if (!this.active) return;
    event.preventDefault();
    this.reportAndWarn('right_click', 0.55, 'El menú contextual está deshabilitado durante el examen');
  };
  private readonly onSelectStart = (event: Event): void => {
    if (!this.active) return;
    if (this.isAnswerInput(event.target)) return;
    event.preventDefault();
  };
  private readonly onDragStart = (event: Event): void => {
    if (!this.active) return;
    event.preventDefault();
  };
  private readonly onKeyDown = (event: KeyboardEvent): void => {
    if (!this.active) return;

    const key = event.key.toLowerCase();
    const withModifier = event.ctrlKey || event.metaKey;
    const inAnswerInput = this.isAnswerInput(event.target);

    if (withModifier) {
      const blockedKeys = ['c', 'x', 'v', 'p', 's', 'u', 'r', 'g'];
      if (blockedKeys.includes(key)) {
        if (key === 'a' && inAnswerInput) return;
        event.preventDefault();
        let eventType: IntegrityEventType = 'shortcut_blocked';
        let confidence = 0.6;
        if (key === 'c' || key === 'x') {
          eventType = 'clipboard_copy';
          confidence = 0.82;
        } else if (key === 'v') {
          eventType = 'clipboard_paste';
          confidence = 0.82;
        } else if (key === 'p') {
          eventType = 'print_attempt';
          confidence = 0.75;
        }
        this.reportAndWarn(eventType, confidence, 'Atajo de teclado no permitido durante el examen', {
          key,
        });
        return;
      }

      if (event.shiftKey && ['i', 'j', 'c', 'k'].includes(key)) {
        event.preventDefault();
        this.reportAndWarn(
          'devtools_suspected',
          0.75,
          'Atajo de teclado no permitido durante el examen',
          { key: `shift+${key}` }
        );
        return;
      }
    }

    if (key === 'f12' || key === 'f5' || (withModifier && key === 'f5')) {
      event.preventDefault();
      this.reportAndWarn(
        key === 'f12' ? 'devtools_suspected' : 'shortcut_blocked',
        key === 'f12' ? 0.78 : 0.55,
        'Atajo de teclado no permitido durante el examen',
        { key }
      );
    }
  };
  private readonly onBeforePrint = (event: Event): void => {
    if (!this.active) return;
    event.preventDefault();
    this.reportAndWarn('print_attempt', 0.8, 'La impresión no está permitida durante el examen');
  };
  private readonly onBeforeUnload = (event: BeforeUnloadEvent): void => {
    if (!this.active) return;
    event.preventDefault();
    event.returnValue = '';
  };

  enable(): void {
    if (this.active) return;
    this.active = true;
    document.body.classList.add('exam-lockdown-active');

    document.addEventListener('copy', this.onCopy, true);
    document.addEventListener('cut', this.onCut, true);
    document.addEventListener('paste', this.onPaste, true);
    document.addEventListener('contextmenu', this.onContextMenu, true);
    document.addEventListener('selectstart', this.onSelectStart, true);
    document.addEventListener('dragstart', this.onDragStart, true);
    document.addEventListener('keydown', this.onKeyDown, true);
    window.addEventListener('beforeprint', this.onBeforePrint);
    window.addEventListener('beforeunload', this.onBeforeUnload);
  }

  disable(): void {
    if (!this.active) return;
    this.active = false;
    document.body.classList.remove('exam-lockdown-active');

    document.removeEventListener('copy', this.onCopy, true);
    document.removeEventListener('cut', this.onCut, true);
    document.removeEventListener('paste', this.onPaste, true);
    document.removeEventListener('contextmenu', this.onContextMenu, true);
    document.removeEventListener('selectstart', this.onSelectStart, true);
    document.removeEventListener('dragstart', this.onDragStart, true);
    document.removeEventListener('keydown', this.onKeyDown, true);
    window.removeEventListener('beforeprint', this.onBeforePrint);
    window.removeEventListener('beforeunload', this.onBeforeUnload);
  }

  private blockClipboard(event: Event, eventType: IntegrityEventType): void {
    if (!this.active) return;
    event.preventDefault();
    const clipboard = (event as ClipboardEvent).clipboardData;
    clipboard?.clearData();
    const inAnswer = this.isAnswerInput(event.target);
    this.reportAndWarn(
      eventType,
      eventType === 'clipboard_paste' ? 0.85 : 0.8,
      'No se permite copiar, cortar ni pegar durante el examen',
      {
        target: inAnswer ? 'answer_input' : 'exam_content',
        selection_length: window.getSelection()?.toString()?.length ?? 0,
      }
    );
  }

  private reportAndWarn(
    eventType: IntegrityEventType,
    confidence: number,
    message: string,
    metadata?: Record<string, unknown>
  ): void {
    // notify:false — el aviso local ya cubre el feedback inmediato
    this.integrity.reportViolation({ eventType, confidence, metadata }, { notify: false });
    this.warn(message);
  }

  private isAnswerInput(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false;
    return target.classList.contains('open-answer') || target.closest('textarea.open-answer') !== null;
  }

  private warn(message: string): void {
    const now = Date.now();
    if (now - this.lastWarning < 2000) return;
    this.lastWarning = now;
    this.snackBar.open(message, 'OK', { duration: 2500 });
  }
}
