import { inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map, tap } from 'rxjs/operators';
import { formatLocalTime } from '../lib/time';

export interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  category?: string;
  rag_used?: boolean;
  matched_faq?: string;
  rating?: 'Good' | 'Average' | 'Poor';
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
}

export interface HealthInfo {
  status: string;
  backend: string;
  llm_connected: boolean;
  llm_message: string;
  model_configured: string;
}

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private readonly http = inject(HttpClient);
  private readonly backendUrl = 'http://localhost:8000';

  // Shared state signals
  readonly sessions = signal<ChatSession[]>([]);
  readonly currentSessionId = signal<string | null>(null);
  readonly systemStatus = signal<'online' | 'degraded' | 'offline'>('offline');
  readonly healthDetails = signal<HealthInfo | null>(null);

  constructor() {
    // Sessions and health are loaded after authentication in ChatLayout
  }

  checkSystemHealth(): void {
    this.http.get<HealthInfo>(`${this.backendUrl}/health`).subscribe({
      next: (data) => {
        this.healthDetails.set(data);
        if (data.status === 'healthy') {
          this.systemStatus.set('online');
        } else {
          this.systemStatus.set('degraded');
        }
      },
      error: (err) => {
        console.error('Backend health check failed:', err);
        this.systemStatus.set('offline');
        this.healthDetails.set(null);
      },
    });
  }

  loadSessions(): void {
    this.http.get<ChatSession[]>(`${this.backendUrl}/sessions`).subscribe({
      next: (data) => {
        this.sessions.set(data);
      },
      error: (err) => console.error('Failed to load sessions:', err),
    });
  }

  getSessionMessages(sessionId: string): Observable<Message[]> {
    return this.http.get<any[]>(`${this.backendUrl}/sessions/${sessionId}/messages`).pipe(
      map((data) =>
        data.map((m) => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: formatLocalTime(m.created_at),
          category: m.category,
          rag_used: m.rag_used,
          matched_faq: m.matched_faq,
          rating: m.rating as 'Good' | 'Average' | 'Poor' | undefined,
        }))
      )
    );
  }

  deleteSession(sessionId: string): Observable<void> {
    return this.http.delete<void>(`${this.backendUrl}/sessions/${sessionId}`).pipe(
      tap(() => {
        this.loadSessions();
      })
    );
  }

  sendMessage(question: string, sessionId: string | null): Observable<any> {
    const body = { question, session_id: sessionId };
    return this.http.post<any>(`${this.backendUrl}/ask`, body).pipe(
      tap(() => {
        this.loadSessions(); // Reload sessions to update titles or add new ones
      })
    );
  }

  rateMessage(messageId: string, rating: 'Good' | 'Average' | 'Poor'): Observable<any> {
    return this.http.post(`${this.backendUrl}/messages/${messageId}/rate`, { rating });
  }
}
