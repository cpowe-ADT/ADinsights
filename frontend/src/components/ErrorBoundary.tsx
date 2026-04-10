import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="phase2-page"
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '100vh',
            padding: '2rem',
            backgroundColor: 'var(--color-bg-subtle, #f9fafb)',
            color: 'var(--color-text, #111827)',
          }}
        >
          <div
            className="phase2-card"
            style={{ maxWidth: '32rem', width: '100%', textAlign: 'center' }}
          >
            <h1 style={{ margin: 0 }}>Something went wrong</h1>
            <p className="phase2-note">
              An unexpected error occurred. Please try again.
            </p>
            {import.meta.env.DEV && this.state.error && (
              <pre
                className="phase2-json"
                style={{ textAlign: 'left', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
              >
                {this.state.error.message}
              </pre>
            )}
            <div>
              <button type="button" className="button primary" onClick={this.handleReset}>
                Try again
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
