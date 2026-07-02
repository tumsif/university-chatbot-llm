import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../services/chat.service';

@Component({
  selector: 'app-new-chat',
  imports: [FormsModule],
  templateUrl: './new-chat.html',
  styleUrl: './new-chat.css',
})
export class NewChat implements OnInit {
  protected readonly chatService = inject(ChatService);
  private readonly router = inject(Router);

  protected readonly userQuery = signal('');
  protected readonly isLoading = signal(false);
  protected readonly isUploading = signal(false);
  protected readonly inputError = signal('');
  protected readonly activeDocument = this.chatService.activeDocument;

  protected readonly suggestions = [
    { emoji: '📅', label: 'Registration Deadlines', query: 'When is the deadline to register for classes?', color: 'text-purple-400 group-hover:text-purple-300' },
    { emoji: '📚', label: 'Library Regulations', query: 'How many books can I borrow from the library?', color: 'text-blue-400 group-hover:text-blue-300' },
    { emoji: '📝', label: 'Examination Policies', query: 'What are the rules for exam cancellations or sickness?', color: 'text-emerald-400 group-hover:text-emerald-300' },
    { emoji: '🏠', label: 'Hostel Application', query: 'How do I apply for hostel allocation?', color: 'text-amber-400 group-hover:text-amber-300' },
  ];

  ngOnInit() {
    this.chatService.currentSessionId.set(null);
    this.chatService.clearActiveDocument();
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
    this.chatService.uploadDocument(file).subscribe({
      next: () => {
        this.isUploading.set(false);
        input.value = '';
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
    this.chatService.deleteDocument(doc.id).subscribe({
      error: (err) => console.error('Failed to delete document', err),
    });
  }

  protected sendQuery(query: string) {
    if (!query.trim() || this.isLoading()) return;
    this.isLoading.set(true);
    this.chatService.sendMessage(query, null).subscribe({
      next: (data) => {
        this.isLoading.set(false);
        this.router.navigate(['/app/chat', data.session_id]);
      },
      error: (err) => {
        this.isLoading.set(false);
        this.inputError.set(err.error?.detail || 'Failed to start session.');
      },
    });
  }

  protected onSubmit() {
    const query = this.userQuery().trim();
    if (!query) {
      this.inputError.set('Please enter a question before sending.');
      return;
    }
    this.inputError.set('');
    this.sendQuery(query);
    this.userQuery.set('');
  }
}
