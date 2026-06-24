import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="flex min-h-[80vh] items-center justify-center px-4">
      <div
        class="w-full max-w-sm rounded-2xl bg-slate-900/80 p-8 shadow-2xl ring-1 ring-slate-800 backdrop-blur"
      >
        <div class="mb-6 text-center">
          <div class="mb-2 text-3xl">🛡️</div>
          <h1 class="text-xl font-bold tracking-tight text-slate-100">
            Threat Dashboard
          </h1>
          <p class="mt-1 text-sm text-slate-400">Secure analyst sign-in</p>
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
              placeholder="nurADMIN"
            />
          </div>

          <div>
            <label class="mb-1 block text-xs font-medium text-slate-400">
              Password
            </label>
            <input
              name="password"
              type="password"
              [(ngModel)]="password"
              autocomplete="current-password"
              required
              class="w-full rounded-lg bg-slate-950 px-3 py-2 text-sm text-slate-100 ring-1 ring-slate-700 outline-none focus:ring-2 focus:ring-sky-500"
              placeholder="••••••••"
            />
          </div>

          <p
            *ngIf="error"
            class="rounded-lg bg-red-950/60 px-3 py-2 text-xs text-red-300 ring-1 ring-red-900"
          >
            {{ error }}
          </p>

          <button
            type="submit"
            [disabled]="loading || !username || !password"
            class="w-full rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {{ loading ? 'Signing in…' : 'Sign in' }}
          </button>
        </form>
      </div>
    </div>
  `,
})
export class LoginComponent {
  username = '';
  password = '';
  error = '';
  loading = false;

  constructor(
    private auth: AuthService,
    private router: Router,
    private route: ActivatedRoute,
  ) {}

  submit(): void {
    if (!this.username || !this.password) {
      return;
    }
    this.loading = true;
    this.error = '';

    this.auth.login(this.username.trim(), this.password).subscribe({
      next: () => {
        const returnUrl =
          this.route.snapshot.queryParamMap.get('returnUrl') || '/dashboard';
        this.router.navigateByUrl(returnUrl);
      },
      error: (err) => {
        this.loading = false;
        this.error =
          err?.status === 401
            ? 'Invalid username or password.'
            : 'Sign-in failed. Is the backend running?';
      },
    });
  }
}
