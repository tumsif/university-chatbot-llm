import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { UiButton } from './ui/button';

@Component({
  selector: 'app-site-header',
  standalone: true,
  imports: [RouterLink, UiButton],
  template: `
    <header class="fixed top-0 inset-x-0 z-50 glass border-b border-border/60">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <a routerLink="/" class="flex items-center gap-3 group">
          <div
            class="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20 group-hover:shadow-violet-500/40 transition-shadow"
          >
            <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          <span class="font-semibold text-[15px] tracking-tight">UniSupport <span class="text-muted-foreground font-normal">AI</span></span>
        </a>

        <nav class="flex items-center gap-2 sm:gap-3">
          @if (auth.isAuthenticated()) {
            @if (auth.currentUser(); as user) {
              <div class="hidden sm:flex items-center gap-2.5 mr-1">
                <div class="w-7 h-7 rounded-full bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center text-[11px] font-bold text-white">
                  {{ user.full_name.charAt(0).toUpperCase() }}
                </div>
                <span class="text-sm text-muted-foreground max-w-[140px] truncate">{{ user.full_name }}</span>
              </div>
            }
            <ui-button routerLink="/app" size="sm" label="Open Chat" />
            <ui-button variant="ghost" size="sm" label="Sign out" (pressed)="auth.logout()" />
          } @else {
            <a routerLink="/login" class="text-sm text-muted-foreground hover:text-foreground transition-colors px-3 py-2 hidden sm:block">Sign in</a>
            <ui-button routerLink="/register" size="sm" label="Get Started" />
          }
        </nav>
      </div>
    </header>
  `,
})
export class SiteHeader {
  protected readonly auth = inject(AuthService);
}
