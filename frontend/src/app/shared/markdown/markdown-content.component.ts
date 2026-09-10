import { Component, computed, input, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { renderMarkdown } from './markdown.util';

@Component({
  selector: 'app-markdown-content',
  standalone: true,
  template: `<div
    class="markdown-body"
    [class.compact]="compact()"
    [class.as-title]="asTitle()"
    [innerHTML]="safeHtml()"
  ></div>`,
  styleUrl: './markdown-content.component.scss',
})
export class MarkdownContentComponent {
  readonly content = input<string>('');
  /** Compact spacing for lists and dialogs */
  readonly compact = input(false);
  /** Slightly larger heading look for exam question statements */
  readonly asTitle = input(false);

  private readonly sanitizer = inject(DomSanitizer);

  readonly safeHtml = computed<SafeHtml>(() =>
    this.sanitizer.bypassSecurityTrustHtml(renderMarkdown(this.content()))
  );
}
