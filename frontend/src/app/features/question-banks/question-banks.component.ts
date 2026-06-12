import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../core/services/api.service';
import { QuestionBank } from '../../core/models';

@Component({
  selector: 'app-question-banks',
  standalone: true,
  imports: [
    RouterLink,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
    MatSnackBarModule,
  ],
  templateUrl: './question-banks.component.html',
  styleUrl: './question-banks.component.scss',
})
export class QuestionBanksComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly snackBar = inject(MatSnackBar);

  banks: QuestionBank[] = [];
  showForm = false;
  editingBankId: string | null = null;

  form = this.fb.group({
    name: ['', Validators.required],
    description: [''],
  });

  ngOnInit(): void {
    this.loadBanks();
  }

  get isEditing(): boolean {
    return this.editingBankId !== null;
  }

  loadBanks(): void {
    this.api.getQuestionBanks().subscribe((banks) => (this.banks = banks));
  }

  openCreateForm(): void {
    this.editingBankId = null;
    this.form.reset();
    this.showForm = true;
  }

  openEditForm(bank: QuestionBank): void {
    this.editingBankId = bank.id;
    this.form.patchValue({ name: bank.name, description: bank.description });
    this.showForm = true;
  }

  cancelForm(): void {
    this.showForm = false;
    this.editingBankId = null;
    this.form.reset();
  }

  saveBank(): void {
    if (this.form.invalid) return;
    const { name, description } = this.form.getRawValue();

    const request$ = this.isEditing
      ? this.api.updateQuestionBank(this.editingBankId!, name!, description || '')
      : this.api.createQuestionBank(name!, description || '');

    request$.subscribe({
      next: () => {
        this.cancelForm();
        this.loadBanks();
        this.snackBar.open(this.isEditing ? 'Banco actualizado' : 'Banco creado', 'OK', {
          duration: 2000,
        });
      },
      error: (err) => this.snackBar.open(err.error?.detail || 'Error', 'Cerrar', { duration: 4000 }),
    });
  }

  deleteBank(bank: QuestionBank): void {
    if (!confirm(`¿Eliminar el banco "${bank.name}"? Se eliminarán también sus preguntas.`)) return;

    this.api.deleteQuestionBank(bank.id).subscribe({
      next: () => {
        this.snackBar.open('Banco eliminado', 'OK', { duration: 2000 });
        this.loadBanks();
      },
      error: (err) => this.snackBar.open(err.error?.detail || 'Error al eliminar', 'Cerrar', {
        duration: 4000,
      }),
    });
  }

  canDelete(bank: QuestionBank): boolean {
    return !bank.has_exams;
  }
}
