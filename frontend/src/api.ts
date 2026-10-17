export type FreshnessStatus = 'fresh' | 'stale' | 'unavailable' | 'missing';
export type Point = { period_label: string; observation_date: string; value: number };
export type Source = {
  name: string;
  source_url: string;
  status: FreshnessStatus;
  limitation: string | null;
};
export type Indicator = {
  indicator: { id: string; name: string; unit: string };
  value: number | null;
  period_label: string | null;
  comparison_value: number | null;
  comparison_period_label: string | null;
  change: number | null;
  change_percent: number | null;
  as_of_date: string | null;
  history: Point[];
  freshness_status: FreshnessStatus;
  source: Source;
  message: string | null;
};
export type Dashboard = {
  generated_at: string;
  ticker: {
    symbol: string;
    name: string;
    last_price: number | null;
    change: number | null;
    change_percent: number | null;
    as_of: string | null;
    freshness_status: FreshnessStatus;
    source: Source;
  }[];
  indicators: Indicator[];
};
const api = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const configuredPollSeconds = Number(import.meta.env.VITE_DASHBOARD_POLL_SECONDS ?? 60);
export const dashboardPollMilliseconds = Number.isFinite(configuredPollSeconds) && configuredPollSeconds >= 15
  ? configuredPollSeconds * 1_000
  : 60_000;
const tokenKey = "economic-dashboard-token";
export const getToken = () => localStorage.getItem(tokenKey);
export const signOut = () => localStorage.removeItem(tokenKey);
export async function signIn(email: string, password: string): Promise<void> { const response = await fetch(`${api}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) }); if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail ?? "Unable to sign in."); const body = await response.json() as { access_token: string }; localStorage.setItem(tokenKey, body.access_token); }
export async function loadDashboard(signal?: AbortSignal): Promise<Dashboard> { const response = await fetch(`${api}/dashboard`, { signal, headers: { Authorization: `Bearer ${getToken()}` } }); if (!response.ok) throw new Error(response.status === 401 ? "Your session has expired." : "Dashboard data is unavailable."); return response.json() as Promise<Dashboard>; }
