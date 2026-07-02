import { Component, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { cn } from '../../lib/utils';

type ButtonVariant = 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive' | 'link';
type ButtonSize = 'default' | 'sm' | 'lg' | 'icon';

@Component({
  selector: 'ui-button',
  standalone: true,
  imports: [RouterLink],
  host: {
    class: 'contents',
  },
  template: `
    @if (routerLink(); as link) {
      <a [routerLink]="link" [class]="classes">{{ label() }}</a>
    } @else {
      <button [type]="type()" [disabled]="disabled()" [class]="classes" (click)="pressed.emit($event)">
        @if (label()) {
          <span>{{ label() }}</span>
        }
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
      'brand-gradient-b text-white shadow-sm shadow-purple-500/20 active:scale-[0.98]',
    secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border',
    outline:
      'border border-border bg-transparent hover:bg-accent hover:border-purple-500/30 text-foreground',
    ghost: 'hover:bg-accent text-muted-foreground hover:text-foreground',
    destructive: 'bg-destructive text-white hover:bg-destructive/90',
    link: 'text-purple-400 underline-offset-4 hover:underline hover:text-purple-300',
  };

  private readonly sizes: Record<ButtonSize, string> = {
    default: 'h-9 sm:h-10 px-3.5 sm:px-4 py-2 text-sm',
    sm: 'h-8 px-2.5 sm:px-3 text-xs sm:text-sm rounded-lg',
    lg: 'h-11 sm:h-12 px-5 sm:px-8 text-sm sm:text-base rounded-xl w-full sm:w-auto sm:min-w-[9rem]',
    icon: 'h-9 w-9 sm:h-10 sm:w-10',
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
