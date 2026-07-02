import { inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map, tap } from 'rxjs/operators';
import { formatLocalTime } from '../lib/time';
import { API_BASE_URL } from '../lib/api-config';

export interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  category?: string;
  rag_used?: boolean;
  matched_faq?: string;
  document_used?: boolean;
  document_filename?: string;
  rating?: 'Good' | 'Average' | 'Poor';
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  document_id?: string | null;
  document_filename?: string | null;
}

export interface UserDocument {
  id: string;
  filename: string;
  file_type: string;
  char_count: number;
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
  private readonly backendUrl = API_BASE_URL;

  readonly sessions = signal<ChatSession[]>([]);
  readonly currentSessionId = signal<string | null>(null);
  readonly activeDocument = signal<UserDocument | null>(null);
  readonly systemStatus = signal<'online' | 'degraded' | 'offline'>('offline');
  readonly healthDetails = signal<HealthInfo | null>(null);

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
        this.syncActiveDocumentForCurrentSession();
      },
      error: (err) => console.error('Failed to load sessions:', err),
    });
  }

  syncActiveDocumentForCurrentSession(): void {
    const sessionId = this.currentSessionId();
    if (!sessionId) return;
    const session = this.sessions().find((s) => s.id === sessionId);
    if (session?.document_id && session.document_filename) {
      const current = this.activeDocument();
      if (!current || current.id !== session.document_id) {
        this.activeDocument.set({
          id: session.document_id,
          filename: session.document_filename,
          file_type: session.document_filename.endsWith('.md') ? 'md' : 'txt',
          char_count: 0,
          created_at: session.created_at,
        });
      }
    } else if (session && !session.document_id) {
      this.activeDocument.set(null);
    }
  }

  setActiveDocument(doc: UserDocument | null): void {
    this.activeDocument.set(doc);
  }

  clearActiveDocument(): void {
    this.activeDocument.set(null);
  }

  uploadDocument(file: File, sessionId: string | null = null): Observable<UserDocument> {
    const form = new FormData();
    form.append('file', file);
    if (sessionId) {
      form.append('session_id', sessionId);
    }
    return this.http.post<UserDocument>(`${this.backendUrl}/documents/upload`, form).pipe(
      tap((doc) => this.activeDocument.set(doc)),
    );
  }

  deleteDocument(documentId: string): Observable<void> {
    return this.http.delete<void>(`${this.backendUrl}/documents/${documentId}`).pipe(
      tap(() => {
        if (this.activeDocument()?.id === documentId) {
          this.activeDocument.set(null);
        }
      }),
    );
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
          document_used: m.category === 'Document Q&A',
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

  sendMessage(question: string, sessionId: string | null, documentId?: string | null): Observable<any> {
    const body: {
      question: string;
      session_id: string | null;
      document_id?: string;
    } = { question, session_id: sessionId };

    const docId = documentId ?? this.activeDocument()?.id;
    if (docId) {
      body.document_id = docId;
    }

    return this.http.post<any>(`${this.backendUrl}/ask`, body).pipe(
      tap(() => {
        this.loadSessions();
      })
    );
  }

  rateMessage(messageId: string, rating: 'Good' | 'Average' | 'Poor'): Observable<any> {
    return this.http.post(`${this.backendUrl}/messages/${messageId}/rate`, { rating });
  }
}
