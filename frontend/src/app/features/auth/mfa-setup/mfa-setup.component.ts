import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-mfa-setup',
  standalone: true,
  imports: [FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatSnackBarModule],
  template: `
    <h1>Configurar MFA (Google Authenticator)</h1>
    <mat-card>
      @if (!provisioningUri) {
        <p>Protege tu cuenta con autenticación de dos factores.</p>
        <button mat-flat-button color="primary" (click)="setup()">Generar código QR</button>
      } @else {
        <p>Escanea este URI en Google Authenticator o ingresa el secreto manualmente:</p>
        <code class="secret">{{ secret }}</code>
        <p><a [href]="provisioningUri" target="_blank">Abrir en Authenticator</a></p>
        <mat-form-field appearance="outline">
          <mat-label>Código de verificación</mat-label>
          <input matInput [(ngModel)]="verifyCode" maxlength="6" />
        </mat-form-field>
        <br />
        <button mat-flat-button color="primary" (click)="enable()">Activar MFA</button>
      }
    </mat-card>
  `,
  styles: `
    .secret { display: block; padding: 1rem; background: #f5f5f5; margin: 1rem 0; word-break: break-all; }
  `,
})
export class MfaSetupComponent {
  private readonly auth = inject(AuthService);
  private readonly snackBar = inject(MatSnackBar);

  secret = '';
  provisioningUri = '';
  verifyCode = '';

  setup(): void {
    this.auth.setupMfa().subscribe({
      next: (res) => {
        this.secret = res.secret;
        this.provisioningUri = res.provisioning_uri;
      },
    });
  }

  enable(): void {
    this.auth.enableMfa(this.verifyCode).subscribe({
      next: () => this.snackBar.open('MFA activado correctamente', 'OK', { duration: 3000 }),
      error: (err) => this.snackBar.open(err.error?.detail || 'Error', 'Cerrar', { duration: 4000 }),
    });
  }
}
