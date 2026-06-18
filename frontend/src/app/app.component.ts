import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Component } from '@angular/core';
import { Observable } from 'rxjs';
import { DashboardGridComponent } from './components/dashboard-grid/dashboard-grid.component';
import { ThreatFeedComponent } from './components/threat-feed/threat-feed.component';
import {
  Alert,
  AlertFilters,
  DashboardSummary,
  Region,
} from './models/alert.model';
import { PollingService } from './services/polling.service';
import { environment } from '../environments/environment';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, DashboardGridComponent, ThreatFeedComponent],
  template: `
    <div class="mx-auto max-w-7xl px-4 py-6">
      <header class="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-bold tracking-tight">
            🛡️ Israel Geopolitical & Security Threat Dashboard
          </h1>
          <p class="text-sm text-slate-400">
            AI threat analysis via Llama 3.3 70B (OpenRouter) · live polling every
            {{ pollSeconds }}s
          </p>
        </div>
        <span class="flex items-center gap-2 text-xs text-emerald-400">
          <span class="h-2 w-2 animate-pulse rounded-full bg-emerald-400"></span>
          LIVE
        </span>
      </header>

      <app-dashboard-grid [summary]="summary$ | async"></app-dashboard-grid>

      <!-- Quick filters -->
      <section class="my-5 flex flex-wrap items-center gap-2">
        <button
          *ngFor="let r of regionFilters"
          (click)="toggleRegion(r.value)"
          class="rounded-full px-3 py-1.5 text-sm ring-1 transition"
          [ngClass]="
            filters.region === r.value
              ? 'bg-sky-600 text-white ring-sky-500'
              : 'bg-slate-900 text-slate-300 ring-slate-700 hover:bg-slate-800'
          "
        >
          {{ r.label }}
        </button>

        <label class="ml-2 flex items-center gap-2 text-sm text-slate-300">
          Min severity
          <select
            [(ngModel)]="filters.min_severity"
            (ngModelChange)="apply()"
            class="rounded-md bg-slate-900 px-2 py-1 text-sm ring-1 ring-slate-700"
          >
            <option [ngValue]="''">Any</option>
            <option *ngFor="let s of severities" [ngValue]="s">{{ s }}+</option>
          </select>
        </label>

        <label class="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            [(ngModel)]="threatsOnly"
            (ngModelChange)="apply()"
            class="h-4 w-4 rounded"
          />
          Threats only
        </label>

        <label class="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            [(ngModel)]="filters.has_image"
            (ngModelChange)="apply()"
            class="h-4 w-4 rounded"
          />
          With image
        </label>

        <button
          (click)="reset()"
          class="ml-auto text-xs text-slate-400 hover:text-slate-200"
        >
          Reset filters
        </button>
      </section>

      <app-threat-feed [alerts]="alerts$ | async"></app-threat-feed>
    </div>
  `,
})
export class AppComponent {
  readonly pollSeconds = environment.pollIntervalMs / 1000;
  readonly alerts$: Observable<Alert[]>;
  readonly summary$: Observable<DashboardSummary>;

  filters: AlertFilters = {};
  threatsOnly = false;

  readonly severities = [3, 5, 7, 8];
  readonly regionFilters: { label: string; value: Region }[] = [
    { label: 'Judea & Samaria', value: 'judea_samaria' },
    { label: 'Golan Heights', value: 'golan_heights' },
    { label: 'North', value: 'north' },
    { label: 'South', value: 'south' },
    { label: 'Central', value: 'central' },
  ];

  constructor(private polling: PollingService) {
    this.alerts$ = this.polling.alerts$;
    this.summary$ = this.polling.summary$;
  }

  toggleRegion(value: Region): void {
    this.filters.region = this.filters.region === value ? '' : value;
    this.apply();
  }

  apply(): void {
    this.polling.setFilters({
      ...this.filters,
      is_threat: this.threatsOnly ? true : '',
    });
  }

  reset(): void {
    this.filters = {};
    this.threatsOnly = false;
    this.polling.setFilters({});
  }
}
