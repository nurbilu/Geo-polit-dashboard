import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import {
  ChartData,
  ChartDataset,
  ChartOptions,
} from 'chart.js';
import { BaseChartDirective } from 'ng2-charts';
import { Alert, Country } from '../../models/alert.model';

@Component({
  selector: 'app-analytics-dashboard',
  standalone: true,
  imports: [CommonModule, BaseChartDirective],
  template: `
    <section class="mt-6 rounded-xl bg-slate-900/70 p-4 ring-1 ring-slate-800">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 class="text-sm font-semibold uppercase tracking-widest text-slate-200">
            Analytics & Insights
          </h3>
          <p class="text-xs text-slate-400">
            Live intelligence metrics from primary threats (auto-refresh on polling cycle)
          </p>
        </div>
        <span class="rounded-md bg-slate-800 px-2 py-1 text-xs text-slate-300 ring-1 ring-slate-700">
          Active threats: {{ activeThreatCount }}
        </span>
      </div>

      <div *ngIf="activeThreatCount > 0; else empty" class="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <article class="rounded-xl bg-slate-950/80 p-4 ring-1 ring-slate-800">
          <h4 class="mb-3 text-sm font-medium text-slate-200">Distribution by Country</h4>
          <div class="h-72">
            <canvas
              baseChart
              [type]="'doughnut'"
              [data]="doughnutChartData"
              [options]="doughnutChartOptions"
            ></canvas>
          </div>
        </article>

        <article class="rounded-xl bg-slate-950/80 p-4 ring-1 ring-slate-800">
          <h4 class="mb-3 text-sm font-medium text-slate-200">Severity Distribution</h4>
          <div class="h-72">
            <canvas
              baseChart
              [type]="'bar'"
              [data]="barChartData"
              [options]="barChartOptions"
            ></canvas>
          </div>
        </article>
      </div>

      <ng-template #empty>
        <div class="rounded-xl bg-slate-950/80 p-10 text-center text-slate-500 ring-1 ring-slate-800">
          No active primary threats yet — charts will populate automatically.
        </div>
      </ng-template>
    </section>
  `,
})
export class AnalyticsDashboardComponent implements OnChanges {
  @Input() alerts: Alert[] | null = [];

  activeThreatCount = 0;

  doughnutChartData: ChartData<'doughnut'> = {
    labels: [],
    datasets: [
      {
        data: [],
        borderWidth: 1.5,
        borderColor: '#020617',
      },
    ],
  };

  readonly doughnutChartOptions: ChartOptions<'doughnut'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          color: '#cbd5e1',
          boxWidth: 14,
          usePointStyle: true,
        },
      },
      tooltip: {
        titleColor: '#e2e8f0',
        bodyColor: '#e2e8f0',
        backgroundColor: '#0f172a',
        borderColor: '#334155',
        borderWidth: 1,
      },
    },
  };

  barChartData: ChartData<'bar'> = {
    labels: ['Low (1-3)', 'Medium (4-7)', 'High/Critical (8-10)'],
    datasets: [
      {
        label: 'Threat count',
        data: [0, 0, 0],
      },
    ],
  };

  readonly barChartOptions: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        ticks: { color: '#94a3b8' },
        grid: { color: 'rgba(51, 65, 85, 0.2)' },
      },
      y: {
        beginAtZero: true,
        ticks: {
          color: '#94a3b8',
          precision: 0,
        },
        grid: { color: 'rgba(51, 65, 85, 0.25)' },
      },
    },
    plugins: {
      legend: {
        labels: {
          color: '#cbd5e1',
        },
      },
      tooltip: {
        titleColor: '#e2e8f0',
        bodyColor: '#e2e8f0',
        backgroundColor: '#0f172a',
        borderColor: '#334155',
        borderWidth: 1,
      },
    },
  };

  ngOnChanges(_changes: SimpleChanges): void {
    this.rebuildCharts(this.alerts ?? []);
  }

  private rebuildCharts(alerts: Alert[]): void {
    const primaryThreats = alerts.filter(
      (a) => a.is_threat === true && a.parent_alert == null,
    );
    this.activeThreatCount = primaryThreats.length;

    this.rebuildCountryChart(primaryThreats);
    this.rebuildSeverityChart(primaryThreats);
  }

  private rebuildCountryChart(alerts: Alert[]): void {
    const counts = new Map<string, number>();
    for (const alert of alerts) {
      const countryLabel = alert.country_display || this.countryLabel(alert.country);
      counts.set(countryLabel, (counts.get(countryLabel) ?? 0) + 1);
    }

    const ordered = [...counts.entries()].sort((a, b) => b[1] - a[1]);
    const labels = ordered.map(([label]) => label);
    const data = ordered.map(([, value]) => value);

    const palette = [
      '#ef4444', // neon red
      '#f97316', // cyber orange
      '#eab308', // signal yellow
      '#38bdf8', // cyan
      '#818cf8', // indigo
      '#14b8a6', // teal
      '#f43f5e', // rose
      '#fb7185', // pink
      '#a78bfa', // violet
      '#22c55e', // green
      '#64748b', // sleek gray
    ];

    this.doughnutChartData = {
      labels,
      datasets: [
        {
          data,
          backgroundColor: data.map((_, i) => palette[i % palette.length]),
          borderWidth: 1.5,
          borderColor: '#020617',
        },
      ],
    };
  }

  private rebuildSeverityChart(alerts: Alert[]): void {
    let low = 0;
    let medium = 0;
    let high = 0;

    for (const alert of alerts) {
      const sev = alert.threat_severity ?? 0;
      if (sev >= 8) high += 1;
      else if (sev >= 4) medium += 1;
      else if (sev >= 1) low += 1;
    }

    const dataset: ChartDataset<'bar'> = {
      label: 'Threat count',
      data: [low, medium, high],
      backgroundColor: ['#eab308', '#f97316', '#ef4444'],
      borderColor: ['#ca8a04', '#ea580c', '#b91c1c'],
      borderWidth: 1.25,
      borderRadius: 6,
      maxBarThickness: 56,
    };

    this.barChartData = {
      labels: ['Low (1-3)', 'Medium (4-7)', 'High/Critical (8-10)'],
      datasets: [dataset],
    };
  }

  private countryLabel(country: Country): string {
    const labels: Record<Country, string> = {
      israel: 'Israel',
      lebanon: 'Lebanon',
      syria: 'Syria',
      jordan: 'Jordan',
      egypt: 'Egypt',
      iraq: 'Iraq',
      arabian_peninsula: 'Arabian Peninsula',
      gulf_states: 'Persian Gulf States',
      iran: 'Iran',
      turkey: 'Turkey',
      mediterranean: 'Mediterranean Region',
      unknown: 'Unknown',
    };
    return labels[country] ?? 'Unknown';
  }
}

