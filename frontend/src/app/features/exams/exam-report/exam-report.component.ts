import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../../core/services/api.service';
import { ExamReport, IndividualReport } from '../../../core/models';
import {
  AttemptAnswersDialogComponent,
} from './attempt-answers-dialog.component';
import {
  DeleteInviteeResultsDialogComponent,
} from './delete-invitee-results-dialog.component';

@Component({
  selector: 'app-exam-report',
  standalone: true,
  imports: [
    RouterLink,
    DecimalPipe,
    MatCardModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
    MatDialogModule,
    MatSnackBarModule,
  ],
  templateUrl: './exam-report.component.html',
  styleUrl: './exam-report.component.scss',
})
export class ExamReportComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ApiService);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  examId = '';
  report: ExamReport | null = null;
  deletingEmail: string | null = null;
  exportingReport = false;
  displayedColumns = [
    'name',
    'email',
    'attempt',
    'score',
    'correct',
    'incorrect',
    'percentage',
    'status',
    'fraud_score',
    'actions',
  ];

  ngOnInit(): void {
    this.examId = this.route.snapshot.paramMap.get('id')!;
    this.loadReport();
  }

  loadReport(): void {
    this.api.getExamReport(this.examId).subscribe({
      next: (report) => (this.report = report),
      error: (err) =>
        this.snackBar.open(err.error?.detail || 'Error al cargar informe', 'Cerrar', {
          duration: 4000,
        }),
    });
  }

  exportReport(): void {
    if (!this.report || this.exportingReport) return;

    this.exportingReport = true;
    this.api.downloadExamReportExport(this.examId).subscribe({
      next: (blob) => {
        this.exportingReport = false;
        const safeTitle = this.report!.exam_title
          .replace(/[^\w\-]+/g, '-')
          .replace(/-+/g, '-')
          .replace(/^-|-$/g, '') || 'examen';
        const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `informe-${safeTitle}-${stamp}.xlsx`;
        anchor.click();
        URL.revokeObjectURL(url);
        this.snackBar.open('Informe exportado a Excel', 'OK', { duration: 3000 });
      },
      error: (err) => {
        this.exportingReport = false;
        this.snackBar.open(err.error?.detail || 'Error al exportar informe', 'Cerrar', {
          duration: 4000,
        });
      },
    });
  }

  viewAnswers(row: IndividualReport): void {
    this.dialog.open(AttemptAnswersDialogComponent, {
      width: '760px',
      maxWidth: '95vw',
      maxHeight: '90vh',
      data: {
        examId: this.examId,
        reportRow: row,
      },
    });
  }

  confirmDeleteResults(row: IndividualReport): void {
    const dialogRef = this.dialog.open(DeleteInviteeResultsDialogComponent, {
      width: '480px',
      maxWidth: '95vw',
      data: {
        name: row.invitee_full_name,
        email: row.invitee_email,
        attemptsUsed: row.attempts_used,
      },
    });

    dialogRef.afterClosed().subscribe((confirmed) => {
      if (!confirmed) return;
      this.deleteResults(row);
    });
  }

  private deleteResults(row: IndividualReport): void {
    this.deletingEmail = row.invitee_email;
    this.api.deleteInviteeExamResults(this.examId, row.invitee_email).subscribe({
      next: (result) => {
        this.deletingEmail = null;
        const count = result.deleted_attempts;
        const message =
          count === 1
            ? 'Resultados del invitado eliminados'
            : `Se eliminaron ${count} intentos del invitado`;
        this.snackBar.open(message, 'OK', { duration: 3000 });
        this.loadReport();
      },
      error: (err) => {
        this.deletingEmail = null;
        this.snackBar.open(err.error?.detail || 'Error al eliminar resultados', 'Cerrar', {
          duration: 4000,
        });
      },
    });
  }
}
