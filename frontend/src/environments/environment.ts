// Production build. Served by nginx, which proxies /api and /media to Django.
export const environment = {
  production: true,
  apiUrl: '/api',
  pollIntervalMs: 20000,
};
