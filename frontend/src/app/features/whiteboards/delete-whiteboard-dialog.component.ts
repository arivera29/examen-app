import { Component, inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';

export interface DeleteWhiteboardDialogData {
  name: string;
}

@Component({
  selector: 'app-delete-whiteboard-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>Eliminar pizarra</h2>
    <mat-dialog-content>
      <p>
        ¿Eliminar la pizarra <strong>{{ data.name }}</strong>?
      </p>
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
export class DeleteWhiteboardDialogComponent {
  readonly data = inject<DeleteWhiteboardDialogData>(MAT_DIALOG_DATA);
}
