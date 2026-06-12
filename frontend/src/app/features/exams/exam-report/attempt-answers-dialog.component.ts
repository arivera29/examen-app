import { Component, inject, OnInit } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../../core/services/api.service';
import { AttemptAnswersReport, AttemptSnapshot, IndividualReport } from '../../../core/models';

export interface AttemptAnswersDialogData {
  examId: string;
  reportRow: IndividualReport;
}

@Component({
  selector: 'app-attempt-answers-dialog',
  standalone: true,
  imports: [
    DatePipe,
    DecimalPipe,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
  ],
  templateUrl: './attempt-answers-dialog.component.html',
  styleUrl: './attempt-answers-dialog.component.scss',
})
export class AttemptAnswersDialogComponent implements OnInit {
  readonly data = inject<AttemptAnswersDialogData>(MAT_DIALOG_DATA);
  private readonly api = inject(ApiService);
  private readonly snackBar = inject(MatSnackBar);

  loading = true;
  detail: AttemptAnswersReport | null = null;

  ngOnInit(): void {
    this.api.getAttemptAnswersReport(this.data.examId, this.data.reportRow.attempt_id).subscribe({
      next: (detail) => {
        this.detail = detail;
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.snackBar.open(err.error?.detail || 'Error al cargar respuestas', 'Cerrar', {
          duration: 4000,
        });
      },
    });
  }

  answerLabel(answer: AttemptAnswersReport['answers'][number]): string {
    if (answer.open_text?.trim()) {
      return answer.open_text.trim();
    }
    if (answer.selected_options.length) {
      return answer.selected_options.join(', ');
    }
    return 'Sin respuesta';
  }

  resultLabel(answer: AttemptAnswersReport['answers'][number]): string {
    if (!answer.answered) {
      return 'Sin respuesta';
    }
    if (answer.is_correct === null) {
      return 'Pendiente de revisión';
    }
    return answer.is_correct ? 'Correcta' : 'Incorrecta';
  }

  resultClass(answer: AttemptAnswersReport['answers'][number]): string {
    if (!answer.answered || answer.is_correct === null) {
      return 'result-pending';
    }
    return answer.is_correct ? 'result-correct' : 'result-incorrect';
  }

  snapshotLabel(snapshot: AttemptSnapshot): string {
    return snapshot.snapshot_type === 'start' ? 'Inicio del examen' : 'Durante el examen';
  }
}
