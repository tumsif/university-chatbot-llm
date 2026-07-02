import { Component, input } from '@angular/core';
import { cn } from '../../lib/utils';

@Component({
  selector: 'ui-card',
  standalone: true,
  template: `
    <div [class]="classes">
      <ng-content />
    </div>
  `,
})
export class UiCard {
  readonly className = input('', { alias: 'class' });

  get classes(): string {
    return cn('rounded-xl border border-border bg-card text-card-foreground shadow-sm', this.className());
  }
}

@Component({
  selector: 'ui-card-header',
  standalone: true,
  template: `
    <div [class]="cn('flex flex-col space-y-1.5 p-6', className())">
      <ng-content />
    </div>
  `,
})
export class UiCardHeader {
  readonly className = input('', { alias: 'class' });
  protected readonly cn = cn;
}

@Component({
  selector: 'ui-card-title',
  standalone: true,
  template: `
    <h3 [class]="cn('text-2xl font-semibold leading-none tracking-tight', className())">
      <ng-content />
    </h3>
  `,
})
export class UiCardTitle {
  readonly className = input('', { alias: 'class' });
  protected readonly cn = cn;
}

@Component({
  selector: 'ui-card-description',
  standalone: true,
  template: `
    <p [class]="cn('text-sm text-muted-foreground', className())">
      <ng-content />
    </p>
  `,
})
export class UiCardDescription {
  readonly className = input('', { alias: 'class' });
  protected readonly cn = cn;
}

@Component({
  selector: 'ui-card-content',
  standalone: true,
  template: `
    <div [class]="cn('p-6 pt-0', className())">
      <ng-content />
    </div>
  `,
})
export class UiCardContent {
  readonly className = input('', { alias: 'class' });
  protected readonly cn = cn;
}
