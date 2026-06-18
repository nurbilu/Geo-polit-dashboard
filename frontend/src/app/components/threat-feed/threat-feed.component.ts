import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { Alert } from '../../models/alert.model';

/**
 * Multimodal live feed. Renders each alert as a card; when an alert carries an
 * image it is shown elegantly alongside the model's visual summary.
 */
@Component({
  selector: 'app-threat-feed',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div
      *ngIf="alerts?.length; else empty"
      class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
    >
      <article
        *ngFor="let a of alerts; trackBy: trackById"
        class="flex flex-col overflow-hidden rounded-xl bg-slate-900 ring-1 ring-slate-800 transition hover:ring-slate-600"
        [class.ring-red-700]="a.is_threat"
      >
        <div *ngIf="a.image" class="relative">
          <img
            [src]="a.image"
            [alt]="a.visual_summary || a.title"
            loading="lazy"
            class="h-44 w-full object-cover"
          />
          <span
            *ngIf="a.threat_severity"
            class="absolute right-2 top-2 rounded-md px-2 py-1 text-xs font-bold text-white"
            [ngClass]="severityClass(a.threat_severity)"
          >
            SEV {{ a.threat_severity }}
          </span>
        </div>

        <div class="flex flex-1 flex-col gap-2 p-4">
          <div class="flex items-center justify-between gap-2">
            <span
              class="rounded px-2 py-0.5 text-xs font-semibold"
              [ngClass]="a.is_threat ? 'bg-red-900 text-red-200' : 'bg-slate-800 text-slate-300'"
            >
              {{ a.is_threat ? 'THREAT' : 'INFO' }}
            </span>
            <span class="rounded bg-slate-800 px-2 py-0.5 text-xs text-sky-300">
              {{ a.region_display }}
            </span>
          </div>

          <h3 class="text-sm font-semibold leading-snug text-slate-100">
            {{ a.title || (a.content | slice: 0:90) }}
          </h3>

          <p class="line-clamp-3 text-xs text-slate-400">{{ a.content }}</p>

          <p
            *ngIf="a.visual_summary"
            class="rounded-md bg-slate-800/70 p-2 text-xs italic text-amber-200"
          >
            👁 {{ a.visual_summary }}
          </p>

          <div class="mt-auto flex items-center justify-between pt-2 text-[11px] text-slate-500">
            <span>{{ a.source_name }} · {{ a.source_type }}</span>
            <span>{{ a.published_at | date: 'short' }}</span>
          </div>

          <a
            *ngIf="a.url"
            [href]="a.url"
            target="_blank"
            rel="noopener"
            class="text-xs text-sky-400 hover:underline"
          >
            Open source ↗
          </a>
        </div>
      </article>
    </div>

    <ng-template #empty>
      <div class="rounded-xl bg-slate-900 p-10 text-center text-slate-500 ring-1 ring-slate-800">
        No alerts match the current filters yet.
      </div>
    </ng-template>
  `,
})
export class ThreatFeedComponent {
  @Input() alerts: Alert[] | null = [];

  trackById(_: number, alert: Alert): number {
    return alert.id;
  }

  severityClass(sev: number): string {
    if (sev >= 8) return 'bg-threat-critical';
    if (sev >= 5) return 'bg-threat-high';
    if (sev >= 3) return 'bg-threat-med';
    return 'bg-threat-low';
  }
}
