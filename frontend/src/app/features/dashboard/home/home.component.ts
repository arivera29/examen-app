import { Component } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [MatCardModule, MatIconModule],
  template: `
    <h1>Bienvenido a tu workspace</h1>
    <div class="cards">
      <mat-card>
        <mat-card-header>
          <mat-icon mat-card-avatar>library_books</mat-icon>
          <mat-card-title>Bancos de preguntas</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          Crea y organiza preguntas por temática: base de datos, software y programación.
        </mat-card-content>
      </mat-card>
      <mat-card>
        <mat-card-header>
          <mat-icon mat-card-avatar>assignment</mat-icon>
          <mat-card-title>Exámenes</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          Configura exámenes, invita participantes y revisa informes de calificación.
        </mat-card-content>
      </mat-card>
      <mat-card>
        <mat-card-header>
          <mat-icon mat-card-avatar>videocam</mat-icon>
          <mat-card-title>Proctoring</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          Detección de fraude con cámara y análisis de comportamiento durante el examen.
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: `
    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1rem;
      margin-top: 1rem;
    }
  `,
})
export class HomeComponent {}
