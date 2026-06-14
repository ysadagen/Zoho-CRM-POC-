import { Component, type ErrorInfo, type ReactNode } from 'react';

import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { logger } from '@/lib/logger';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * Last-resort boundary for render-time exceptions — prevents a white screen and
 * logs the crash through the single structured-logging sink. Recovery is a full
 * reload (React can't safely resume after a render throw).
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    logger.error('ui.crash', {
      message: error.message,
      stack: error.stack,
      componentStack: info.componentStack,
    });
  }

  private readonly handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <EmptyState
          icon="alertTriangle"
          title="Something went wrong"
          sub="An unexpected error occurred. Reloading the page usually fixes it."
          action={
            <Button variant="pri" icon="refresh" onClick={this.handleReload}>
              Reload page
            </Button>
          }
        />
      );
    }
    return this.props.children;
  }
}
