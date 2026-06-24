import { HttpInterceptorFn } from '@angular/common/http';

const ACCESS_KEY = 'gpd_access';

/**
 * Appends the JWT Bearer token to outgoing API requests. The token-obtain and
 * token-refresh endpoints are skipped (they authenticate by credentials).
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = localStorage.getItem(ACCESS_KEY);
  const isAuthEndpoint = req.url.includes('/auth/token');

  if (token && !isAuthEndpoint) {
    req = req.clone({
      setHeaders: { Authorization: `Bearer ${token}` },
    });
  }

  return next(req);
};
