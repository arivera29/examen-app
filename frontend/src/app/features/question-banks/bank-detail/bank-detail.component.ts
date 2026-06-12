import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { ApiService } from '../../../core/services/api.service';
import { Question, Topic } from '../../../core/models';
import { QuestionFormDialogComponent } from './question-form-dialog.component';

@Component({
  selector: 'app-bank-detail',
  standalone: true,
  imports: [
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
    MatSnackBarModule,
    MatPaginatorModule,
    MatDialogModule,
  ],
  templateUrl: './bank-detail.component.html',
  styleUrl: './bank-detail.component.scss',
})
export class BankDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ApiService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);

  bankId = '';
  questions: Question[] = [];
  topics: Topic[] = [];
  pageIndex = 0;
  pageSize = 10;
  pageSizeOptions = [5, 10, 25, 50];
  totalQuestions = 0;

  ngOnInit(): void {
    this.bankId = this.route.snapshot.paramMap.get('id')!;
    this.loadQuestions();
    this.api.getTopics().subscribe((t) => (this.topics = t));
  }

  loadQuestions(): void {
    this.api.getQuestions(this.bankId, this.pageIndex + 1, this.pageSize).subscribe((result) => {
      this.questions = result.items;
      this.totalQuestions = result.total;
      if (result.page !== this.pageIndex + 1) {
        this.pageIndex = Math.max(0, result.page - 1);
      }
    });
  }

  onPageChange(event: PageEvent): void {
    this.pageIndex = event.pageIndex;
    this.pageSize = event.pageSize;
    this.loadQuestions();
  }

  openCreateForm(): void {
    this.openQuestionDialog();
  }

  openEditForm(question: Question): void {
    this.openQuestionDialog(question);
  }

  private openQuestionDialog(question?: Question): void {
    const dialogRef = this.dialog.open(QuestionFormDialogComponent, {
      width: '720px',
      maxWidth: '95vw',
      maxHeight: '90vh',
      autoFocus: 'first-tapable',
      data: {
        bankId: this.bankId,
        question,
        topics: this.topics,
      },
    });

    dialogRef.afterClosed().subscribe((saved) => {
      if (saved) {
        this.loadQuestions();
      }
    });
  }

  deleteQuestion(question: Question): void {
    if (!confirm(`¿Eliminar la pregunta "${question.text.slice(0, 50)}..."?`)) return;

    this.api.deleteQuestion(this.bankId, question.id).subscribe({
      next: () => {
        this.snackBar.open('Pregunta eliminada', 'OK', { duration: 2000 });
        this.loadQuestions();
      },
      error: (err) => this.snackBar.open(err.error?.detail || 'Error al eliminar', 'Cerrar', {
        duration: 4000,
      }),
    });
  }

  canDelete(question: Question): boolean {
    return !question.used_in_exam;
  }

  downloadBackup(): void {
    this.api.downloadQuestionBackup(this.bankId).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `backup-banco-${this.bankId}.json`;
        anchor.click();
        URL.revokeObjectURL(url);
        this.snackBar.open('Backup descargado', 'OK', { duration: 2000 });
      },
      error: (err) => this.snackBar.open(err.error?.detail || 'Error al descargar', 'Cerrar', {
        duration: 4000,
      }),
    });
  }

  onRestoreFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;

    const replace = confirm(
      '¿Reemplazar las preguntas del banco?\n\n' +
        'Aceptar: elimina las que no están en exámenes e importa el backup.\n' +
        'Cancelar: agrega las preguntas del backup sin eliminar las actuales.'
    );
    const mode = replace ? 'replace' : 'append';

    this.api.restoreQuestionBackup(this.bankId, file, mode).subscribe({
      next: (result) => {
        this.loadQuestions();
        this.api.getTopics().subscribe((t) => (this.topics = t));
        let message = `${result.imported_count} pregunta(s) restaurada(s)`;
        if (result.deleted_count > 0) {
          message += `, ${result.deleted_count} eliminada(s)`;
        }
        if (result.skipped_count > 0) {
          message += `, ${result.skipped_count} omitida(s)`;
        }
        this.snackBar.open(message, 'OK', { duration: 4000 });
      },
      error: (err) => this.snackBar.open(err.error?.detail || 'Error al restaurar', 'Cerrar', {
        duration: 4000,
      }),
    });
  }
}
