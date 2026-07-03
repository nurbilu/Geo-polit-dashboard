import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="flex min-h-[80vh] items-center justify-center px-4">
      <div
        class="w-full max-w-sm rounded-2xl bg-slate-900/80 p-8 shadow-2xl ring-1 ring-slate-800 backdrop-blur"
      >
        <div class="mb-6 text-center">
          <div class="mb-2 text-3xl">🛡️</div>
          <h1 class="text-xl font-bold tracking-tight text-slate-100">
            Create account
          </h1>
          <p class="mt-1 text-sm text-slate-400">Register a dashboard analyst</p>
        </div>

        <form (ngSubmit)="submit()" class="space-y-4">
          <div>
            <label class="mb-1 block text-xs font-medium text-slate-400">
              Username
            </label>
            <input
              name="username"
              [(ngModel)]="username"
              autocomplete="username"
              required
              class="w-full rounded-lg bg-slate-950 px-3 py-2 text-sm text-slate-100 ring-1 ring-slate-700 outline-none focus:ring-2 focus:ring-sky-500"
              placeholder="analyst01"
            />
          </div>

          <div>
            <label class="mb-1 block text-xs font-medium text-slate-400">
              Email
            </label>
            <input
              name="email"
              type="email"
              [(ngModel)]="email"
              autocomplete="email"
              class="w-full rounded-lg bg-slate-950 px-3 py-2 text-sm text-slate-100 ring-1 ring-slate-700 outline-none focus:ring-2 focus:ring-sky-500"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label class="mb-1 block text-xs font-medium text-slate-400">
              Password
            </label>
            <div class="relative">
              <input
                name="password"
                [type]="showPassword ? 'text' : 'password'"
                [(ngModel)]="password"
                autocomplete="new-password"
                required
                minlength="8"
                class="w-full rounded-lg bg-slate-950 px-3 py-2 pr-10 text-sm text-slate-100 ring-1 ring-slate-700 outline-none focus:ring-2 focus:ring-sky-500"
                placeholder="At least 8 characters"
              />
              <button
                type="button"
                (click)="showPassword = !showPassword"
                [attr.aria-label]="showPassword ? 'Hide password' : 'Show password'"
                class="absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 transition hover:text-slate-200"
              >
                {{ showPassword ? '🙈' : '👁️' }}
              </button>
            </div>
          </div>

          <label
            class="flex cursor-pointer items-center gap-2 rounded-lg bg-slate-950/60 px-3 py-2 text-sm text-slate-300 ring-1 ring-slate-800"
          >
            <input
              type="checkbox"
              name="isAdmin"
              [(ngModel)]="isAdmin"
              class="h-4 w-4 rounded accent-amber-500"
            />
            Register as Admin
          </label>

          <div *ngIf="isAdmin" class="animate-[fadeIn_0.2s_ease-in]">
            <label class="mb-1 block text-xs font-medium text-amber-400">
              Admin Verification Code
            </label>
            <input
              name="adminCode"
              type="password"
              [(ngModel)]="adminCode"
              autocomplete="off"
              class="w-full rounded-lg bg-slate-950 px-3 py-2 text-sm text-slate-100 ring-1 ring-amber-700/60 outline-none focus:ring-2 focus:ring-amber-500"
              placeholder="Shared admin secret"
            />
            <p class="mt-1 text-[11px] text-slate-500">
              Required to provision a superuser account.
            </p>
          </div>

          <p
            *ngIf="error"
            class="rounded-lg bg-red-950/60 px-3 py-2 text-xs text-red-300 ring-1 ring-red-900"
          >
            {{ error }}
          </p>

          <button
            type="submit"
            [disabled]="loading || !username || !password || (isAdmin && !adminCode)"
            class="w-full rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {{ loading ? 'Creating account…' : 'Create account' }}
          </button>

          <p class="text-center text-xs text-slate-400">
            Already have an account?
            <a routerLink="/login" class="text-sky-400 hover:underline">Sign in</a>
          </p>
        </form>
      </div>
    </div>
  `,
})
export class RegisterComponent {
  username = '';
  email = '';
  password = '';
  showPassword = false;
  isAdmin = false;
  adminCode = '';
  error = '';
  loading = false;

  constructor(
    private auth: AuthService,
    private router: Router,
  ) {}

  submit(): void {
    if (!this.username || !this.password) {
      return;
    }
    if (this.isAdmin && !this.adminCode) {
      this.error = 'Admin verification code is required.';
      return;
    }

    this.loading = true;
    this.error = '';

    this.auth
      .register({
        username: this.username.trim(),
        email: this.email.trim(),
        password: this.password,
        is_admin: this.isAdmin,
        admin_verification_password: this.isAdmin ? this.adminCode : '',
      })
      .subscribe({
        next: () => {
          // Auto-login the freshly created account, then go to the dashboard.
          this.auth.login(this.username.trim(), this.password).subscribe({
            next: () => this.router.navigateByUrl('/dashboard'),
            error: () => this.router.navigateByUrl('/login'),
          });
        },
        error: (err) => {
          this.loading = false;
          this.error = this.describeError(err);
        },
      });
  }

  private describeError(err: unknown): string {
    const e = err as { status?: number; error?: Record<string, unknown> };
    if (e?.status === 403) {
      return 'Invalid admin verification code.';
    }
    if (e?.status === 400 && e.error) {
      const first = Object.values(e.error)[0];
      const msg = Array.isArray(first) ? first[0] : first;
      return String(msg ?? 'Registration failed. Check your input.');
    }
    return 'Registration failed. Is the backend running?';
  }
}
