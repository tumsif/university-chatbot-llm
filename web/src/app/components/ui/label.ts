import { Component, input } from '@angular/core';
import { cn } from '../../lib/utils';

@Component({
  selector: 'ui-label',
  standalone: true,
  template: `
    <label [for]="htmlFor()" [class]="classes">
      <ng-content />
    </label>
  `,
})
export class UiLabel {
  readonly htmlFor = input('');
  readonly className = input('', { alias: 'class' });

  get classes(): string {
    return cn(
      'text-sm font-medium leading-none text-foreground peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
      this.className(),
    );
  }
}
