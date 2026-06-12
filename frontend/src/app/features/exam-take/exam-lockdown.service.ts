import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

@Injectable({ providedIn: 'root' })
export class ExamLockdownService {
  private readonly snackBar = inject(MatSnackBar);
  private active = false;
  private lastWarning = 0;

  private readonly onCopy = (event: Event): void => this.blockClipboard(event);
  private readonly onCut = (event: Event): void => this.blockClipboard(event);
  private readonly onPaste = (event: Event): void => this.blockClipboard(event);
  private readonly onContextMenu = (event: Event): void => {
    if (!this.active) return;
    event.preventDefault();
    this.warn('El menú contextual está deshabilitado durante el examen');
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
        this.warn('Atajo de teclado no permitido durante el examen');
        return;
      }

      if (event.shiftKey && ['i', 'j', 'c', 'k'].includes(key)) {
        event.preventDefault();
        this.warn('Atajo de teclado no permitido durante el examen');
        return;
      }
    }

    if (key === 'f12' || key === 'f5' || (withModifier && key === 'f5')) {
      event.preventDefault();
      this.warn('Atajo de teclado no permitido durante el examen');
    }
  };
  private readonly onBeforePrint = (event: Event): void => {
    if (!this.active) return;
    event.preventDefault();
    this.warn('La impresión no está permitida durante el examen');
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

  private blockClipboard(event: Event): void {
    if (!this.active) return;
    event.preventDefault();
    const clipboard = (event as ClipboardEvent).clipboardData;
    clipboard?.clearData();
    this.warn('No se permite copiar, cortar ni pegar durante el examen');
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
