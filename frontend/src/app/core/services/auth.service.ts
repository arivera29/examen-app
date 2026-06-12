import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { TokenResponse, User } from '../models';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly currentUserSubject = new BehaviorSubject<User | null>(null);

  currentUser$ = this.currentUserSubject.asObservable();

  register(email: string, password: string, fullName: string): Observable<User> {
    return this.http.post<User>(`${environment.apiUrl}/auth/register`, {
      email,
      password,
      full_name: fullName,
    });
  }

  login(email: string, password: string, mfaCode?: string): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/login`, {
        email,
        password,
        mfa_code: mfaCode || null,
      })
      .pipe(tap((tokens) => this.storeTokens(tokens)));
  }

  setupMfa(): Observable<{ secret: string; provisioning_uri: string }> {
    return this.http.post<{ secret: string; provisioning_uri: string }>(
      `${environment.apiUrl}/auth/mfa/setup`,
      {}
    );
  }

  enableMfa(code: string): Observable<User> {
    return this.http.post<User>(`${environment.apiUrl}/auth/mfa/enable`, { code });
  }

  loadCurrentUser(): Observable<User> {
    return this.http.get<User>(`${environment.apiUrl}/auth/me`).pipe(
      tap((user) => this.currentUserSubject.next(user))
    );
  }

  logout(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    this.currentUserSubject.next(null);
    this.router.navigate(['/login']);
  }

  handleSessionExpired(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    this.currentUserSubject.next(null);
    if (!this.router.url.startsWith('/login')) {
      this.router.navigate(['/login'], { queryParams: { reason: 'session_expired' } });
    }
  }

  isAuthenticated(): boolean {
    const token = this.getToken();
    return !!token && !this.isAccessTokenExpired(token);
  }

  isAccessTokenExpired(token?: string | null): boolean {
    const value = token ?? this.getToken();
    if (!value) {
      return true;
    }

    try {
      const payloadPart = value.split('.')[1];
      if (!payloadPart) {
        return true;
      }
      const normalized = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
      const payload = JSON.parse(atob(normalized)) as { exp?: number };
      return typeof payload.exp !== 'number' || payload.exp * 1000 <= Date.now();
    } catch {
      return true;
    }
  }

  getToken(): string | null {
    return localStorage.getItem('access_token');
  }

  private storeTokens(tokens: TokenResponse): void {
    localStorage.setItem('access_token', tokens.access_token);
    localStorage.setItem('refresh_token', tokens.refresh_token);
  }
}
