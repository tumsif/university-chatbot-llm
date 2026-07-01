import { Component, computed, effect, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService, Message } from '../services/chat.service';
import { Title } from '@angular/platform-browser';

@Component({
  selector: 'app-chat',
  imports: [NgClass, FormsModule],
  templateUrl: './chat.html',
  styleUrl: './chat.css',
})
export class Chat implements OnInit {
  protected readonly chatService = inject(ChatService);
  private readonly route = inject(ActivatedRoute);
  private title = inject(Title);

  // State management signals
  protected readonly messages = signal<Message[]>([]);
  protected readonly userQuery = signal('');
  protected readonly isLoading = signal(false);
  protected readonly inputError = signal('');
  protected readonly systemStatus = this.chatService.systemStatus;

  protected readonly ratings = [
    { value: 'Good' as const, emoji: '👍', label: 'Good' },
    { value: 'Average' as const, emoji: '😐', label: 'Average' },
    { value: 'Poor' as const, emoji: '👎', label: 'Poor' },
  ];

  protected readonly currentSession = computed(() => {
    const currentId = this.chatService.currentSessionId();
    const sessions = this.chatService.sessions();

    return sessions.find((value) => value.id == currentId);
  });

  ngOnInit() {
    // Listen to route parameter changes to update state
    this.route.paramMap.subscribe((params) => {
      const sessionId = params.get('id');
      if (sessionId) {
        this.chatService.currentSessionId.set(sessionId);
        this.loadMessages(sessionId);
      }
    });
  }

  constructor() {
    effect(() => {
      const currentSession = this.currentSession();
      this.title.setTitle(currentSession?.title ?? 'New Chat');
    });
  }

  private loadMessages(sessionId: string) {
    this.isLoading.set(true);
    this.chatService.getSessionMessages(sessionId).subscribe({
      next: (data) => {
        this.messages.set(data);
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error('Failed to load session messages:', err);
        this.isLoading.set(false);
      },
    });
  }

  protected onEnter(event: Event): void {
    const ke = event as KeyboardEvent;
    if (!ke.shiftKey) {
      ke.preventDefault();
      this.sendMessage();
    }
  }

  protected sendMessage() {
    const query = this.userQuery().trim();
    if (!query) {
      this.inputError.set('Please enter a question before sending.');
      return;
    }
    this.inputError.set('');

    // Add user query to chat history locally first
    const userMsg: Message = {
      role: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    this.messages.update((msgs) => [...msgs, userMsg]);
    this.userQuery.set('');

    this.isLoading.set(true);
    const sessionId = this.chatService.currentSessionId();

    this.chatService.sendMessage(query, sessionId).subscribe({
      next: (data) => {
        this.isLoading.set(false);

        // Update the last user message with its DB-assigned ID
        this.messages.update((msgs) => {
          const updated = [...msgs];
          const lastUserIndex = updated.map((m) => m.role).lastIndexOf('user');
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
          matched_faq: data.matched_faq,
        };
        this.messages.update((msgs) => [...msgs, assistantMsg]);
      },
      error: (err) => {
        this.isLoading.set(false);
        const errorDetail =
          err.error?.detail || 'Failed to communicate with the server. Please try again.';
        const errorMsg: Message = {
          role: 'assistant',
          content: `Error: ${errorDetail}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          category: 'Error',
        };
        this.messages.update((msgs) => [...msgs, errorMsg]);
      },
    });
  }

  protected rateMessage(index: number, rating: 'Good' | 'Average' | 'Poor') {
    const msgs = this.messages();
    const msg = msgs[index];
    if (msg.role !== 'assistant' || !msg.id) return;

    // Set rating locally to update UI immediately
    msg.rating = rating;
    this.messages.set([...msgs]);

    // Send rating to backend
    this.chatService.rateMessage(msg.id, rating).subscribe({
      next: () => console.log('Feedback submitted successfully'),
      error: (err) => console.error('Failed to submit feedback', err),
    });
  }
}
