import { Injectable } from '@angular/core';
import {
  BehaviorSubject,
  Observable,
  combineLatest,
  of,
  timer,
} from 'rxjs';
import {
  catchError,
  distinctUntilChanged,
  shareReplay,
  switchMap,
} from 'rxjs/operators';
import { environment } from '../../environments/environment';
import {
  Alert,
  AlertFilters,
  DashboardSummary,
} from '../models/alert.model';
import { ThreatApiService } from './threat-api.service';

/**
 * Efficient HTTP polling without WebSockets.
 *
 * A single RxJS `timer(0, interval)` drives periodic fetches. Filters are held
 * in a BehaviorSubject so changing a filter restarts polling immediately via
 * `switchMap` (cancelling any in-flight request).
 */
@Injectable({ providedIn: 'root' })
export class PollingService {
  private readonly intervalMs = environment.pollIntervalMs;
  private readonly filters$ = new BehaviorSubject<AlertFilters>({});

  readonly alerts$: Observable<Alert[]>;
  readonly summary$: Observable<DashboardSummary>;

  constructor(private api: ThreatApiService) {
    const tick$ = timer(0, this.intervalMs);

    this.alerts$ = combineLatest([
      tick$,
      this.filters$.pipe(distinctUntilChanged(this.sameFilters)),
    ]).pipe(
      switchMap(([, filters]) =>
        this.api.getAlerts(filters).pipe(
          switchMap((page) => of(page.results)),
          catchError((err) => {
            console.error('Alert poll failed', err);
            return of<Alert[]>([]);
          }),
        ),
      ),
      shareReplay({ bufferSize: 1, refCount: true }),
    );

    this.summary$ = tick$.pipe(
      switchMap(() =>
        this.api.getSummary().pipe(
          catchError((err) => {
            console.error('Summary poll failed', err);
            return of<DashboardSummary>({
              window_hours: 24,
              total_alerts: 0,
              threat_alerts: 0,
              pending_analysis: 0,
              critical_alerts: 0,
              by_region: [],
            });
          }),
        ),
      ),
      shareReplay({ bufferSize: 1, refCount: true }),
    );
  }

  setFilters(filters: AlertFilters): void {
    this.filters$.next(filters);
  }

  get currentFilters(): AlertFilters {
    return this.filters$.value;
  }

  private sameFilters(a: AlertFilters, b: AlertFilters): boolean {
    return JSON.stringify(a) === JSON.stringify(b);
  }
}
