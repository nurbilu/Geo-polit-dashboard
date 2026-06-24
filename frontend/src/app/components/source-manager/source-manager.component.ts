import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Source, SourceInput, SourceType } from '../../models/source.model';
import { SourceService } from '../../services/source.service';

@Component({
  selector: 'app-source-manager',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="mb-6">
      <h2 class="text-xl font-bold tracking-tight text-slate-100">
        OSINT Source Manager
      </h2>
      <p class="text-sm text-slate-400">
        Paste public links to monitor. Telegram channels are scraped anonymously
        via their public web preview — no API keys required.
      </p>
    </div>

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-5">
      <!-- Add form -->
      <form
        (ngSubmit)="add()"
        class="lg:col-span-2 space-y-4 self-start rounded-xl bg-slate-900 p-5 ring-1 ring-slate-800"
      >
        <h3 class="text-sm font-semibold text-slate-200">Add a source</h3>

        <div>
          <label class="mb-1 block text-xs font-medium text-slate-400">Name</label>
          <input
            name="name"
            [(ngModel)]="draft.name"
            required
            placeholder="e.g. IDF Spokesperson"
            class="w-full rounded-lg bg-slate-950 px-3 py-2 text-sm text-slate-100 ring-1 ring-slate-700 outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-slate-400">Type</label>
          <select
            name="source_type"
            [(ngModel)]="draft.source_type"
            class="w-full rounded-lg bg-slate-950 px-3 py-2 text-sm text-slate-100 ring-1 ring-slate-700 outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option *ngFor="let t of types" [value]="t.value">{{ t.label }}</option>
          </select>
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-slate-400">
            Link / identifier
          </label>
          <input
            name="identifier"
            [(ngModel)]="draft.identifier"
            required
            [placeholder]="placeholderFor(draft.source_type)"
            class="w-full rounded-lg bg-slate-950 px-3 py-2 text-sm text-slate-100 ring-1 ring-slate-700 outline-none focus:ring-2 focus:ring-sky-500"
          />
          <p class="mt-1 text-[11px] text-slate-500">{{ hintFor(draft.source_type) }}</p>
        </div>

        <label class="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            name="is_active"
            [(ngModel)]="draft.is_active"
            class="h-4 w-4 rounded accent-emerald-500"
          />
          Active (poll on schedule)
        </label>

        <p
          *ngIf="error"
          class="rounded-lg bg-red-950/60 px-3 py-2 text-xs text-red-300 ring-1 ring-red-900"
        >
          {{ error }}
        </p>

        <button
          type="submit"
          [disabled]="saving || !draft.name || !draft.identifier"
          class="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {{ saving ? 'Saving…' : 'Add source' }}
        </button>
      </form>

      <!-- List -->
      <div class="lg:col-span-3 rounded-xl bg-slate-900 ring-1 ring-slate-800">
        <div class="flex items-center justify-between border-b border-slate-800 px-5 py-3">
          <h3 class="text-sm font-semibold text-slate-200">
            Monitored sources ({{ sources.length }})
          </h3>
          <button
            (click)="load()"
            class="text-xs text-slate-400 hover:text-slate-200"
          >
            ↻ Refresh
          </button>
        </div>

        <div *ngIf="loading" class="p-6 text-center text-sm text-slate-500">
          Loading…
        </div>

        <div
          *ngIf="!loading && !sources.length"
          class="p-6 text-center text-sm text-slate-500"
        >
          No sources yet. Add one on the left to start monitoring.
        </div>

        <ul *ngIf="!loading && sources.length" class="divide-y divide-slate-800">
          <li
            *ngFor="let s of sources"
            class="flex items-center gap-3 px-5 py-3"
          >
            <span
              class="rounded px-2 py-0.5 text-[11px] font-semibold uppercase"
              [ngClass]="typeBadge(s.source_type)"
            >
              {{ s.source_type }}
            </span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-slate-100">{{ s.name }}</p>
              <p class="truncate text-xs text-slate-500">{{ s.identifier }}</p>
            </div>

            <button
              (click)="toggleActive(s)"
              class="rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 transition"
              [ngClass]="
                s.is_active
                  ? 'bg-emerald-950 text-emerald-300 ring-emerald-800'
                  : 'bg-slate-800 text-slate-400 ring-slate-700'
              "
            >
              {{ s.is_active ? 'Active' : 'Paused' }}
            </button>

            <button
              (click)="remove(s)"
              title="Delete source"
              class="rounded-md px-2 py-1 text-xs text-red-400 transition hover:bg-red-950 hover:text-red-300"
            >
              ✕
            </button>
          </li>
        </ul>
      </div>
    </div>
  `,
})
export class SourceManagerComponent implements OnInit {
  sources: Source[] = [];
  loading = false;
  saving = false;
  error = '';

  draft: SourceInput = this.emptyDraft();

  readonly types: { value: SourceType; label: string }[] = [
    { value: 'telegram', label: 'Telegram Channel' },
    { value: 'x', label: 'X (Twitter) Handle' },
    { value: 'rss', label: 'RSS Feed' },
    { value: 'gov', label: 'Government Site' },
  ];

  constructor(private sourceApi: SourceService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading = true;
    this.sourceApi.list().subscribe({
      next: (rows) => {
        this.sources = rows;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.error = 'Could not load sources.';
      },
    });
  }

  add(): void {
    if (!this.draft.name || !this.draft.identifier) {
      return;
    }
    this.saving = true;
    this.error = '';
    this.sourceApi.create(this.draft).subscribe({
      next: (created) => {
        this.sources = [...this.sources, created].sort((a, b) =>
          a.name.localeCompare(b.name),
        );
        this.draft = this.emptyDraft();
        this.saving = false;
      },
      error: (err) => {
        this.saving = false;
        this.error =
          err?.status === 401
            ? 'Session expired — please sign in again.'
            : 'Failed to add source. Check the link and try again.';
      },
    });
  }

  toggleActive(source: Source): void {
    const next = !source.is_active;
    this.sourceApi.update(source.id, { is_active: next }).subscribe({
      next: (updated) => (source.is_active = updated.is_active),
      error: () => (this.error = 'Could not update source.'),
    });
  }

  remove(source: Source): void {
    this.sourceApi.remove(source.id).subscribe({
      next: () => (this.sources = this.sources.filter((s) => s.id !== source.id)),
      error: () => (this.error = 'Could not delete source.'),
    });
  }

  typeBadge(type: SourceType): string {
    const map: Record<SourceType, string> = {
      telegram: 'bg-sky-950 text-sky-300',
      x: 'bg-slate-800 text-slate-200',
      rss: 'bg-amber-950 text-amber-300',
      gov: 'bg-emerald-950 text-emerald-300',
    };
    return map[type];
  }

  placeholderFor(type: SourceType): string {
    switch (type) {
      case 'telegram':
        return 'https://t.me/channel_name  or  @channel_name';
      case 'x':
        return '@handle';
      case 'rss':
        return 'https://example.com/feed.xml';
      case 'gov':
        return 'https://gov.example.com/news';
    }
  }

  hintFor(type: SourceType): string {
    switch (type) {
      case 'telegram':
        return 'Public channel — scraped anonymously from t.me/s/<channel>.';
      case 'x':
        return 'Handle for the X (Twitter) connector.';
      case 'rss':
        return 'Direct RSS/Atom feed URL.';
      case 'gov':
        return 'Government site or its news/RSS endpoint.';
    }
  }

  private emptyDraft(): SourceInput {
    return { name: '', source_type: 'telegram', identifier: '', is_active: true };
  }
}
