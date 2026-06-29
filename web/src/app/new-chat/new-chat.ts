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

  ngOnInit() {
    // Reset any selected session in the sidebar
    this.chatService.currentSessionId.set(null);
  }

  protected prefillQuery(query: string) {
    this.userQuery.set(query);
  }

  protected sendQuery(query: string) {
    if (!query.trim() || this.isLoading()) return;

    this.isLoading.set(true);
    this.chatService.sendMessage(query, null).subscribe({
      next: (data) => {
        this.isLoading.set(false);
        // Navigate to the newly created session
        this.router.navigate(['/chat', data.session_id]);
      },
      error: (err) => {
        this.isLoading.set(false);
        console.error('Failed to start session:', err);
      }
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
