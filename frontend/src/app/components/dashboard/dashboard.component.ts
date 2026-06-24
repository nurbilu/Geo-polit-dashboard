import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';
import { DashboardGridComponent } from '../dashboard-grid/dashboard-grid.component';
import { ThreatFeedComponent } from '../threat-feed/threat-feed.component';
import {
  Alert,
  AlertFilters,
  DashboardSummary,
  Region,
} from '../../models/alert.model';
import { PollingService } from '../../services/polling.service';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    DashboardGridComponent,
    ThreatFeedComponent,
  ],
  template: `
    <app-dashboard-grid [summary]="summary$ | async"></app-dashboard-grid>

    <!-- Prominent region quick-tabs -->
    <section class="mt-6">
      <p class="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
        Region focus
      </p>
      <div class="flex flex-wrap gap-2">
        <button
          *ngFor="let r of regionFilters"
          (click)="toggleRegion(r.value)"
          class="rounded-full px-4 py-2 text-sm font-medium ring-1 transition"
          [ngClass]="regionButtonClass(r.value, r.featured)"
        >
          <span *ngIf="r.featured" class="mr-1">📍</span>{{ r.label }}
        </button>
      </div>
    </section>

    <!-- Severity + toggles -->
    <section
      class="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3 rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800"
    >
      <div class="flex items-center gap-3">
        <label class="text-sm font-medium text-slate-300">
          Min severity score
        </label>
        <input
          type="range"
          min="0"
          max="10"
          step="1"
          [(ngModel)]="minSeverity"
          (ngModelChange)="apply()"
          class="h-2 w-40 cursor-pointer accent-sky-500"
        />
        <span
          class="inline-flex h-7 w-9 items-center justify-center rounded-md text-sm font-bold text-white"
          [ngClass]="severityBadgeClass(minSeverity)"
        >
          {{ minSeverity === 0 ? 'Any' : minSeverity }}
        </span>
      </div>

      <label class="flex items-center gap-2 text-sm text-slate-300">
        <input
          type="checkbox"
          [(ngModel)]="threatsOnly"
          (ngModelChange)="apply()"
          class="h-4 w-4 rounded accent-red-500"
        />
        Threats only
      </label>

      <label class="flex items-center gap-2 text-sm text-slate-300">
        <input
          type="checkbox"
          [(ngModel)]="withImage"
          (ngModelChange)="apply()"
          class="h-4 w-4 rounded accent-sky-500"
        />
        With image
      </label>

      <button
        (click)="reset()"
        class="ml-auto rounded-md px-3 py-1.5 text-xs text-slate-400 ring-1 ring-slate-700 transition hover:bg-slate-800 hover:text-slate-200"
      >
        Reset filters
      </button>
    </section>

    <p class="mt-3 text-xs text-slate-500">
      Live polling every {{ pollSeconds }}s · auto-refreshing without WebSockets.
    </p>

    <div class="mt-4">
      <app-threat-feed [alerts]="alerts$ | async"></app-threat-feed>
    </div>
  `,
})
export class DashboardComponent {
  readonly pollSeconds = environment.pollIntervalMs / 1000;
  readonly alerts$: Observable<Alert[]>;
  readonly summary$: Observable<DashboardSummary>;

  activeRegion: Region | '' = '';
  minSeverity = 0;
  threatsOnly = false;
  withImage = false;

  readonly regionFilters: { label: string; value: Region; featured: boolean }[] =
    [
      { label: 'Judea & Samaria', value: 'judea_samaria', featured: true },
      { label: 'Golan Heights', value: 'golan_heights', featured: true },
      { label: 'North', value: 'north', featured: false },
      { label: 'South', value: 'south', featured: false },
      { label: 'Central', value: 'central', featured: false },
    ];

  constructor(private polling: PollingService) {
    this.alerts$ = this.polling.alerts$;
    this.summary$ = this.polling.summary$;
  }

  toggleRegion(value: Region): void {
    this.activeRegion = this.activeRegion === value ? '' : value;
    this.apply();
  }

  regionButtonClass(value: Region, featured: boolean): string {
    if (this.activeRegion === value) {
      return featured
        ? 'bg-amber-500 text-slate-950 ring-amber-400'
        : 'bg-sky-600 text-white ring-sky-500';
    }
    return featured
      ? 'bg-slate-900 text-amber-300 ring-amber-700/60 hover:bg-slate-800'
      : 'bg-slate-900 text-slate-300 ring-slate-700 hover:bg-slate-800';
  }

  severityBadgeClass(sev: number): string {
    if (sev >= 8) return 'bg-threat-critical';
    if (sev >= 5) return 'bg-threat-high';
    if (sev >= 3) return 'bg-threat-med';
    if (sev >= 1) return 'bg-threat-low';
    return 'bg-slate-700';
  }

  apply(): void {
    const filters: AlertFilters = {
      region: this.activeRegion,
      is_threat: this.threatsOnly ? true : '',
      min_severity: this.minSeverity > 0 ? this.minSeverity : '',
      has_image: this.withImage,
    };
    this.polling.setFilters(filters);
  }

  reset(): void {
    this.activeRegion = '';
    this.minSeverity = 0;
    this.threatsOnly = false;
    this.withImage = false;
    this.polling.setFilters({});
  }
}
