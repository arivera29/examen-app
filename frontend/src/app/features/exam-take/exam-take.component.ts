import {
  afterNextRender,
  Component,
  ElementRef,
  inject,
  Injector,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatRadioModule } from '@angular/material/radio';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { ApiService } from '../../core/services/api.service';
import { ExamSession, Question, SavedAnswer } from '../../core/models';
import { ExamLockdownService } from './exam-lockdown.service';

interface MouseEventData {
  x: number;
  y: number;
  t: number;
}

@Component({
  selector: 'app-exam-take',
  standalone: true,
  imports: [
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatRadioModule,
    MatCheckboxModule,
    MatProgressBarModule,
    MatSnackBarModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
  ],
  templateUrl: './exam-take.component.html',
  styleUrl: './exam-take.component.scss',
})
export class ExamTakeComponent implements OnInit, OnDestroy {
  @ViewChild('setupVideo') setupVideo?: ElementRef<HTMLVideoElement>;
  @ViewChild('examVideo') examVideo?: ElementRef<HTMLVideoElement>;
  @ViewChild('canvasElement') canvasElement?: ElementRef<HTMLCanvasElement>;

  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ApiService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly injector = inject(Injector);
  private readonly examLockdown = inject(ExamLockdownService);

  token = '';
  inviteeFullName = '';
  inviteeEmail = '';
  session: ExamSession | null = null;
  currentIndex = 0;
  remainingSeconds = 0;
  questionRemainingSeconds = 0;
  cameraReady = false;
  examStarted = false;
  examFinished = false;
  examBlocked = false;
  blockMessage = '';
  finalScore: number | null = null;
  maxAttempts = 1;
  attemptsRemaining = 1;
  attemptPolicy: 'flexible' | 'sequential' = 'flexible';
  canStartNewAttempt = false;
  canFinishEarly = false;
  requiresNextAttempt = false;
  currentAttemptNumber: number | null = null;
  examTotalScore: number | null = null;
  examFinalized = false;
  requireAttemptVideo = false;
  isSubmitting = false;
  isRecordingVideo = false;
  pendingResume = false;
  examTerminatedForViolation = false;
  private tabViolationHandled = false;

  answers: Record<string, string[]> = {};
  openAnswers: Record<string, string> = {};
  lockedQuestionIds = new Set<string>();
  mouseEvents: MouseEventData[] = [];

  private timerInterval?: ReturnType<typeof setInterval>;
  private questionTimerInterval?: ReturnType<typeof setInterval>;
  private proctoringInterval?: ReturnType<typeof setInterval>;
  private mediaStream?: MediaStream;
  private mediaRecorder?: MediaRecorder;
  private recordedVideoChunks: Blob[] = [];
  private readonly progressSnapshotCount = 5;
  private readonly maxVideoUploadAttempts = 3;
  private snapshotQuestionIndices = new Set<number>();
  private capturedSnapshotQuestions = new Set<number>();

  ngOnInit(): void {
    this.token = this.route.snapshot.paramMap.get('token')!;
    this.loadSessionInfo();
    document.addEventListener('mousemove', this.onMouseMove);
    document.addEventListener('visibilitychange', this.onVisibilityChange);
    window.addEventListener('blur', this.onWindowBlur);
  }

  private loadSessionInfo(): void {
    this.api.getExamSessionInfo(this.token).subscribe({
      next: (info) => {
        this.inviteeEmail = String(info['invitee_email'] ?? '');
        const savedName = String(info['invitee_full_name'] ?? '').trim();
        if (savedName) {
          this.inviteeFullName = savedName;
        }
        this.maxAttempts = Number(info['max_attempts'] ?? 1);
        this.attemptsRemaining = Number(info['attempts_remaining'] ?? 0);
        this.examTotalScore = info['exam_total_score'] != null
          ? Number(info['exam_total_score'])
          : null;
        this.attemptPolicy =
          info['attempt_policy'] === 'sequential' ? 'sequential' : 'flexible';
        this.canStartNewAttempt = Boolean(info['can_start_new_attempt']);
        this.canFinishEarly = Boolean(info['can_finish_early']);
        this.requiresNextAttempt = Boolean(info['requires_next_attempt']);
        this.examFinalized = Boolean(info['exam_finalized']);
        this.requireAttemptVideo = Boolean(info['require_attempt_video']);
        this.currentAttemptNumber = info['current_attempt_number']
          ? Number(info['current_attempt_number'])
          : null;

        if (info['terminated_for_violation']) {
          this.examTerminatedForViolation = true;
          this.examFinished = true;
          this.examFinalized = true;
          this.examBlocked = false;
          this.canStartNewAttempt = false;
          this.canFinishEarly = false;
          if (info['final_score'] != null) {
            this.finalScore = Number(info['final_score']);
          }
        } else if (info['exam_finalized']) {
          this.examFinished = true;
          this.examBlocked = false;
          this.canStartNewAttempt = false;
          this.canFinishEarly = false;
          if (info['final_score'] != null) {
            this.finalScore = Number(info['final_score']);
          }
        } else if (info['email_already_completed']) {
          this.examBlocked = true;
          this.blockMessage = 'Agotó los intentos disponibles para este examen.';
        } else if (info['email_in_progress'] && info['attempt_status'] !== 'in_progress') {
          this.examBlocked = true;
          this.blockMessage =
            'Este correo ya tiene un examen en progreso. Use el enlace original para continuar.';
        } else if (
          info['attempt_status'] === 'in_progress' ||
          Boolean(info['has_in_progress_attempt'])
        ) {
          this.pendingResume = true;
        }
      },
    });
  }

  prepareAnotherAttempt(): void {
    this.examFinished = false;
    this.examStarted = false;
    this.pendingResume = false;
    this.session = null;
    this.currentIndex = 0;
    this.finalScore = null;
    this.answers = {};
    this.openAnswers = {};
    this.lockedQuestionIds.clear();
    this.cameraReady = false;
    this.stopCamera();
    this.mediaStream = undefined;
    this.resetSnapshotPlan();
    this.stopVideoRecording(false);
    this.loadSessionInfo();
  }

  finishExamEarly(): void {
    this.api.finishExamSession(this.token).subscribe({
      next: (result) => {
        this.examFinalized = true;
        this.examFinished = true;
        this.canStartNewAttempt = false;
        this.canFinishEarly = false;
        if (result.final_score != null) {
          this.finalScore = result.final_score;
        }
        this.snackBar.open('Examen finalizado con la calificación del último intento', 'OK', {
          duration: 5000,
        });
      },
      error: (err) => {
        this.snackBar.open(err.error?.detail || 'No se pudo finalizar el examen', 'Cerrar', {
          duration: 5000,
        });
      },
    });
  }

  get displayTotalScore(): number | null {
    return this.session?.exam.total_score ?? this.examTotalScore;
  }

  ngOnDestroy(): void {
    this.examLockdown.disable();
    this.resetSnapshotPlan();
    this.stopVideoRecording(false);
    this.stopTimer();
    this.stopQuestionTimer();
    this.stopProctoring();
    this.stopCamera();
    document.removeEventListener('mousemove', this.onMouseMove);
    document.removeEventListener('visibilitychange', this.onVisibilityChange);
    window.removeEventListener('blur', this.onWindowBlur);
  }

  private onMouseMove = (e: MouseEvent): void => {
    if (!this.examStarted || this.examFinished) return;
    this.mouseEvents.push({ x: e.clientX, y: e.clientY, t: Date.now() });
    if (this.mouseEvents.length > 100) {
      this.mouseEvents = this.mouseEvents.slice(-50);
    }
  };

  private onVisibilityChange = (): void => {
    if (document.hidden) {
      void this.handleTabSwitchViolation();
    }
  };

  private onWindowBlur = (): void => {
    if (document.hidden || document.hasFocus()) return;
    void this.handleTabSwitchViolation();
  };

  private async handleTabSwitchViolation(): Promise<void> {
    if (
      this.tabViolationHandled ||
      !this.examStarted ||
      this.examFinished ||
      !this.session
    ) {
      return;
    }

    this.tabViolationHandled = true;
    this.stopTimer();
    this.stopQuestionTimer();
    this.stopProctoring();
    this.examLockdown.disable();

    try {
      await this.saveCurrentAnswerAsync();
      const result = await firstValueFrom(this.api.reportTabSwitchViolation(this.token));
      await this.completeViolationTermination(result);
    } catch (err: unknown) {
      const recovered = await this.tryRecoverViolationState();
      if (!recovered) {
        this.snackBar.open(this.extractErrorMessage(err), 'Cerrar', { duration: 5000 });
      }
    }
  }

  private async completeViolationTermination(result: {
    final_score: number | null;
    message: string;
  }): Promise<void> {
    this.examTerminatedForViolation = true;
    this.examFinalized = true;
    this.canStartNewAttempt = false;
    this.canFinishEarly = false;
    await this.completeExamSubmission(result.final_score);
    this.snackBar.open(result.message, 'OK', { duration: 6000 });
  }

  private async tryRecoverViolationState(): Promise<boolean> {
    try {
      const info = await firstValueFrom(this.api.getExamSessionInfo(this.token));
      if (!info['terminated_for_violation']) {
        return false;
      }
      const score = info['final_score'] != null ? Number(info['final_score']) : this.finalScore;
      await this.completeViolationTermination({
        final_score: score,
        message:
          'El examen fue cerrado por cambiar de pestaña o ventana. No podrás realizar más intentos.',
      });
      return true;
    } catch {
      return false;
    }
  }

  async enableCamera(): Promise<void> {
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user' },
        audio: false,
      });
      this.cameraReady = true;
      this.scheduleAttachStream('setup');
    } catch {
      this.snackBar.open('Debes habilitar la cámara para continuar', 'Cerrar', { duration: 5000 });
    }
  }

  get canStartExam(): boolean {
    return this.cameraReady && this.inviteeFullName.trim().length >= 2;
  }

  startExam(): void {
    if (this.examBlocked) {
      this.snackBar.open(this.blockMessage, 'Cerrar', { duration: 5000 });
      return;
    }
    if (!this.inviteeFullName.trim()) {
      this.snackBar.open('Ingresa tu nombre completo', 'Cerrar', { duration: 3000 });
      return;
    }
    if (!this.cameraReady) {
      this.snackBar.open('La cámara es obligatoria', 'Cerrar', { duration: 3000 });
      return;
    }

    this.api.startExamSession(this.token, true, this.inviteeFullName).subscribe({
      next: (session) => {
        this.pendingResume = false;
        this.applySession(session);
      },
      error: (err) => {
        const detail = err.error?.detail || 'Error';
        if (detail.includes('ya presentó') || detail.includes('en progreso')) {
          this.examBlocked = true;
          this.blockMessage = detail;
        }
        this.snackBar.open(detail, 'Cerrar', { duration: 5000 });
      },
    });
  }

  private applySession(session: ExamSession): void {
    this.session = session;
    this.remainingSeconds = session.remaining_seconds;
    this.examStarted = true;
    this.currentAttemptNumber = session.attempt.attempt_number ?? this.currentAttemptNumber;
    this.restoreSavedAnswers(session.saved_answers ?? []);
    this.lockedQuestionIds = new Set(session.locked_question_ids ?? []);
    this.currentIndex = Math.min(
      session.current_question_index ?? 0,
      Math.max(session.questions.length - 1, 0)
    );

    if (session.resumed) {
      this.snackBar.open('Examen reanudado donde lo dejaste', 'OK', { duration: 4000 });
    }

    this.startTimer();
    if (this.enforceQuestionTime) {
      const remainingForQuestion =
        session.question_remaining_seconds ?? this.currentQuestion?.time_seconds ?? 0;
      this.questionRemainingSeconds = remainingForQuestion;
      if (
        this.questionRemainingSeconds <= 0 &&
        this.currentQuestion &&
        !this.isQuestionLocked(this.currentQuestion.id)
      ) {
        void this.advanceFromCurrentQuestion(true);
        return;
      }
      this.startQuestionTimer();
    }

    this.startProctoring();
    this.examLockdown.enable();
    this.scheduleAttachStream('exam');
    this.setupQuestionSnapshots(session.questions.length);
    if (session.exam.require_attempt_video) {
      this.startVideoRecording();
    }
    if (!session.resumed) {
      setTimeout(() => this.captureSnapshot('start'), 500);
    }
    this.onQuestionDisplayed(this.currentIndex);
    this.saveProgress();
  }

  private restoreSavedAnswers(savedAnswers: SavedAnswer[]): void {
    this.answers = {};
    this.openAnswers = {};
    for (const saved of savedAnswers) {
      if (saved.open_text) {
        this.openAnswers[saved.question_id] = saved.open_text;
      }
      if (saved.selected_option_ids?.length) {
        this.answers[saved.question_id] = [...saved.selected_option_ids];
      }
    }
  }

  private saveProgress(): void {
    if (!this.session || !this.examStarted || this.examFinished) return;
    this.api
      .saveAttemptProgress(this.session.attempt.id, this.currentIndex, [...this.lockedQuestionIds])
      .subscribe();
  }

  private scheduleAttachStream(target: 'setup' | 'exam'): void {
    afterNextRender(
      () => {
        const videoRef = target === 'exam' ? this.examVideo : this.setupVideo;
        this.attachStreamToVideo(videoRef);
      },
      { injector: this.injector }
    );
  }

  private attachStreamToVideo(videoRef?: ElementRef<HTMLVideoElement>): void {
    const video = videoRef?.nativeElement ?? this.activeVideoElement;
    if (!video || !this.mediaStream) return;

    video.srcObject = this.mediaStream;
    void video.play().catch(() => {
      // Algunos navegadores requieren una interacción previa antes de reproducir.
    });
  }

  private get activeVideoElement(): HTMLVideoElement | undefined {
    if (this.examStarted) {
      return this.examVideo?.nativeElement;
    }
    return this.setupVideo?.nativeElement;
  }

  get requiresAttemptVideo(): boolean {
    return this.session?.exam.require_attempt_video ?? this.requireAttemptVideo;
  }

  get enforceQuestionTime(): boolean {
    return this.session?.exam.enforce_question_time ?? false;
  }

  get currentQuestion(): Question | null {
    return this.session?.questions[this.currentIndex] ?? null;
  }

  get progress(): number {
    if (!this.session) return 0;
    return ((this.currentIndex + 1) / this.session.questions.length) * 100;
  }

  formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  isQuestionLocked(questionId: string): boolean {
    return this.lockedQuestionIds.has(questionId);
  }

  isQuestionInputDisabled(question: Question): boolean {
    return this.enforceQuestionTime && this.isQuestionLocked(question.id);
  }

  goToQuestion(index: number): void {
    if (this.enforceQuestionTime) return;
    if (index >= 0 && index < (this.session?.questions.length ?? 0)) {
      this.saveCurrentAnswer();
      this.currentIndex = index;
      this.onQuestionDisplayed(index);
      this.saveProgress();
    }
  }

  get canAdvanceTimedQuestion(): boolean {
    const q = this.currentQuestion;
    return (
      this.enforceQuestionTime &&
      !!q &&
      this.isAnswered(q.id) &&
      !this.isQuestionLocked(q.id)
    );
  }

  nextQuestion(): void {
    if (this.enforceQuestionTime) {
      this.advanceFromCurrentQuestion(false);
      return;
    }
    this.saveCurrentAnswer();
    if (this.session && this.currentIndex < this.session.questions.length - 1) {
      this.currentIndex++;
      this.onQuestionDisplayed(this.currentIndex);
      this.saveProgress();
    }
  }

  prevQuestion(): void {
    if (this.enforceQuestionTime) return;
    this.saveCurrentAnswer();
    if (this.currentIndex > 0) {
      this.currentIndex--;
      this.saveProgress();
    }
  }

  isSelected(questionId: string, optionId: string): boolean {
    return this.answers[questionId]?.includes(optionId) ?? false;
  }

  isAnswered(questionId: string): boolean {
    if ((this.answers[questionId]?.length ?? 0) > 0) {
      return true;
    }
    return Boolean(this.openAnswers[questionId]?.trim());
  }

  toggleOption(question: Question, optionId: string): void {
    if (this.isQuestionInputDisabled(question)) return;
    if (question.question_type === 'multiple_choice') {
      const current = this.answers[question.id] || [];
      if (current.includes(optionId)) {
        this.answers[question.id] = current.filter((id) => id !== optionId);
      } else {
        this.answers[question.id] = [...current, optionId];
      }
    } else {
      this.answers[question.id] = [optionId];
    }
  }

  saveCurrentAnswer(): void {
    const q = this.currentQuestion;
    if (!q || !this.session) return;

    const optionIds = this.answers[q.id] || [];
    const openText = this.openAnswers[q.id];

    this.api
      .submitAnswer(this.session.attempt.id, q.id, optionIds, openText)
      .subscribe();
  }

  private async saveCurrentAnswerAsync(): Promise<void> {
    const q = this.currentQuestion;
    if (!q || !this.session) return;

    const optionIds = this.answers[q.id] || [];
    const openText = this.openAnswers[q.id];

    await firstValueFrom(
      this.api.submitAnswer(this.session.attempt.id, q.id, optionIds, openText)
    );
  }

  submitExam(): void {
    void this.finishExamSubmission();
  }

  private async finishExamSubmission(): Promise<void> {
    if (!this.session || this.isSubmitting) return;

    this.isSubmitting = true;
    this.saveCurrentAnswer();

    try {
      let skipVideoRequired = false;
      if (this.requiresAttemptVideo) {
        const uploaded = await this.tryUploadAttemptVideo();
        if (!uploaded) {
          skipVideoRequired = true;
        }
      }

      const result = await firstValueFrom(
        this.api.submitExam(this.session.attempt.id, skipVideoRequired)
      );
      await this.completeExamSubmission((result as { score: number | null }).score);
    } catch (err: unknown) {
      const recovered = await this.tryRecoverSubmittedState();
      if (recovered) {
        return;
      }
      this.snackBar.open(this.extractErrorMessage(err), 'Cerrar', { duration: 5000 });
    } finally {
      this.isSubmitting = false;
    }
  }

  private async completeExamSubmission(score: number | null): Promise<void> {
    this.examFinished = true;
    this.finalScore = score;
    this.examLockdown.disable();
    this.resetSnapshotPlan();
    this.stopVideoRecording(true);
    this.stopTimer();
    this.stopQuestionTimer();
    this.stopProctoring();
    this.stopCamera();

    try {
      await this.refreshAttemptOptions();
    } catch {
      // El examen ya fue enviado; la pantalla de resultado no debe bloquearse.
    }
  }

  private async refreshAttemptOptions(): Promise<void> {
    const info = await firstValueFrom(this.api.getExamSessionInfo(this.token));
    this.attemptsRemaining = Number(info['attempts_remaining'] ?? 0);
    this.canStartNewAttempt = Boolean(info['can_start_new_attempt']);
    this.canFinishEarly = Boolean(info['can_finish_early']);
    this.requiresNextAttempt = Boolean(info['requires_next_attempt']);
    if (info['current_attempt_number']) {
      this.currentAttemptNumber = Number(info['current_attempt_number']);
    }
  }

  private async tryRecoverSubmittedState(): Promise<boolean> {
    try {
      const info = await firstValueFrom(this.api.getExamSessionInfo(this.token));
      const status = String(info['attempt_status'] ?? '');
      if (status !== 'submitted' && status !== 'timed_out') {
        return false;
      }

      const score = info['final_score'] != null ? Number(info['final_score']) : this.finalScore;
      await this.completeExamSubmission(score);
      return true;
    } catch {
      return false;
    }
  }

  private extractErrorMessage(err: unknown): string {
    if (err instanceof HttpErrorResponse) {
      if (err.status === 413) {
        return 'El video del intento supera el tamaño máximo permitido. Finalice el examen en menos tiempo o contacte al administrador.';
      }
      const detail = err.error?.detail;
      if (typeof detail === 'string') {
        return detail;
      }
      if (Array.isArray(detail)) {
        return detail
          .map((item) => {
            if (typeof item === 'object' && item !== null && 'msg' in item) {
              return String((item as { msg: string }).msg);
            }
            return String(item);
          })
          .join('. ');
      }
    }
    if (err instanceof Error && err.message) {
      return err.message;
    }
    return 'No se pudo finalizar el examen';
  }

  private startQuestionTimer(): void {
    this.stopQuestionTimer();
    const q = this.currentQuestion;
    if (!q || this.isQuestionLocked(q.id)) return;

    if (this.questionRemainingSeconds <= 0) {
      this.questionRemainingSeconds = q.time_seconds;
    }
    this.questionTimerInterval = setInterval(() => {
      this.questionRemainingSeconds--;
      if (this.questionRemainingSeconds <= 0) {
        this.onQuestionTimeExpired();
      }
    }, 1000);
  }

  private stopQuestionTimer(): void {
    if (this.questionTimerInterval) {
      clearInterval(this.questionTimerInterval);
      this.questionTimerInterval = undefined;
    }
  }

  private advanceFromCurrentQuestion(timedOut: boolean): void {
    if (!this.session || this.examFinished) return;

    const q = this.currentQuestion;
    if (!q || this.isQuestionLocked(q.id)) return;

    if (this.enforceQuestionTime && !timedOut && !this.isAnswered(q.id)) return;

    this.stopQuestionTimer();
    this.saveCurrentAnswer();
    this.lockedQuestionIds.add(q.id);

    if (timedOut) {
      this.snackBar.open('Tiempo agotado para esta pregunta', 'OK', { duration: 3000 });
    }

    const isLast = this.currentIndex >= this.session.questions.length - 1;
    if (isLast) {
      this.submitExam();
      return;
    }

    this.currentIndex++;
    this.onQuestionDisplayed(this.currentIndex);
    this.saveProgress();
    this.questionRemainingSeconds = 0;
    this.startQuestionTimer();
  }

  private onQuestionTimeExpired(): void {
    this.advanceFromCurrentQuestion(true);
  }

  private startTimer(): void {
    this.timerInterval = setInterval(() => {
      this.remainingSeconds--;
      if (this.remainingSeconds <= 0) {
        this.submitExam();
        this.snackBar.open('Tiempo agotado. Examen enviado automáticamente.', 'OK', { duration: 5000 });
      }
    }, 1000);
  }

  private stopTimer(): void {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
    }
  }

  private startProctoring(): void {
    this.proctoringInterval = setInterval(() => this.captureAndAnalyze(), 5000);
  }

  private stopProctoring(): void {
    if (this.proctoringInterval) {
      clearInterval(this.proctoringInterval);
    }
  }

  private startVideoRecording(): void {
    if (!this.mediaStream || typeof MediaRecorder === 'undefined') {
      this.snackBar.open('Tu navegador no soporta grabación de video', 'Cerrar', { duration: 5000 });
      return;
    }

    this.recordedVideoChunks = [];
    try {
      const mimeType = this.getSupportedVideoMimeType();
      const options: MediaRecorderOptions = {
        videoBitsPerSecond: 350_000,
      };
      if (MediaRecorder.isTypeSupported(mimeType)) {
        options.mimeType = mimeType;
      }
      this.mediaRecorder = new MediaRecorder(this.mediaStream, options);
    } catch {
      this.mediaRecorder = new MediaRecorder(this.mediaStream, { videoBitsPerSecond: 350_000 });
    }

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.recordedVideoChunks.push(event.data);
      }
    };
    this.mediaRecorder.onerror = () => {
      this.isRecordingVideo = false;
      this.snackBar.open('Error al grabar el video del intento', 'Cerrar', { duration: 4000 });
    };
    this.mediaRecorder.start(1000);
    this.isRecordingVideo = true;
  }

  private getSupportedVideoMimeType(): string {
    const candidates = ['video/webm;codecs=vp8', 'video/webm', 'video/mp4'];
    return candidates.find((type) => MediaRecorder.isTypeSupported(type)) ?? 'video/webm';
  }

  private async tryUploadAttemptVideo(): Promise<boolean> {
    let blob: Blob;
    try {
      blob = await this.prepareAttemptVideoBlob();
    } catch (err: unknown) {
      this.snackBar.open(this.extractErrorMessage(err), 'Cerrar', { duration: 5000 });
      return false;
    }

    for (let attempt = 1; attempt <= this.maxVideoUploadAttempts; attempt++) {
      try {
        await firstValueFrom(this.api.uploadAttemptVideo(this.session!.attempt.id, blob));
        if (attempt > 1) {
          this.snackBar.open('Video del intento enviado correctamente', 'OK', { duration: 3000 });
        }
        return true;
      } catch {
        const isLastAttempt = attempt === this.maxVideoUploadAttempts;
        const message = isLastAttempt
          ? 'No se pudo enviar el video tras 3 intentos. El examen se enviará sin video.'
          : `Error al enviar el video (intento ${attempt} de ${this.maxVideoUploadAttempts}). Reintentando...`;
        this.snackBar.open(message, isLastAttempt ? 'OK' : 'Cerrar', {
          duration: isLastAttempt ? 6000 : 4000,
        });
        if (isLastAttempt) {
          return false;
        }
        await this.delay(attempt * 1000);
      }
    }

    return false;
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private async prepareAttemptVideoBlob(): Promise<Blob> {
    if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
      throw new Error('No hay grabación de video disponible');
    }

    const recorder = this.mediaRecorder;
    await new Promise<void>((resolve, reject) => {
      const onStop = (): void => {
        recorder.removeEventListener('stop', onStop);
        resolve();
      };
      recorder.addEventListener('stop', onStop);
      recorder.addEventListener(
        'error',
        () => reject(new Error('Error al detener la grabación de video')),
        { once: true }
      );

      try {
        if (recorder.state === 'recording') {
          recorder.requestData();
        }
        recorder.stop();
      } catch {
        reject(new Error('Error al detener la grabación de video'));
      }
    });

    this.isRecordingVideo = false;
    this.mediaRecorder = undefined;

    const mimeType = recorder.mimeType || 'video/webm';
    const blob = new Blob(this.recordedVideoChunks, { type: mimeType });
    if (!blob.size) {
      throw new Error('La grabación de video está vacía');
    }

    return blob;
  }

  private stopVideoRecording(clearChunks: boolean): void {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      try {
        if (this.mediaRecorder.state === 'recording') {
          this.mediaRecorder.requestData();
        }
        this.mediaRecorder.stop();
      } catch {
        // Ignorar errores al detener un grabador ya finalizado.
      }
    }
    this.mediaRecorder = undefined;
    this.isRecordingVideo = false;
    if (clearChunks) {
      this.recordedVideoChunks = [];
    }
  }

  private setupQuestionSnapshots(questionCount: number): void {
    this.resetSnapshotPlan();
    if (questionCount <= 0) return;

    const targetCount = Math.min(this.progressSnapshotCount, questionCount);
    const indices = Array.from({ length: questionCount }, (_, index) => index);
    for (let index = indices.length - 1; index > 0; index -= 1) {
      const swapIndex = Math.floor(Math.random() * (index + 1));
      [indices[index], indices[swapIndex]] = [indices[swapIndex], indices[index]];
    }
    indices.slice(0, targetCount).forEach((index) => this.snapshotQuestionIndices.add(index));
  }

  private resetSnapshotPlan(): void {
    this.snapshotQuestionIndices.clear();
    this.capturedSnapshotQuestions.clear();
  }

  private onQuestionDisplayed(questionIndex: number): void {
    if (!this.examStarted || this.examFinished) return;
    if (!this.snapshotQuestionIndices.has(questionIndex)) return;
    if (this.capturedSnapshotQuestions.has(questionIndex)) return;

    this.capturedSnapshotQuestions.add(questionIndex);
    setTimeout(() => this.captureSnapshot('progress'), 300);
  }

  private captureSnapshot(snapshotType: 'start' | 'progress'): void {
    const video = this.activeVideoElement;
    if (!this.session || !video || !this.canvasElement?.nativeElement) return;

    const canvas = this.canvasElement.nativeElement;
    canvas.width = video.videoWidth || 320;
    canvas.height = video.videoHeight || 240;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (blob && this.session) {
          this.api.uploadAttemptSnapshot(this.session.attempt.id, snapshotType, blob).subscribe();
        }
      },
      'image/jpeg',
      0.8
    );
  }

  private captureAndAnalyze(): void {
    const video = this.activeVideoElement;
    if (!this.session || !video || !this.canvasElement?.nativeElement) return;
    const canvas = this.canvasElement.nativeElement;
    canvas.width = video.videoWidth || 320;
    canvas.height = video.videoHeight || 240;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      if (blob && this.session) {
        this.api
          .sendProctoringData(this.session.attempt.id, blob, [...this.mouseEvents])
          .subscribe({
            next: (result: any) => {
              if (result.fraud_detected) {
                this.snackBar.open('Comportamiento sospechoso detectado', 'OK', { duration: 3000 });
              }
            },
          });
        this.mouseEvents = [];
      }
    }, 'image/jpeg', 0.7);
  }

  private stopCamera(): void {
    this.stopVideoRecording(false);
    this.mediaStream?.getTracks().forEach((t) => t.stop());
    this.mediaStream = undefined;
  }
}
