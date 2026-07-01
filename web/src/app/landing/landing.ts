import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { UiButton } from '../components/ui/button';
import { SiteHeader } from '../components/site-header';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-landing',
  imports: [RouterLink, UiButton, SiteHeader],
  templateUrl: './landing.html',
})
export class Landing implements OnInit {
  protected readonly auth = inject(AuthService);

  protected readonly features = [
    {
      icon: '⚡',
      title: 'Instant answers',
      description: 'Get responses in seconds about registration, exams, and campus services.',
    },
    {
      icon: '🎯',
      title: 'FAQ-powered RAG',
      description: 'Grounded in official UDSM knowledge — not random internet guesses.',
    },
    {
      icon: '🔒',
      title: 'Self-hosted & private',
      description: 'Runs on campus infrastructure with Ollama. Your data stays local.',
    },
    {
      icon: '💬',
      title: 'Saved conversations',
      description: 'Pick up where you left off with persistent chat history per account.',
    },
  ];

  protected readonly topics = [
    'Course Registration',
    'Examination Rules',
    'Library Services',
    'ICT & ARIS',
    'Hostel Allocation',
    'Fee Structure',
    'Academic Calendar',
  ];

  protected readonly demoMessages = [
    { role: 'user', text: 'When is the ARIS registration deadline?' },
    {
      role: 'assistant',
      text: 'The ARIS registration deadline for Semester I is typically two weeks after the start of the semester. Check the academic calendar on the UDSM website for exact dates.',
      tag: 'Course Registration',
    },
    { role: 'user', text: 'How many books can I borrow?' },
    {
      role: 'assistant',
      text: 'Undergraduate students can borrow up to 3 books for 14 days. Postgraduate students may borrow up to 5 books for 30 days.',
      tag: 'Library Services',
    },
  ];

  ngOnInit(): void {
    if (this.auth.isAuthenticated()) {
      this.auth.fetchMe().subscribe({ error: () => {} });
    }
  }
}
