import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, map, tap, throwError } from 'rxjs';
import { environment } from '../../environments/environment';

interface TokenPair {
  access: string;
  refresh: string;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  is_admin: boolean;
  admin_verification_password?: string;
}

export interface RegisteredUser {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
}

const ACCESS_KEY = 'gpd_access';
const REFRESH_KEY = 'gpd_refresh';
const USER_KEY = 'gpd_user';

/**
 * Handles JWT auth against Django SimpleJWT endpoints. Tokens live in
 * localStorage; `isAuthenticated$` lets the shell react to login/logout.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly base = environment.apiUrl;
  private readonly authState$ = new BehaviorSubject<boolean>(this.hasToken());

  readonly isAuthenticated$ = this.authState$.asObservable();

  constructor(
    private http: HttpClient,
    private router: Router,
  ) {}

  login(username: string, password: string): Observable<void> {
    return this.http
      .post<TokenPair>(`${this.base}/auth/token/`, { username, password })
      .pipe(
        tap((tokens) => this.persist(tokens, username)),
        map(() => void 0),
      );
  }

  register(payload: RegisterPayload): Observable<RegisteredUser> {
    return this.http.post<RegisteredUser>(
      `${this.base}/auth/register/`,
      payload,
    );
  }

  logout(): void {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    this.authState$.next(false);
    this.router.navigateByUrl('/login');
  }

  /**
   * Exchange the stored refresh token for a new access token (and, with
   * rotation enabled, a new refresh token). Emits the fresh access token so the
   * interceptor can replay the original request. Errors if no refresh token is
   * present so the caller can force a logout.
   */
  refreshToken(): Observable<string> {
    const refresh = localStorage.getItem(REFRESH_KEY);
    if (!refresh) {
      return throwError(() => new Error('No refresh token available.'));
    }
    return this.http
      .post<{ access: string; refresh?: string }>(
        `${this.base}/auth/token/refresh/`,
        { refresh },
      )
      .pipe(
        tap((tokens) => {
          localStorage.setItem(ACCESS_KEY, tokens.access);
          // With ROTATE_REFRESH_TOKENS the server returns a new refresh token.
          if (tokens.refresh) {
            localStorage.setItem(REFRESH_KEY, tokens.refresh);
          }
        }),
        map((tokens) => tokens.access),
      );
  }

  get accessToken(): string | null {
    return localStorage.getItem(ACCESS_KEY);
  }

  get username(): string | null {
    return localStorage.getItem(USER_KEY);
  }

  hasToken(): boolean {
    return !!this.accessToken;
  }

  private persist(tokens: TokenPair, username: string): void {
    localStorage.setItem(ACCESS_KEY, tokens.access);
    localStorage.setItem(REFRESH_KEY, tokens.refresh);
    localStorage.setItem(USER_KEY, username);
    this.authState$.next(true);
  }
}
