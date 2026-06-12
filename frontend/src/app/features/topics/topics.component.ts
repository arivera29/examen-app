import { Component, inject, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../core/services/api.service';
import { Topic } from '../../core/models';

@Component({
  selector: 'app-topics',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatSnackBarModule,
    MatTooltipModule,
  ],
  templateUrl: './topics.component.html',
  styleUrl: './topics.component.scss',
})
export class TopicsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly snackBar = inject(MatSnackBar);

  topics: Topic[] = [];
  showForm = false;
  editingTopicId: string | null = null;

  form = this.fb.group({
    name: ['', Validators.required],
    description: [''],
  });

  ngOnInit(): void {
    this.loadTopics();
  }

  get isEditing(): boolean {
    return this.editingTopicId !== null;
  }

  loadTopics(): void {
    this.api.getTopics().subscribe((topics) => (this.topics = topics));
  }

  openCreateForm(): void {
    this.editingTopicId = null;
    this.form.reset();
    this.showForm = true;
  }

  openEditForm(topic: Topic): void {
    this.editingTopicId = topic.id;
    this.form.patchValue({ name: topic.name, description: topic.description });
    this.showForm = true;
  }

  cancelForm(): void {
    this.showForm = false;
    this.editingTopicId = null;
    this.form.reset();
  }

  saveTopic(): void {
    if (this.form.invalid) return;
    const { name, description } = this.form.getRawValue();
    const request$ = this.isEditing
      ? this.api.updateTopic(this.editingTopicId!, name!, description || '')
      : this.api.createTopic(name!, description || '');

    request$.subscribe({
      next: () => {
        this.cancelForm();
        this.loadTopics();
        this.snackBar.open(this.isEditing ? 'Temática actualizada' : 'Temática creada', 'OK', {
          duration: 2000,
        });
      },
      error: (err) => this.snackBar.open(err.error?.detail || 'Error', 'Cerrar', { duration: 4000 }),
    });
  }

  deleteTopic(topic: Topic): void {
    if (!confirm(`¿Eliminar la temática "${topic.name}"? Las preguntas asociadas quedarán sin temática.`)) {
      return;
    }

    this.api.deleteTopic(topic.id).subscribe({
      next: () => {
        this.loadTopics();
        this.snackBar.open('Temática eliminada', 'OK', { duration: 2000 });
      },
      error: (err) => this.snackBar.open(err.error?.detail || 'Error al eliminar', 'Cerrar', {
        duration: 4000,
      }),
    });
  }
}
