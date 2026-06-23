import { Component, OnInit, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { NgClass } from '@angular/common';

interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  category?: string;
  rag_used?: boolean;
  matched_faq?: string;
  rating?: 'Good' | 'Average' | 'Poor';
}

interface ChatSession {
  id: string;
  title: string;
  created_at: string;
}

interface HealthInfo {
  status: string;
  backend: string;
  llm_connected: boolean;
  llm_message: string;
  model_configured: string;
}

@Component({
  selector: 'app-root',
  imports: [FormsModule, NgClass],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App implements OnInit {
  private readonly http = inject(HttpClient);

  // Signals for state management
  protected readonly backendUrl = 'http://localhost:8000';
  protected readonly messages = signal<Message[]>([]);
  protected readonly userQuery = signal('');
  protected readonly isLoading = signal(false);
  protected readonly systemStatus = signal<'online' | 'degraded' | 'offline'>('offline');
  protected readonly healthDetails = signal<HealthInfo | null>(null);

  // Chat sessions state
  protected readonly sessions = signal<ChatSession[]>([]);
  protected readonly currentSessionId = signal<string | null>(null);

  ngOnInit() {
    this.checkSystemHealth();
    this.loadSessions();
  }

  protected checkSystemHealth() {
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
      }
    });
  }

  protected loadSessions() {
    this.http.get<ChatSession[]>(`${this.backendUrl}/sessions`).subscribe({
      next: (data) => {
        this.sessions.set(data);
      },
      error: (err) => console.error('Failed to load sessions:', err)
    });
  }

  protected selectSession(sessionId: string) {
    if (this.currentSessionId() === sessionId) return;

    this.currentSessionId.set(sessionId);
    this.isLoading.set(true);

    this.http.get<any[]>(`${this.backendUrl}/sessions/${sessionId}/messages`).subscribe({
      next: (data) => {
        this.isLoading.set(false);
        const msgs: Message[] = data.map(m => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          category: m.category,
          rag_used: m.rag_used,
          matched_faq: m.matched_faq,
          rating: m.rating as 'Good' | 'Average' | 'Poor' | undefined
        }));
        this.messages.set(msgs);
      },
      error: (err) => {
        this.isLoading.set(false);
        console.error('Failed to load session messages:', err);
      }
    });
  }

  protected startNewChat() {
    this.currentSessionId.set(null);
    this.messages.set([]);
  }

  protected deleteSession(sessionId: string, event: MouseEvent) {
    event.stopPropagation(); // Prevent selecting the session when clicking delete
    
    if (confirm('Are you sure you want to delete this chat conversation?')) {
      this.http.delete(`${this.backendUrl}/sessions/${sessionId}`).subscribe({
        next: () => {
          this.loadSessions();
          if (this.currentSessionId() === sessionId) {
            this.startNewChat();
          }
        },
        error: (err) => console.error('Failed to delete session:', err)
      });
    }
  }

  protected sendMessage() {
    const query = this.userQuery().trim();
    if (!query) {
      return;
    }

    // Add user query to chat history locally first
    const userMsg: Message = {
      role: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    this.messages.update(msgs => [...msgs, userMsg]);
    this.userQuery.set('');
    
    // Set loading state
    this.isLoading.set(true);

    const body = {
      question: query,
      session_id: this.currentSessionId()
    };

    // Call backend API
    this.http.post<any>(`${this.backendUrl}/ask`, body).subscribe({
      next: (data) => {
        this.isLoading.set(false);
        
        // Store session ID if we just created a session
        this.currentSessionId.set(data.session_id);

        // Update the last user message with its DB-assigned ID
        this.messages.update(msgs => {
          const updated = [...msgs];
          const lastUserIndex = updated.map(m => m.role).lastIndexOf('user');
          if (lastUserIndex !== -1) {
            updated[lastUserIndex].id = data.question_id;
          }
          return updated;
        });

        // Add assistant response to local messages
        const assistantMsg: Message = {
          id: data.answer_id,
          role: 'assistant',
          content: data.answer,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          category: data.category,
          rag_used: data.rag_used,
          matched_faq: data.matched_faq
        };
        this.messages.update(msgs => [...msgs, assistantMsg]);

        // Reload the sessions list to reflect updated or new titles
        this.loadSessions();
      },
      error: (err) => {
        this.isLoading.set(false);
        const errorDetail = err.error?.detail || 'Failed to communicate with the server. Please try again.';
        const errorMsg: Message = {
          role: 'assistant',
          content: `Error: ${errorDetail}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          category: 'Error'
        };
        this.messages.update(msgs => [...msgs, errorMsg]);
      }
    });
  }

  protected rateMessage(index: number, rating: 'Good' | 'Average' | 'Poor') {
    const msgs = this.messages();
    const msg = msgs[index];
    if (msg.role !== 'assistant' || !msg.id) return;

    // Set rating locally to update UI immediately
    msg.rating = rating;
    this.messages.set([...msgs]);

    // Send rating to backend for DB persistence
    this.http.post(`${this.backendUrl}/messages/${msg.id}/rate`, {
      rating: rating
    }).subscribe({
      next: () => console.log('Feedback submitted successfully'),
      error: (err) => console.error('Failed to submit feedback', err)
    });
  }
}
