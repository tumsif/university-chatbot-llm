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
  protected readonly inputError = signal('');

  protected readonly suggestions = [
    { emoji: '📅', label: 'Registration Deadlines', query: 'When is the deadline to register for classes?', color: 'text-purple-400 group-hover:text-purple-300' },
    { emoji: '📚', label: 'Library Regulations', query: 'How many books can I borrow from the library?', color: 'text-blue-400 group-hover:text-blue-300' },
    { emoji: '📝', label: 'Examination Policies', query: 'What are the rules for exam cancellations or sickness?', color: 'text-emerald-400 group-hover:text-emerald-300' },
    { emoji: '🏠', label: 'Hostel Application', query: 'How do I apply for hostel allocation?', color: 'text-amber-400 group-hover:text-amber-300' },
  ];

  ngOnInit() {
    this.chatService.currentSessionId.set(null);
  }

  protected onEnter(event: Event): void {
    const ke = event as KeyboardEvent;
    if (!ke.shiftKey) {
      ke.preventDefault();
      this.onSubmit();
    }
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
        console.error('Failed to start session:', err);
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
