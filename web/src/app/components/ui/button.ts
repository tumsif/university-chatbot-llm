import { Component, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { cn } from '../../lib/utils';

type ButtonVariant = 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive' | 'link';
type ButtonSize = 'default' | 'sm' | 'lg' | 'icon';

@Component({
  selector: 'ui-button',
  standalone: true,
  imports: [RouterLink],
  template: `
    @if (routerLink(); as link) {
      <a [routerLink]="link" [class]="classes">{{ label() }}</a>
    } @else {
      <button [type]="type()" [disabled]="disabled()" [class]="classes" (click)="pressed.emit($event)">
        <ng-content />
      </button>
    }
  `,
})
export class UiButton {
  readonly variant = input<ButtonVariant>('default');
  readonly size = input<ButtonSize>('default');
  readonly type = input<'button' | 'submit' | 'reset'>('button');
  readonly disabled = input(false);
  readonly routerLink = input<string | string[] | null>(null);
  readonly label = input('');
  readonly className = input('', { alias: 'class' });
  readonly pressed = output<MouseEvent>();

  private readonly variants: Record<ButtonVariant, string> = {
    default:
      'bg-violet-600 text-white hover:bg-violet-500 shadow-sm shadow-violet-600/25 active:scale-[0.98]',
    secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border',
    outline:
      'border border-border bg-transparent hover:bg-accent hover:border-violet-500/30 text-foreground',
    ghost: 'hover:bg-accent text-muted-foreground hover:text-foreground',
    destructive: 'bg-destructive text-white hover:bg-destructive/90',
    link: 'text-violet-400 underline-offset-4 hover:underline hover:text-violet-300',
  };

  private readonly sizes: Record<ButtonSize, string> = {
    default: 'h-10 px-4 py-2 text-sm',
    sm: 'h-8 px-3.5 text-xs rounded-lg min-w-[5rem]',
    lg: 'h-12 px-8 text-base rounded-xl min-w-[10rem]',
    icon: 'h-10 w-10',
  };

  get classes(): string {
    return cn(
      'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium transition-all duration-150 no-underline',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
      'disabled:pointer-events-none disabled:opacity-50 cursor-pointer select-none',
      this.variants[this.variant()],
      this.sizes[this.size()],
      this.className(),
    );
  }
}
