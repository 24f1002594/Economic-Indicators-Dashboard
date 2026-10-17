import { Component, FormEvent, ReactNode, useCallback, useEffect, useState } from 'react';
import { Dashboard as DashboardData, dashboardPollMilliseconds, getToken, loadDashboard, signIn, signOut } from './api';
import { Dashboard } from './components/Dashboard';
import { SkeletonGrid } from './components/layout/Skeleton';
import { TitleBar } from './components/layout/TitleBar';
import './components/layout/TitleBar.css';
import './components/layout/TickerBar.css';
import './components/layout/Skeleton.css';
import './components/cards/IndicatorCard.css';
import './components/cards/KPISubCard.css';
import './components/cards/ChartLegend.css';
import './components/charts/Charts.css';
import './components/Dashboard.css';
import './App.css';

// ── Error Boundary ───────────────────────────────────────────────────────────
class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="app-state">
        <h1>Economic Indicator Dashboard</h1>
        <p>An unexpected error occurred.</p>
        <button onClick={() => location.reload()}>Reload</button>
      </div>
    );
  }
}

// ── Login Page ───────────────────────────────────────────────────────────────
function Login({ complete }: { complete: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError('');
    try {
      await signIn(email, password);
      complete();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to sign in.');
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={submit} aria-label="Sign in form">
        {/* Header accent */}
        <div className="login-card__header">
          <div className="login-card__chart-bg" aria-hidden="true">
            <svg viewBox="0 0 420 80" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
              <polyline points="0,70 70,45 140,55 210,25 280,40 350,15 420,28"
                fill="none" stroke="#ef4444" strokeWidth="1.5" strokeOpacity="0.3" />
              <polyline points="0,55 70,65 140,35 210,50 280,22 350,38 420,20"
                fill="none" stroke="#38bdf8" strokeWidth="1.5" strokeOpacity="0.3" />
            </svg>
          </div>
          <h1 className="login-card__title">ECONOMIC INDICATOR</h1>
        </div>

        <div className="login-card__body">
          <p className="login-card__subtitle">Sign in to access the live economic dashboard.</p>

          <label className="login-card__field">
            <span>Email</span>
            <input
              id="login-email"
              name="email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoComplete="email"
              required
              placeholder="you@example.com"
            />
          </label>

          <label className="login-card__field">
            <span>Password</span>
            <input
              id="login-password"
              name="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              placeholder="••••••••"
            />
          </label>

          {error && <output className="login-card__error" role="alert">{error}</output>}

          <button
            id="login-submit"
            className="login-card__submit"
            type="submit"
            disabled={pending}
          >
            {pending ? 'Signing in…' : 'Sign in'}
          </button>

        </div>
      </form>
    </main>
  );
}


// ── App-level Error Banner ───────────────────────────────────────────────────
function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="app-state">
      <h1>Economic Indicator Dashboard</h1>
      <p>{message}</p>
      <button onClick={onRetry}>Try again</button>
    </div>
  );
}

// ── Root ─────────────────────────────────────────────────────────────────────
function Root() {
  const [authenticated, setAuthenticated] = useState(Boolean(getToken()));
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState('');

  const clearSession = useCallback(() => {
    signOut();
    setAuthenticated(false);
    setData(null);
    setError('');
  }, []);

  const refresh = useCallback(() => {
    const controller = new AbortController();
    setError('');
    loadDashboard(controller.signal)
      .then(setData)
      .catch((reason) => {
        if (String(reason?.message).includes('session')) {
          clearSession();
        } else {
          setError(reason instanceof Error ? reason.message : 'Dashboard data is unavailable.');
        }
      });
    return () => controller.abort();
  }, [clearSession]);

  useEffect(() => {
    if (!authenticated) return;
    const cancelInitialLoad = refresh();
    const pollingTimer = window.setInterval(refresh, dashboardPollMilliseconds);
    return () => {
      cancelInitialLoad();
      window.clearInterval(pollingTimer);
    };
  }, [authenticated, refresh]);

  if (authenticated) {
    if (!data && !error) {
      return (
        <>
          <div className="dashboard-shell">
            <TitleBar onSignOut={clearSession} />
            <SkeletonGrid />
          </div>
        </>
      );
    }
    if (data) {
      return (
        <Dashboard
          data={data}
          onRefresh={refresh}
          onSignOut={clearSession}
        />
      );
    }
    if (error) return <ErrorBanner message={error} onRetry={refresh} />;
  }

  if (!authenticated) {
    return <Login complete={() => setAuthenticated(true)} />;
  }

  return null;
}


export default function App() {
  return (
    <ErrorBoundary>
      <Root />
    </ErrorBoundary>
  );
}
