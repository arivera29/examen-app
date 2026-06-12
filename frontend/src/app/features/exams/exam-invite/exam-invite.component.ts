import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../../core/services/api.service';
import { Invitation } from '../../../core/models';

@Component({
  selector: 'app-exam-invite',
  standalone: true,
  imports: [
    RouterLink,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSnackBarModule,
    MatTableModule,
    MatIconModule,
    MatTooltipModule,
  ],
  templateUrl: './exam-invite.component.html',
  styleUrl: './exam-invite.component.scss',
})
export class ExamInviteComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly snackBar = inject(MatSnackBar);

  examId = '';
  invitations: Invitation[] = [];
  loading = false;
  displayedColumns = ['email', 'status', 'attempt', 'attempts_count', 'sent_at', 'link', 'actions'];

  form = this.fb.group({
    emails: ['', Validators.required],
  });

  ngOnInit(): void {
    this.examId = this.route.snapshot.paramMap.get('id')!;
    this.loadInvitations();
  }

  loadInvitations(): void {
    this.loading = true;
    this.api.getExamInvitations(this.examId).subscribe({
      next: (items) => {
        this.invitations = items;
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.snackBar.open(err.error?.detail || 'Error al cargar invitaciones', 'Cerrar', {
          duration: 4000,
        });
      },
    });
  }

  sendInvites(): void {
    const emails = this.form.value.emails!
      .split(',')
      .map((e) => e.trim())
      .filter(Boolean);

    this.api.inviteToExam(this.examId, emails).subscribe({
      next: () => {
        this.form.reset();
        this.snackBar.open('Invitaciones enviadas', 'OK', { duration: 3000 });
        this.loadInvitations();
      },
      error: (err) => this.snackBar.open(err.error?.detail || 'Error', 'Cerrar', { duration: 4000 }),
    });
  }

  resendInvitation(invitation: Invitation): void {
    this.api.resendExamInvitation(this.examId, invitation.id).subscribe({
      next: () => {
        this.snackBar.open(`Enlace reenviado a ${invitation.invitee_email}`, 'OK', { duration: 3000 });
        this.loadInvitations();
      },
      error: (err) => this.snackBar.open(err.error?.detail || 'Error al reenviar', 'Cerrar', { duration: 4000 }),
    });
  }

  deleteInvitation(invitation: Invitation): void {
    if (!this.canDelete(invitation)) return;
    if (!confirm(`¿Eliminar la invitación de ${invitation.invitee_email}?`)) return;

    this.api.deleteExamInvitation(this.examId, invitation.id).subscribe({
      next: () => {
        this.snackBar.open('Invitación eliminada', 'OK', { duration: 2000 });
        this.loadInvitations();
      },
      error: (err) => this.snackBar.open(err.error?.detail || 'Error al eliminar', 'Cerrar', { duration: 4000 }),
    });
  }

  copyLink(link: string): void {
    navigator.clipboard.writeText(link).then(() => {
      this.snackBar.open('Enlace copiado al portapapeles', 'OK', { duration: 2000 });
    });
  }

  canDelete(invitation: Invitation): boolean {
    return !['in_progress', 'submitted', 'timed_out'].includes(invitation.attempt_status);
  }

  statusLabel(status: string): string {
    const labels: Record<string, string> = {
      pending: 'Pendiente',
      sent: 'Enviada',
      started: 'Iniciada',
      completed: 'Completada',
      expired: 'Expirada',
    };
    return labels[status] || status;
  }

  attemptLabel(status: string): string {
    const labels: Record<string, string> = {
      not_started: 'Sin iniciar',
      in_progress: 'En progreso',
      submitted: 'Enviado',
      timed_out: 'Tiempo agotado',
    };
    return labels[status] || status;
  }

  formatDate(value: string | null): string {
    if (!value) return '-';
    return new Date(value).toLocaleString('es-CO');
  }
}
