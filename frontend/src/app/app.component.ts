import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import {
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from '@angular/router';
import { AuthService } from './services/auth.service';

interface NavItem {
  label: string;
  route: string;
  icon: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="min-h-screen bg-slate-950 text-slate-100">
      <!-- Top header -->
      <header
        class="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/80 backdrop-blur"
      >
        <div class="flex items-center gap-3 px-4 py-3">
          <button
            *ngIf="isAuthed"
            (click)="toggleSidebar()"
            aria-label="Toggle navigation"
            class="inline-flex h-9 w-9 items-center justify-center rounded-lg text-slate-300 ring-1 ring-slate-700 transition hover:bg-slate-800"
          >
            <!-- Hamburger / close icon -->
            <svg
              *ngIf="!sidebarOpen"
              xmlns="http://www.w3.org/2000/svg"
              class="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              stroke-width="2"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
            <svg
              *ngIf="sidebarOpen"
              xmlns="http://www.w3.org/2000/svg"
              class="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              stroke-width="2"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <a routerLink="/dashboard" class="flex items-center gap-2">
            <span class="text-xl">🛡️</span>
            <span class="hidden text-base font-bold tracking-tight sm:inline">
              Israel Geopolitical &amp; Security Threat Dashboard
            </span>
            <span class="text-base font-bold tracking-tight sm:hidden">
              Threat Dashboard
            </span>
          </a>

          <div class="ml-auto flex items-center gap-3">
            <span
              class="hidden items-center gap-2 text-xs text-emerald-400 sm:flex"
            >
              <span class="h-2 w-2 animate-pulse rounded-full bg-emerald-400"></span>
              LIVE
            </span>

            <ng-container *ngIf="isAuthed; else signedOut">
              <span class="hidden text-xs text-slate-400 sm:inline">
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

      <!-- Backdrop -->
      <div
        *ngIf="isAuthed && sidebarOpen"
        (click)="closeSidebar()"
        class="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm transition-opacity"
      ></div>

      <!-- Sidebar drawer -->
      <aside
        *ngIf="isAuthed"
        class="fixed inset-y-0 left-0 z-40 flex w-64 transform flex-col border-r border-slate-800 bg-slate-900 shadow-2xl transition-transform duration-300 ease-in-out"
        [ngClass]="sidebarOpen ? 'translate-x-0' : '-translate-x-full'"
      >
        <div
          class="flex items-center justify-between border-b border-slate-800 px-4 py-4"
        >
          <span class="text-sm font-semibold text-slate-200">Navigation</span>
          <button
            (click)="closeSidebar()"
            aria-label="Close navigation"
            class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-800 hover:text-slate-200"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              stroke-width="2"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <nav class="flex-1 space-y-1 overflow-y-auto p-3">
          <a
            *ngFor="let item of navItems"
            [routerLink]="item.route"
            routerLinkActive="bg-slate-800 text-white ring-1 ring-slate-700"
            (click)="closeSidebar()"
            class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-300 transition hover:bg-slate-800 hover:text-white"
          >
            <span class="text-lg">{{ item.icon }}</span>
            {{ item.label }}
          </a>
        </nav>

        <div class="border-t border-slate-800 p-4">
          <p class="text-xs text-slate-500">Signed in as</p>
          <p class="truncate text-sm font-medium text-slate-200">
            {{ auth.username }}
          </p>
          <button
            (click)="logout()"
            class="mt-3 w-full rounded-md px-3 py-2 text-xs font-medium text-slate-300 ring-1 ring-slate-700 transition hover:bg-slate-800"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main class="mx-auto max-w-7xl px-4 py-6">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
})
export class AppComponent {
  sidebarOpen = false;

  readonly navItems: NavItem[] = [
    { label: 'Dashboard', route: '/dashboard', icon: '📊' },
    { label: 'Sources', route: '/admin/sources', icon: '🛰️' },
  ];

  constructor(
    public auth: AuthService,
    private router: Router,
  ) {}

  get isAuthed(): boolean {
    return this.auth.hasToken();
  }

  toggleSidebar(): void {
    this.sidebarOpen = !this.sidebarOpen;
  }

  closeSidebar(): void {
    this.sidebarOpen = false;
  }

  logout(): void {
    this.closeSidebar();
    this.auth.logout();
    this.router.navigateByUrl('/login');
  }
}
