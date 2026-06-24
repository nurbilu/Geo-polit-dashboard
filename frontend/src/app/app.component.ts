import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="min-h-screen bg-slate-950 text-slate-100">
      <header
        class="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/80 backdrop-blur"
      >
        <div
          class="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3"
        >
          <a routerLink="/dashboard" class="flex items-center gap-2">
            <span class="text-xl">🛡️</span>
            <span class="text-base font-bold tracking-tight">
              Israel Geopolitical &amp; Security Threat Dashboard
            </span>
          </a>

          <nav
            *ngIf="auth.isAuthenticated$ | async"
            class="ml-2 flex items-center gap-1 text-sm"
          >
            <a
              routerLink="/dashboard"
              routerLinkActive="bg-slate-800 text-white"
              class="rounded-md px-3 py-1.5 text-slate-300 transition hover:bg-slate-800"
            >
              Dashboard
            </a>
            <a
              routerLink="/admin/sources"
              routerLinkActive="bg-slate-800 text-white"
              class="rounded-md px-3 py-1.5 text-slate-300 transition hover:bg-slate-800"
            >
              Sources
            </a>
          </nav>

          <div class="ml-auto flex items-center gap-3">
            <span
              class="hidden items-center gap-2 text-xs text-emerald-400 sm:flex"
            >
              <span
                class="h-2 w-2 animate-pulse rounded-full bg-emerald-400"
              ></span>
              LIVE
            </span>

            <ng-container *ngIf="auth.isAuthenticated$ | async; else signedOut">
              <span class="text-xs text-slate-400">
                {{ auth.username }}
              </span>
              <button
                (click)="logout()"
                class="rounded-md px-3 py-1.5 text-xs font-medium text-slate-300 ring-1 ring-slate-700 transition hover:bg-slate-800"
              >
                Sign out
              </button>
            </ng-container>
            <ng-template #signedOut>
              <a
                routerLink="/login"
                class="rounded-md bg-sky-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-sky-500"
              >
                Sign in
              </a>
            </ng-template>
          </div>
        </div>
      </header>

      <main class="mx-auto max-w-7xl px-4 py-6">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
})
export class AppComponent {
  constructor(
    public auth: AuthService,
    private router: Router,
  ) {}

  logout(): void {
    this.auth.logout();
    this.router.navigateByUrl('/login');
  }
}
