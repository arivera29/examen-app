import { Component, inject, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSliderModule } from '@angular/material/slider';
import { ApiService } from '../../core/services/api.service';
import { Exam, QuestionBank } from '../../core/models';
import { DeleteExamDialogComponent } from './delete-exam-dialog.component';

@Component({
  selector: 'app-exams',
  standalone: true,
  imports: [
    RouterLink,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatCheckboxModule,
    MatSnackBarModule,
    MatIconModule,
    MatTooltipModule,
    MatDialogModule,
    MatSliderModule,
  ],
  templateUrl: './exams.component.html',
  styleUrl: './exams.component.scss',
})
export class ExamsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);

  exams: Exam[] = [];
  banks: QuestionBank[] = [];
  showForm = false;
  editingExamId: string | null = null;

  form = this.fb.group({
    title: ['', Validators.required],
    description: [''],
    question_bank_id: ['', Validators.required],
    mode: ['simulation', Validators.required],
    total_score: [100, [Validators.required, Validators.min(1)]],
    question_count: [10, [Validators.required, Validators.min(1)]],
    closes_at: [this.defaultClosesAtLocal(), Validators.required],
    random_selection: [true],
    enforce_question_time: [false],
    require_attempt_video: [false],
    max_attempts: [1, [Validators.required, Validators.min(1)]],
    attempt_policy: ['flexible', Validators.required],
    proctoring_sensitivity: [4, [Validators.required, Validators.min(1), Validators.max(10)]],
  });

  defaultClosesAtLocal(): string {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    return this.toDatetimeLocal(d.toISOString());
  }

  toDatetimeLocal(iso: string): string {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  formatClosesAt(iso: string): string {
    return new Date(iso).toLocaleString();
  }

  sensitivityLabel(value: number | null | undefined): string {
    const level = Number(value ?? 4);
    if (level <= 2) return 'Muy baja';
    if (level <= 4) return 'Baja';
    if (level <= 6) return 'Media';
    if (level <= 8) return 'Alta';
    return 'Muy alta';
  }

  ngOnInit(): void {
    this.loadData();
  }

  get isEditing(): boolean {
    return this.editingExamId !== null;
  }

  get editingExam(): Exam | undefined {
    return this.exams.find((e) => e.id === this.editingExamId);
  }

  get isRestrictedEdit(): boolean {
    return this.isEditing && !!this.editingExam?.has_attempts;
  }

  loadData(): void {
    this.api.getExams().subscribe((e) => (this.exams = e));
    this.api.getQuestionBanks().subscribe((b) => (this.banks = b));
  }

  openCreateForm(): void {
    this.editingExamId = null;
    this.form.reset({
      title: '',
      description: '',
      question_bank_id: '',
      mode: 'simulation',
      total_score: 100,
      question_count: 10,
      closes_at: this.defaultClosesAtLocal(),
      random_selection: true,
      enforce_question_time: false,
      require_attempt_video: false,
      max_attempts: 1,
      attempt_policy: 'flexible',
      proctoring_sensitivity: 4,
    });
    this.form.enable();
    this.showForm = true;
  }

  openEditForm(exam: Exam): void {
    this.editingExamId = exam.id;
    this.form.patchValue({
      title: exam.title,
      description: exam.description,
      question_bank_id: exam.question_bank_id,
      mode: exam.mode,
      total_score: exam.total_score,
      question_count: exam.question_count,
      closes_at: this.toDatetimeLocal(exam.closes_at),
      random_selection: exam.random_selection,
      enforce_question_time: exam.enforce_question_time,
      require_attempt_video: exam.require_attempt_video,
      max_attempts: exam.max_attempts,
      attempt_policy: exam.attempt_policy,
      proctoring_sensitivity: Math.round((exam.proctoring_sensitivity ?? 0.4) * 10),
    });
    if (exam.has_attempts) {
      this.form.get('question_bank_id')?.disable();
      this.form.get('mode')?.disable();
      this.form.get('total_score')?.disable();
      this.form.get('question_count')?.disable();
      this.form.get('closes_at')?.disable();
      this.form.get('random_selection')?.disable();
      this.form.get('enforce_question_time')?.disable();
      this.form.get('require_attempt_video')?.disable();
      this.form.get('max_attempts')?.disable();
      this.form.get('attempt_policy')?.disable();
      this.form.get('proctoring_sensitivity')?.disable();
    } else {
      this.form.enable();
    }
    this.showForm = true;
  }

  cancelForm(): void {
    this.showForm = false;
    this.editingExamId = null;
    this.form.enable();
  }

  saveExam(): void {
    if (this.form.invalid) return;

    const raw = this.form.getRawValue();
    const data = {
      title: String(raw.title ?? '').trim(),
      description: String(raw.description ?? '').trim(),
      question_bank_id: String(raw.question_bank_id ?? ''),
      mode: String(raw.mode ?? 'simulation'),
      total_score: Number(raw.total_score),
      question_count: Number(raw.question_count),
      closes_at: new Date(String(raw.closes_at)).toISOString(),
      random_selection: Boolean(raw.random_selection),
      enforce_question_time: Boolean(raw.enforce_question_time),
      require_attempt_video: Boolean(raw.require_attempt_video),
      max_attempts: Number(raw.max_attempts),
      attempt_policy: String(raw.attempt_policy ?? 'flexible'),
      proctoring_sensitivity: Number(raw.proctoring_sensitivity) / 10,
      selected_question_ids: [] as string[],
    };

    const request$ = this.isEditing
      ? this.api.updateExam(this.editingExamId!, data)
      : this.api.createExam(data);

    request$.subscribe({
      next: () => {
        const wasEditing = this.isEditing;
        this.cancelForm();
        this.loadData();
        this.snackBar.open(wasEditing ? 'Examen actualizado' : 'Examen creado', 'OK', {
          duration: 2000,
        });
      },
      error: (err) => this.snackBar.open(this.formatApiError(err), 'Cerrar', { duration: 4000 }),
    });
  }

  private formatApiError(err: { error?: { detail?: unknown } }): string {
    const detail = err.error?.detail;
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
    if (typeof detail === 'string') {
      return detail;
    }
    return 'Error';
  }

  deleteExam(exam: Exam): void {
    const dialogRef = this.dialog.open(DeleteExamDialogComponent, {
      width: '480px',
      maxWidth: '95vw',
      data: {
        title: exam.title,
        hasAttempts: Boolean(exam.has_attempts),
      },
    });

    dialogRef.afterClosed().subscribe((confirmed) => {
      if (!confirmed) return;

      this.api.deleteExam(exam.id).subscribe({
        next: () => {
          this.snackBar.open('Examen eliminado', 'OK', { duration: 2000 });
          this.loadData();
        },
        error: (err) =>
          this.snackBar.open(err.error?.detail || 'Error al eliminar', 'Cerrar', {
            duration: 4000,
          }),
      });
    });
  }
}
