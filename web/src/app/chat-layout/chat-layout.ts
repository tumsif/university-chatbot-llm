import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs/operators';
import { ChatService } from '../services/chat.service';
import { AuthService } from '../services/auth.service';
import { formatLocalDate } from '../lib/time';

@Component({
  selector: 'app-chat-layout',
  imports: [NgClass, FormsModule, RouterOutlet, RouterLink],
  templateUrl: './chat-layout.html',
  styleUrl: './chat-layout.css',
})
export class ChatLayout implements OnInit {
  protected readonly chatService = inject(ChatService);
  protected readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly sessions = this.chatService.sessions;
  protected readonly currentSessionId = this.chatService.currentSessionId;
  protected readonly systemStatus = this.chatService.systemStatus;
  protected readonly currentUser = this.authService.currentUser;
  protected readonly sidebarOpen = signal(false);
  protected readonly sidebarCollapsed = signal(false);
  protected readonly searchQuery = signal('');

  protected readonly filteredSessions = computed(() => {
    const q = this.searchQuery().trim().toLowerCase();
    const list = this.sessions();
    if (!q) return list;
    return list.filter((s) => s.title.toLowerCase().includes(q));
  });

  protected readonly pageTitle = computed(() => {
    const id = this.currentSessionId();
    if (!id) return 'New conversation';
    const session = this.sessions().find((s) => s.id === id);
    return session?.title ?? 'Chat';
  });

  protected readonly currentSession = computed(() => {
    const id = this.currentSessionId();
    if (!id) return null;
    return this.sessions().find((s) => s.id === id) ?? null;
  });

  protected formatSessionDate(iso: string): string {
    return formatLocalDate(iso);
  }

  ngOnInit(): void {
    this.chatService.checkSystemHealth();
    this.chatService.loadSessions();
    this.authService.fetchMe().subscribe({ error: () => this.authService.logout() });

    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe(() => {
      if (this.router.url === '/app' || this.router.url === '/app/') {
        this.chatService.currentSessionId.set(null);
      }
    });
  }

  protected toggleSidebar(): void {
    if (!this.sidebarOpen() && this.sidebarCollapsed()) {
      this.sidebarCollapsed.set(false);
    }
    this.sidebarOpen.update((v) => !v);
  }

  protected toggleCollapse(): void {
    this.sidebarCollapsed.update((v) => !v);
    this.sidebarOpen.set(false);
  }

  protected closeSidebar(): void {
    this.sidebarOpen.set(false);
  }

  protected startNewChat(): void {
    this.chatService.currentSessionId.set(null);
    this.closeSidebar();
    this.router.navigate(['/app']);
  }

  protected selectSession(sessionId: string): void {
    this.closeSidebar();
    this.router.navigate(['/app/chat', sessionId]);
  }

  protected deleteSession(sessionId: string, event: MouseEvent): void {
    event.stopPropagation();
    if (confirm('Delete this conversation?')) {
      this.chatService.deleteSession(sessionId).subscribe({
        next: () => {
          if (this.currentSessionId() === sessionId) {
            this.startNewChat();
          }
        },
        error: (err) => console.error('Failed to delete session:', err),
      });
    }
  }

  protected logout(): void {
    this.authService.logout();
  }
}
