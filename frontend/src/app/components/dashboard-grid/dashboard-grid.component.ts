import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { DashboardSummary } from '../../models/alert.model';

@Component({
  selector: 'app-dashboard-grid',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
      <div class="rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
        <p class="text-xs uppercase tracking-wide text-slate-400">Alerts ({{ summary?.window_hours || 24 }}h)</p>
        <p class="mt-1 text-3xl font-bold">{{ summary?.total_alerts ?? 0 }}</p>
      </div>
      <div class="rounded-xl bg-slate-900 p-4 ring-1 ring-red-900/60">
        <p class="text-xs uppercase tracking-wide text-slate-400">Threats</p>
        <p class="mt-1 text-3xl font-bold text-red-400">{{ summary?.threat_alerts ?? 0 }}</p>
      </div>
      <div class="rounded-xl bg-slate-900 p-4 ring-1 ring-amber-900/60">
        <p class="text-xs uppercase tracking-wide text-slate-400">Critical (≥8)</p>
        <p class="mt-1 text-3xl font-bold text-amber-400">{{ summary?.critical_alerts ?? 0 }}</p>
      </div>
      <div class="rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
        <p class="text-xs uppercase tracking-wide text-slate-400">Pending AI</p>
        <p class="mt-1 text-3xl font-bold text-sky-400">{{ summary?.pending_analysis ?? 0 }}</p>
      </div>
    </div>

    <div class="mt-3 flex flex-wrap gap-2" *ngIf="summary?.by_region?.length">
      <span
        *ngFor="let bucket of summary?.by_region"
        class="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-200"
      >
        {{ regionLabel(bucket.region) }}:
        <strong class="text-red-300">{{ bucket.count }}</strong>
        <span class="text-slate-400" *ngIf="bucket.avg_severity">
          (avg {{ bucket.avg_severity | number: '1.0-1' }})
        </span>
      </span>
    </div>
  `,
})
export class DashboardGridComponent {
  @Input() summary: DashboardSummary | null = null;

  private readonly labels: Record<string, string> = {
    judea_samaria: 'Judea & Samaria',
    golan_heights: 'Golan Heights',
    north: 'North',
    south: 'South',
    central: 'Central',
    unknown: 'Unknown',
  };

  regionLabel(region: string): string {
    return this.labels[region] ?? region;
  }
}
