import {
  HttpErrorResponse,
  HttpInterceptorFn,
  HttpRequest,
} from '@angular/common/http';
import { inject } from '@angular/core';
import {
  BehaviorSubject,
  catchError,
  filter,
  switchMap,
  take,
  throwError,
} from 'rxjs';
import { AuthService } from '../services/auth.service';

const ACCESS_KEY = 'gpd_access';

// Shared across interceptor invocations: a single refresh runs at a time and
// concurrent 401s queue on `refreshedToken$` until the new token arrives.
let isRefreshing = false;
const refreshedToken$ = new BehaviorSubject<string | null>(null);

function withAuth(
  req: HttpRequest<unknown>,
  token: string | null,
): HttpRequest<unknown> {
  return token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;
}

/**
 * Attaches the JWT Bearer token and transparently refreshes expired access
 * tokens on 401, replaying the original request. Concurrent 401s are queued so
 * only one refresh call is made; if the refresh itself fails, the user is
 * logged out.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  // Auth endpoints (login / refresh / register) must never carry a stale token
  // nor trigger the refresh loop on their own 401s.
  const isAuthEndpoint = req.url.includes('/auth/');

  const authReq = isAuthEndpoint ? req : withAuth(req, auth.accessToken);

  return next(authReq).pipe(
    catchError((error: unknown) => {
      if (
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        !isAuthEndpoint
      ) {
        return handle401(req, next, auth);
      }
      return throwError(() => error);
    }),
  );
};

function handle401(
  req: HttpRequest<unknown>,
  next: (r: HttpRequest<unknown>) => ReturnType<HttpInterceptorFn>,
  auth: AuthService,
) {
  if (!isRefreshing) {
    isRefreshing = true;
    // Reset the queue placeholder so queued requests wait for the new token.
    refreshedToken$.next(null);

    return auth.refreshToken().pipe(
      switchMap((newToken) => {
        isRefreshing = false;
        refreshedToken$.next(newToken);
        return next(withAuth(req, newToken));
      }),
      catchError((refreshError) => {
        // Refresh token expired/invalid → clean local state and go to /login.
        isRefreshing = false;
        auth.logout();
        return throwError(() => refreshError);
      }),
    );
  }

  // A refresh is already in flight: wait for it, then replay with the token.
  return refreshedToken$.pipe(
    filter((token): token is string => token !== null),
    take(1),
    switchMap((token) => next(withAuth(req, token ?? localStorage.getItem(ACCESS_KEY)))),
  );
}
