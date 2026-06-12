import { Component, inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';

export interface DeleteExamDialogData {
  title: string;
  hasAttempts: boolean;
}

@Component({
  selector: 'app-delete-exam-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>Eliminar examen</h2>
    <mat-dialog-content>
      <p>
        ¿Eliminar el examen <strong>{{ data.title }}</strong>?
      </p>
      @if (data.hasAttempts) {
        <p>
          Este examen tiene intentos registrados. Se eliminarán invitaciones, intentos, respuestas,
          fotos, videos y eventos de supervisión asociados.
        </p>
      }
      <p class="warning">Esta acción no se puede deshacer.</p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancelar</button>
      <button mat-flat-button color="warn" [mat-dialog-close]="true">Eliminar</button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .warning {
        color: #c62828;
        font-size: 0.9rem;
      }
    `,
  ],
})
export class DeleteExamDialogComponent {
  readonly data = inject<DeleteExamDialogData>(MAT_DIALOG_DATA);
}
