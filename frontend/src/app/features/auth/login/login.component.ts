import { Component, inject, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSnackBarModule,
  ],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly snackBar = inject(MatSnackBar);

  showMfa = false;

  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
    mfa_code: [''],
  });

  ngOnInit(): void {
    if (this.route.snapshot.queryParamMap.get('reason') === 'session_expired') {
      this.snackBar.open('Tu sesión expiró. Inicia sesión de nuevo.', 'Cerrar', {
        duration: 5000,
      });
    }
  }

  onSubmit(): void {
    if (this.form.invalid) return;

    const { email, password, mfa_code } = this.form.getRawValue();
    this.auth.login(email!, password!, mfa_code || undefined).subscribe({
      next: () => {
        this.auth.loadCurrentUser().subscribe(() => this.router.navigate(['/dashboard']));
      },
      error: (err) => {
        const detail = err.error?.detail || 'Error al iniciar sesión';
        if (detail.includes('MFA')) {
          this.showMfa = true;
        }
        this.snackBar.open(detail, 'Cerrar', { duration: 4000 });
      },
    });
  }
}
