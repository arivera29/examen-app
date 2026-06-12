import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        AuthService,
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
    localStorage.clear();
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should login and store tokens', () => {
    service.login('test@test.com', 'password123').subscribe((tokens) => {
      expect(tokens.access_token).toBe('token123');
      expect(service.isAuthenticated()).toBeTrue();
    });

    const req = httpMock.expectOne(`${environment.apiUrl}/auth/login`);
    expect(req.request.method).toBe('POST');
    req.flush({ access_token: 'token123', refresh_token: 'refresh123', token_type: 'bearer' });
  });

  it('should logout and clear tokens', () => {
    localStorage.setItem('access_token', 'token');
    service.logout();
    expect(service.isAuthenticated()).toBeFalse();
  });

  it('should treat expired token as unauthenticated', () => {
    const expiredToken = createJwt(-60);
    localStorage.setItem('access_token', expiredToken);
    expect(service.isAuthenticated()).toBeFalse();
    expect(service.isAccessTokenExpired()).toBeTrue();
  });

  it('should treat valid token as authenticated', () => {
    const validToken = createJwt(3600);
    localStorage.setItem('access_token', validToken);
    expect(service.isAuthenticated()).toBeTrue();
    expect(service.isAccessTokenExpired()).toBeFalse();
  });
});

function createJwt(expOffsetSeconds: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + expOffsetSeconds }));
  return `${header}.${payload}.signature`;
}
