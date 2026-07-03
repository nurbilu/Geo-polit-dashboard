import { CommonModule } from '@angular/common';
import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import * as L from 'leaflet';
import { Alert, Region } from '../../models/alert.model';

const ISRAEL_BOUNDS: L.LatLngBoundsExpression = [
  [29.35, 34.15], // SW
  [33.45, 36.35], // NE
];

const REGION_ANCHORS: Record<Region, L.LatLngTuple> = {
  judea_samaria: [31.78, 35.2],
  golan_heights: [33.05, 35.77],
  north: [32.87, 35.45],
  south: [30.95, 34.85],
  central: [32.09, 34.82],
  unknown: [31.5, 35.0],
};

const REGION_ZONES: Array<{
  label: string;
  bounds: L.LatLngBoundsExpression;
}> = [
  {
    label: 'Judea & Samaria',
    bounds: [
      [31.35, 34.92],
      [32.05, 35.52],
    ],
  },
  {
    label: 'Golan Heights',
    bounds: [
      [32.77, 35.62],
      [33.28, 36.0],
    ],
  },
  {
    label: 'North',
    bounds: [
      [32.65, 34.9],
      [33.32, 35.9],
    ],
  },
  {
    label: 'South',
    bounds: [
      [29.55, 34.2],
      [31.35, 35.3],
    ],
  },
];

@Component({
  selector: 'app-threat-map',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="mt-4 rounded-xl bg-slate-900/70 p-4 ring-1 ring-slate-800">
      <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 class="text-sm font-semibold uppercase tracking-widest text-slate-200">
            Threat Map
          </h3>
          <p class="text-xs text-slate-400">
            Primary events across critical Israeli regions (updates every poll cycle)
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-2 text-xs text-slate-300">
          <span class="inline-flex items-center gap-1.5">
            <span class="h-2.5 w-2.5 rounded-full bg-threat-med"></span> 1-4
          </span>
          <span class="inline-flex items-center gap-1.5">
            <span class="h-2.5 w-2.5 rounded-full bg-threat-high"></span> 5-7
          </span>
          <span class="inline-flex items-center gap-1.5">
            <span class="leaflet-threat-dot h-2.5 w-2.5 rounded-full bg-threat-critical"></span>
            8-10
          </span>
        </div>
      </div>

      <div #mapHost class="h-[380px] w-full overflow-hidden rounded-xl ring-1 ring-slate-700"></div>
    </section>
  `,
})
export class ThreatMapComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() alerts: Alert[] | null = [];
  @ViewChild('mapHost', { static: true }) mapHost!: ElementRef<HTMLDivElement>;

  private map?: L.Map;
  private zoneLayer = L.layerGroup();
  private markerLayer = L.layerGroup();

  ngAfterViewInit(): void {
    this.map = L.map(this.mapHost.nativeElement, {
      zoomControl: true,
      attributionControl: true,
      minZoom: 7,
      maxZoom: 11,
    });
    this.map.fitBounds(ISRAEL_BOUNDS);
    this.map.setMaxBounds(ISRAEL_BOUNDS);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(this.map);

    this.zoneLayer.addTo(this.map);
    this.markerLayer.addTo(this.map);
    this.drawRegionZones();
    this.renderMarkers();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['alerts'] && this.map) {
      this.renderMarkers();
    }
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }

  private drawRegionZones(): void {
    this.zoneLayer.clearLayers();
    for (const zone of REGION_ZONES) {
      L.rectangle(zone.bounds, {
        color: '#334155',
        weight: 1,
        fillColor: '#0f172a',
        fillOpacity: 0.2,
        dashArray: '4 4',
      })
        .bindTooltip(zone.label, {
          permanent: true,
          direction: 'center',
          opacity: 0.75,
        })
        .addTo(this.zoneLayer);
    }
  }

  private renderMarkers(): void {
    this.markerLayer.clearLayers();
    const primaryAlerts = (this.alerts ?? []).filter((a) => a.parent_alert == null);

    for (const alert of primaryAlerts) {
      const center = REGION_ANCHORS[alert.region] ?? REGION_ANCHORS.unknown;
      const sev = alert.threat_severity ?? 1;
      const isCritical = sev >= 8;

      const marker = L.circleMarker(center, {
        radius: sev >= 8 ? 10 : sev >= 5 ? 8 : 6,
        color: this.borderBySeverity(sev),
        fillColor: this.fillBySeverity(sev),
        fillOpacity: 0.8,
        weight: 2,
        className: isCritical ? 'leaflet-threat-flash' : '',
      });

      marker.bindPopup(this.popupHtml(alert), {
        className: 'threat-popup',
        maxWidth: 300,
      });
      marker.addTo(this.markerLayer);
    }
  }

  private fillBySeverity(sev: number): string {
    if (sev >= 8) return '#991b1b';
    if (sev >= 5) return '#ea580c';
    return '#eab308';
  }

  private borderBySeverity(sev: number): string {
    if (sev >= 8) return '#f87171';
    if (sev >= 5) return '#fdba74';
    return '#fde047';
  }

  private popupHtml(alert: Alert): string {
    const summary = this.escapeHtml(
      (alert.summary_hebrew || alert.visual_summary || alert.title || 'No summary available.').trim(),
    );
    const detailsHref = alert.url || `/dashboard?alert=${alert.id}`;
    const external = !!alert.url;

    return `
      <div class="space-y-2 text-slate-100">
        <div class="text-xs font-semibold text-sky-300">${this.escapeHtml(alert.region_display)}</div>
        <div dir="rtl" lang="he" class="text-sm">${summary}</div>
        <a href="${detailsHref}" ${
          external ? 'target="_blank" rel="noopener"' : ''
        } class="text-xs text-sky-400 underline">View full details</a>
      </div>
    `;
  }

  private escapeHtml(value: string): string {
    return value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

