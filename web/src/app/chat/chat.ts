import { Component, computed, effect, ElementRef, inject, OnInit, signal, ViewChild } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService, Message, UserDocument } from '../services/chat.service';
import { Title } from '@angular/platform-browser';
import { nowLocalTime } from '../lib/time';

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

  @ViewChild('messagesContainer') private messagesContainer?: ElementRef<HTMLDivElement>;

  protected readonly messages = signal<Message[]>([]);
  protected readonly userQuery = signal('');
  protected readonly isLoading = signal(false);
  protected readonly inputError = signal('');
  protected readonly copiedIndex = signal<number | null>(null);
  protected readonly isUploading = signal(false);
  protected readonly systemStatus = this.chatService.systemStatus;
  protected readonly activeDocument = this.chatService.activeDocument;
  private readonly pendingFooterDocument = signal<UserDocument | null>(null);

  /** Shown in footer before send; cleared once the message is sent. */
  protected readonly footerDocument = computed(() => {
    const pending = this.pendingFooterDocument();
    if (pending) return pending;
    const active = this.activeDocument();
    if (active && this.userQuery().trim()) return active;
    return null;
  });

  protected readonly ratings = [
    { value: 'Good' as const, emoji: '👍', label: 'Good' },
    { value: 'Average' as const, emoji: '😐', label: 'Average' },
    { value: 'Poor' as const, emoji: '👎', label: 'Poor' },
  ];

  protected readonly currentSession = computed(() => {
    const currentId = this.chatService.currentSessionId();
    return this.chatService.sessions().find((value) => value.id == currentId);
  });

  ngOnInit() {
    this.route.paramMap.subscribe((params) => {
      const sessionId = params.get('id');
      if (sessionId) {
        this.chatService.currentSessionId.set(sessionId);
        this.chatService.syncActiveDocumentForCurrentSession();
        this.loadMessages(sessionId);
      }
    });
  }

  constructor() {
    effect(() => {
      const currentSession = this.currentSession();
      this.title.setTitle(currentSession?.title ?? 'New Chat');
    });

    effect(() => {
      this.messages();
      this.isLoading();
      this.scrollToBottom();
    });
  }

  private annotateDocumentOnUserMessages(messages: Message[]): Message[] {
    const session = this.currentSession();
    const docName = session?.document_filename;
    if (!docName) return messages;

    return messages.map((msg, index) => {
      if (msg.role !== 'user' || msg.document_filename) return msg;
      const next = messages[index + 1];
      if (
        next?.role === 'assistant' &&
        (next.document_used || next.category === 'Document Q&A')
      ) {
        return { ...msg, document_filename: docName };
      }
      return msg;
    });
  }

  private loadMessages(sessionId: string) {
    this.isLoading.set(true);
    this.chatService.getSessionMessages(sessionId).subscribe({
      next: (data) => {
        this.messages.set(this.annotateDocumentOnUserMessages(data));
        this.isLoading.set(false);
        this.scrollToBottom();
      },
      error: (err) => {
        console.error('Failed to load session messages:', err);
        this.isLoading.set(false);
      },
    });
  }

  private scrollToBottom(): void {
    requestAnimationFrame(() => {
      const el = this.messagesContainer?.nativeElement;
      if (el) {
        el.scrollTop = el.scrollHeight;
      }
    });
  }

  protected sendMessage() {
    const query = this.userQuery().trim();
    if (!query) {
      this.inputError.set('Please enter a question before sending.');
      return;
    }
    this.inputError.set('');

    const doc = this.activeDocument();
    const userMsg: Message = {
      role: 'user',
      content: query,
      timestamp: nowLocalTime(),
      ...(doc ? { document_filename: doc.filename } : {}),
    };
    this.messages.update((msgs) => [...msgs, userMsg]);
    this.pendingFooterDocument.set(null);
    this.userQuery.set('');
    this.isLoading.set(true);

    const sessionId = this.chatService.currentSessionId();

    this.chatService.sendMessage(query, sessionId).subscribe({
      next: (data) => {
        this.isLoading.set(false);
        this.messages.update((msgs) => {
          const updated = [...msgs];
          const lastUserIndex = updated.map((m) => m.role).lastIndexOf('user');
          if (lastUserIndex !== -1) {
            updated[lastUserIndex].id = data.question_id;
          }
          return updated;
        });

        const assistantMsg: Message = {
          id: data.answer_id,
          role: 'assistant',
          content: data.answer,
          timestamp: nowLocalTime(),
          category: data.category,
          rag_used: data.rag_used,
          matched_faq: data.matched_faq,
          document_used: data.document_used,
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
          timestamp: nowLocalTime(),
          category: 'Error',
        };
        this.messages.update((msgs) => [...msgs, errorMsg]);
      },
    });
  }

  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    const name = file.name.toLowerCase();
    if (!name.endsWith('.txt') && !name.endsWith('.md')) {
      this.inputError.set('Only .txt and .md files are supported.');
      input.value = '';
      return;
    }

    this.inputError.set('');
    this.isUploading.set(true);
    const sessionId = this.chatService.currentSessionId();
    this.chatService.uploadDocument(file, sessionId).subscribe({
      next: () => {
        this.isUploading.set(false);
        input.value = '';
        this.pendingFooterDocument.set(this.activeDocument());
        this.chatService.loadSessions();
      },
      error: (err) => {
        this.isUploading.set(false);
        input.value = '';
        this.inputError.set(err.error?.detail || 'Failed to upload document.');
      },
    });
  }

  protected removeDocument(): void {
    const doc = this.activeDocument();
    if (!doc) return;
    this.pendingFooterDocument.set(null);
    this.chatService.deleteDocument(doc.id).subscribe({
      next: () => this.chatService.loadSessions(),
      error: (err) => console.error('Failed to delete document', err),
    });
  }

  protected async copyMessage(index: number, content: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(content);
      this.copiedIndex.set(index);
      setTimeout(() => this.copiedIndex.set(null), 2000);
    } catch {
      /* clipboard unavailable */
    }
  }

  protected rateMessage(index: number, rating: 'Good' | 'Average' | 'Poor') {
    const msgs = [...this.messages()];
    const msg = msgs[index];
    if (!msg || msg.role !== 'assistant' || !msg.id) return;

    msgs[index] = { ...msg, rating };
    this.messages.set(msgs);

    this.chatService.rateMessage(msg.id, rating).subscribe({
      error: (err) => console.error('Failed to submit feedback', err),
    });
  }
}
