import { Component, inject, OnInit } from '@angular/core';
import { FormArray, FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../../core/services/api.service';
import { Question, Topic } from '../../../core/models';

export interface QuestionFormDialogData {
  bankId: string;
  question?: Question;
  topics: Topic[];
}

@Component({
  selector: 'app-question-form-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatCheckboxModule,
    MatSnackBarModule,
  ],
  templateUrl: './question-form-dialog.component.html',
  styleUrl: './question-form-dialog.component.scss',
})
export class QuestionFormDialogComponent implements OnInit {
  private readonly dialogRef = inject(MatDialogRef<QuestionFormDialogComponent>);
  readonly data = inject<QuestionFormDialogData>(MAT_DIALOG_DATA);
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly snackBar = inject(MatSnackBar);

  editingQuestionId: string | null = null;

  questionTypes = [
    { value: 'single_choice', label: 'Selección única' },
    { value: 'multiple_choice', label: 'Selección múltiple' },
    { value: 'open', label: 'Abierta' },
    { value: 'true_false', label: 'Verdadero/Falso' },
  ];

  form = this.fb.group({
    text: ['', Validators.required],
    question_type: ['single_choice', Validators.required],
    topic_id: [''],
    time_seconds: [60, [Validators.required, Validators.min(10)]],
    options: this.fb.array([this.createOption(true), this.createOption(false)]),
    image: [null as File | null],
  });

  ngOnInit(): void {
    if (this.data.question) {
      this.populateForm(this.data.question);
    }
  }

  get isEditing(): boolean {
    return this.editingQuestionId !== null;
  }

  get options(): FormArray {
    return this.form.get('options') as FormArray;
  }

  createOption(isCorrect = false) {
    return this.fb.group({
      text: ['', Validators.required],
      is_correct: [isCorrect],
    });
  }

  addOption(): void {
    this.options.push(this.createOption());
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files?.length) {
      this.form.patchValue({ image: input.files[0] });
    }
  }

  saveQuestion(): void {
    if (this.form.invalid) return;

    const raw = this.form.getRawValue();
    const formData = new FormData();
    formData.append('text', raw.text!);
    formData.append('question_type', raw.question_type!);
    if (raw.topic_id) {
      formData.append('topic_id', raw.topic_id);
    }
    formData.append('time_seconds', String(raw.time_seconds));
    const optionsPayload =
      raw.question_type === 'open'
        ? []
        : raw.options!.map((o) => ({ text: o.text, is_correct: o.is_correct }));
    formData.append('options', JSON.stringify(optionsPayload));
    if (raw.image) {
      formData.append('image', raw.image);
    }

    const isEditing = this.isEditing;
    const request$ = isEditing
      ? this.api.updateQuestion(this.data.bankId, this.editingQuestionId!, formData)
      : this.api.createQuestion(this.data.bankId, formData);

    request$.subscribe({
      next: () => {
        this.snackBar.open(isEditing ? 'Pregunta actualizada' : 'Pregunta creada', 'OK', {
          duration: 2000,
        });
        this.dialogRef.close(true);
      },
      error: (err) => this.snackBar.open(err.error?.detail || 'Error', 'Cerrar', { duration: 4000 }),
    });
  }

  cancel(): void {
    this.dialogRef.close(false);
  }

  private populateForm(question: Question): void {
    this.editingQuestionId = question.id;
    this.options.clear();
    if (question.options.length) {
      for (const opt of question.options) {
        this.options.push(
          this.fb.group({
            text: [opt.text, Validators.required],
            is_correct: [opt.is_correct],
          })
        );
      }
    } else {
      this.options.push(this.createOption(true));
      this.options.push(this.createOption(false));
    }
    this.form.patchValue({
      text: question.text,
      question_type: question.question_type,
      topic_id: question.topic_id || '',
      time_seconds: question.time_seconds,
      image: null,
    });
  }
}
