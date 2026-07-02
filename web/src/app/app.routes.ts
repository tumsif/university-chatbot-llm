import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './guards/auth.guard';
import { Landing } from './landing/landing';
import { Login } from './auth/login';
import { Register } from './auth/register';
import { ChatLayout } from './chat-layout/chat-layout';
import { NewChat } from './new-chat/new-chat';
import { Chat } from './chat/chat';

export const routes: Routes = [
  {
    path: '',
    component: Landing,
    title: 'UniSupport AI — UDSM Student Support',
  },
  {
    path: 'login',
    component: Login,
    canActivate: [guestGuard],
    title: 'Sign in — UniSupport AI',
  },
  {
    path: 'register',
    component: Register,
    canActivate: [guestGuard],
    title: 'Create account — UniSupport AI',
  },
  {
    path: 'app',
    component: ChatLayout,
    canActivate: [authGuard],
    children: [
      {
        path: '',
        component: NewChat,
        title: 'New Chat — UniSupport AI',
      },
      {
        path: 'chat/:id',
        component: Chat,
        title: 'Chat — UniSupport AI',
      },
    ],
  },
  {
    path: '**',
    redirectTo: '',
  },
];
