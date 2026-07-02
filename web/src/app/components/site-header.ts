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
      <div class="max-w-6xl mx-auto px-3 sm:px-6 h-14 sm:h-16 flex items-center justify-between gap-2">
        <a routerLink="/" class="flex items-center gap-2 sm:gap-3 group min-w-0 shrink">
          <div
            class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center shadow-lg shadow-purple-500/20 shrink-0"
          >
            <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          <span class="font-semibold text-sm sm:text-[15px] tracking-tight truncate">
            UniSupport <span class="text-muted-foreground font-normal hidden xs:inline">AI</span>
          </span>
        </a>

        <nav class="flex items-center gap-1 sm:gap-2 shrink-0">
          @if (auth.isAuthenticated()) {
            @if (auth.currentUser(); as user) {
              <div class="hidden md:flex items-center gap-2 mr-1 max-w-[120px] lg:max-w-[140px]">
                <div class="w-7 h-7 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-[11px] font-bold text-white shrink-0">
                  {{ user.full_name.charAt(0).toUpperCase() }}
                </div>
                <span class="text-sm text-muted-foreground truncate">{{ user.full_name }}</span>
              </div>
            }
            <ui-button routerLink="/app" size="sm" label="Chat" class="sm:hidden" />
            <ui-button routerLink="/app" size="sm" label="Open Chat" class="hidden sm:inline-flex" />
            <button
              type="button"
              (click)="auth.logout()"
              class="h-8 px-2 sm:px-3 text-xs sm:text-sm text-muted-foreground hover:text-foreground hover:bg-accent rounded-lg transition-colors cursor-pointer"
            >
              <span class="hidden sm:inline">Sign out</span>
              <span class="sm:hidden">Out</span>
            </button>
          } @else {
            <a routerLink="/login" class="text-xs sm:text-sm text-muted-foreground hover:text-foreground transition-colors px-2 sm:px-3 py-1.5">Sign in</a>
            <ui-button routerLink="/register" size="sm" label="Start" class="sm:hidden" />
            <ui-button routerLink="/register" size="sm" label="Get Started" class="hidden sm:inline-flex" />
          }
        </nav>
      </div>
    </header>
  `,
})
export class SiteHeader {
  protected readonly auth = inject(AuthService);
}
