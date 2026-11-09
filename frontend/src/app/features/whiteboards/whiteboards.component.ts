import { DatePipe } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatMenuModule } from '@angular/material/menu';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../core/services/api.service';
import { WhiteboardSummary } from '../../core/models';
import { BACKGROUND_PRESETS, CANVAS_SIZE_PRESETS } from './whiteboard.models';
import { DeleteWhiteboardDialogComponent } from './delete-whiteboard-dialog.component';

@Component({
  selector: 'app-whiteboards',
  standalone: true,
  imports: [
    DatePipe,
    ReactiveFormsModule,
    MatButtonModule,
    MatCardModule,
    MatDialogModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatMenuModule,
    MatSelectModule,
    MatSnackBarModule,
    MatTooltipModule,
  ],
  templateUrl: './whiteboards.component.html',
  styleUrl: './whiteboards.component.scss',
})
export class WhiteboardsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  readonly backgroundPresets = BACKGROUND_PRESETS;
  readonly sizePresets = CANVAS_SIZE_PRESETS;

  whiteboards: WhiteboardSummary[] = [];
  loading = true;
  showForm = false;
  creating = false;
  renamingId: string | null = null;

  form = this.fb.nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(255)]],
    background_color: ['#ffffff'],
    size: [0],
  });

  renameForm = this.fb.nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(255)]],
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading = true;
    this.api.getWhiteboards().subscribe({
      next: (whiteboards) => {
        this.whiteboards = whiteboards;
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.showError(err, 'No se pudieron cargar las pizarras');
      },
    });
  }

  openCreateForm(): void {
    this.form.reset({ name: '', background_color: '#ffffff', size: 0 });
    this.showForm = true;
  }

  cancelForm(): void {
    this.showForm = false;
  }

  create(): void {
    if (this.form.invalid || this.creating) return;
    const { name, background_color, size } = this.form.getRawValue();
    const preset = this.sizePresets[size] ?? this.sizePresets[0];
    this.creating = true;
    this.api
      .createWhiteboard({ name: name.trim(), background_color, width: preset.width, height: preset.height })
      .subscribe({
        next: (whiteboard) => {
          this.creating = false;
          this.showForm = false;
          this.router.navigate(['/dashboard/whiteboards', whiteboard.id]);
        },
        error: (err) => {
          this.creating = false;
          this.showError(err, 'No se pudo crear la pizarra');
        },
      });
  }

  open(whiteboard: WhiteboardSummary): void {
    if (this.renamingId) return;
    this.router.navigate(['/dashboard/whiteboards', whiteboard.id]);
  }

  startRename(whiteboard: WhiteboardSummary): void {
    this.renamingId = whiteboard.id;
    this.renameForm.reset({ name: whiteboard.name });
  }

  cancelRename(): void {
    this.renamingId = null;
  }

  saveRename(whiteboard: WhiteboardSummary): void {
    if (this.renameForm.invalid) return;
    const name = this.renameForm.getRawValue().name.trim();
    if (!name || name === whiteboard.name) {
      this.renamingId = null;
      return;
    }
    this.api.updateWhiteboard(whiteboard.id, { name }).subscribe({
      next: () => {
        this.renamingId = null;
        this.snackBar.open('Pizarra renombrada', 'OK', { duration: 2000 });
        this.load();
      },
      error: (err) => this.showError(err, 'No se pudo renombrar la pizarra'),
    });
  }

  duplicate(whiteboard: WhiteboardSummary): void {
    this.api.duplicateWhiteboard(whiteboard.id).subscribe({
      next: () => {
        this.snackBar.open('Pizarra duplicada', 'OK', { duration: 2000 });
        this.load();
      },
      error: (err) => this.showError(err, 'No se pudo duplicar la pizarra'),
    });
  }

  confirmDelete(whiteboard: WhiteboardSummary): void {
    this.dialog
      .open(DeleteWhiteboardDialogComponent, { data: { name: whiteboard.name }, width: '420px' })
      .afterClosed()
      .subscribe((confirmed) => {
        if (!confirmed) return;
        this.api.deleteWhiteboard(whiteboard.id).subscribe({
          next: () => {
            this.whiteboards = this.whiteboards.filter((w) => w.id !== whiteboard.id);
            this.snackBar.open('Pizarra eliminada', 'OK', { duration: 2000 });
          },
          error: (err) => this.showError(err, 'No se pudo eliminar la pizarra'),
        });
      });
  }

  private showError(err: { error?: { detail?: unknown } }, fallback: string): void {
    const detail = err.error?.detail;
    this.snackBar.open(typeof detail === 'string' ? detail : fallback, 'Cerrar', { duration: 4000 });
  }
}
