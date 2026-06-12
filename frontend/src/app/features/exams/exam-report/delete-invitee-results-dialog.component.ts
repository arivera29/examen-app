import { Component, inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';

export interface DeleteInviteeResultsDialogData {
  name: string;
  email: string;
  attemptsUsed?: number;
}

@Component({
  selector: 'app-delete-invitee-results-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>Eliminar resultados del invitado</h2>
    <mat-dialog-content>
      <p>
        ¿Eliminar todos los intentos de
        <strong>{{ data.name || data.email }}</strong>?
      </p>
      @if (data.attemptsUsed && data.attemptsUsed > 1) {
        <p>Se eliminarán {{ data.attemptsUsed }} intentos registrados.</p>
      }
      <p class="warning">
        Esta acción no se puede deshacer. Se borrarán respuestas, fotos, video y eventos de
        supervisión asociados.
      </p>
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
export class DeleteInviteeResultsDialogComponent {
  readonly data = inject<DeleteInviteeResultsDialogData>(MAT_DIALOG_DATA);
}
