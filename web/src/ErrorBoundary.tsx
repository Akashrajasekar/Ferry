import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Ferry UI crashed:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          style={{
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
            padding: '40px',
            textAlign: 'center',
            background: '#0b0f14',
            color: '#e6edf3',
            fontFamily:
              "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
          }}
        >
          <h1 style={{ fontSize: '24px' }}>Something went off course.</h1>
          <p style={{ color: '#9aa7b4', maxWidth: '440px' }}>
            The page hit an unexpected error. Refreshing usually fixes it.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: '#4589ff',
              color: '#061019',
              border: 'none',
              borderRadius: '6px',
              padding: '10px 20px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
