import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

function isPublicAuthEndpoint(url: string): boolean {
  return url.includes('/auth/login') || url.includes('/auth/register');
}

function isExamPublicEndpoint(url: string): boolean {
  if (url.includes('/exam-session/')) {
    return true;
  }
  // Rutas públicas del examen para invitados (no el informe bajo /exams/.../attempts/)
  return url.includes('/attempts/') && !url.includes('/exams/');
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const token = auth.getToken();

  if (token && auth.isAccessTokenExpired(token)) {
    auth.handleSessionExpired();
    return throwError(() => new Error('Session expired'));
  }

  if (token && !isExamPublicEndpoint(req.url)) {
    req = req.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`,
        'X-Frontend-Url': window.location.origin,
      },
    });
  } else {
    req = req.clone({
      setHeaders: { 'X-Frontend-Url': window.location.origin },
    });
  }

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      if (
        error.status === 401 &&
        token &&
        !isPublicAuthEndpoint(req.url) &&
        !isExamPublicEndpoint(req.url)
      ) {
        auth.handleSessionExpired();
      }
      return throwError(() => error);
    })
  );
};
