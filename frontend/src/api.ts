import type {
  BacktestComparison,
  BacktestResult,
  CustomStrategyConfig,
  IngestRun,
  OverviewRow,
  PaperPortfolio,
  PaperRunDetail,
  PaperRunSummary,
  PaperSnapshot,
  SignalCatalogItem,
  SignalPoint,
  StrategyInfo,
  SystemDiagnostics,
  UserState,
  UniverseResponse
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";
let activeUserId: number | null = null;

export function setApiUser(userId: number | null) {
  activeUserId = userId;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (activeUserId != null) {
    headers.set("X-User-Id", String(activeUserId));
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json();
}

export async function login(username: string): Promise<UserState> {
  const envelope = await request<{ data: UserState }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username })
  });
  setApiUser(envelope.data.user.id);
  return envelope.data;
}

export async function fetchUserState(): Promise<UserState> {
  const envelope = await request<{ data: UserState }>("/user/state");
  return envelope.data;
}

export async function fetchOverview(strategyId?: string, customStrategy?: CustomStrategyConfig): Promise<OverviewRow[]> {
  const envelope = await request<{ data: OverviewRow[] }>(`/overview${strategyQuery(strategyId, customStrategy)}`);
  return envelope.data;
}

export async function fetchDiagnostics(): Promise<SystemDiagnostics> {
  const envelope = await request<{ data: SystemDiagnostics }>("/diagnostics");
  return envelope.data;
}

export async function fetchTimeseries(symbol: string, strategyId?: string, customStrategy?: CustomStrategyConfig): Promise<SignalPoint[]> {
  const envelope = await request<{ data: SignalPoint[] }>(`/timeseries/${symbol}${strategyQuery(strategyId, customStrategy)}`);
  return envelope.data;
}

export async function ingest(symbols: string[]): Promise<void> {
  await request("/ingest", {
    method: "POST",
    body: JSON.stringify({ symbols, period: "2y" })
  });
}

export async function fetchIngestRuns(limit = 25): Promise<IngestRun[]> {
  const envelope = await request<{ data: IngestRun[] }>(`/ingest/runs?limit=${limit}`);
  return envelope.data;
}

export async function addSymbols(symbols: string[]): Promise<void> {
  await request("/symbols", {
    method: "POST",
    body: JSON.stringify({ symbols, period: "2y" })
  });
}

export async function fetchStrategies(): Promise<StrategyInfo[]> {
  const envelope = await request<{ data: StrategyInfo[] }>("/strategies");
  return envelope.data;
}

export async function saveUserStrategy(strategy: CustomStrategyConfig): Promise<StrategyInfo> {
  const envelope = await request<{ data: StrategyInfo }>("/user/strategies", {
    method: "POST",
    body: JSON.stringify({ strategy })
  });
  return envelope.data;
}

export async function resetModelAccount(): Promise<UserState> {
  const envelope = await request<{ data: UserState }>("/user/account/reset", { method: "POST" });
  return envelope.data;
}

export async function fetchPaperPortfolio(): Promise<PaperPortfolio | null> {
  const envelope = await request<{ data: PaperPortfolio | null }>("/paper/portfolio");
  return envelope.data;
}

export async function fetchStrategy(strategyId?: string, customStrategy?: CustomStrategyConfig): Promise<StrategyInfo> {
  const envelope = await request<{ data: StrategyInfo }>(`/strategy${strategyQuery(strategyId, customStrategy)}`);
  return envelope.data;
}

export async function fetchSignalCatalog(): Promise<SignalCatalogItem[]> {
  const envelope = await request<{ data: SignalCatalogItem[] }>("/signals/catalog");
  return envelope.data;
}

export async function fetchLatestSignals(strategyId?: string, customStrategy?: CustomStrategyConfig): Promise<OverviewRow[]> {
  const envelope = await request<{ data: OverviewRow[] }>(`/signals/latest${strategyQuery(strategyId, customStrategy)}`);
  return envelope.data;
}

export async function fetchSp500Universe(refresh = false): Promise<UniverseResponse> {
  const envelope = await request<{ data: UniverseResponse }>(`/universe/sp500${refresh ? "?refresh=true" : ""}`);
  return envelope.data;
}

export async function refreshSp500Universe(): Promise<UniverseResponse> {
  const envelope = await request<{ data: UniverseResponse }>("/universe/sp500/refresh", { method: "POST" });
  return envelope.data;
}

export async function runBacktest(symbol: string, strategyId?: string, customStrategy?: CustomStrategyConfig): Promise<BacktestResult> {
  const envelope = await request<{ data: BacktestResult }>("/backtests", {
    method: "POST",
    body: JSON.stringify({ symbol, initial_capital: 100000, fee_bps: 1, slippage_bps: 2, strategy_id: strategyId, custom_strategy: customStrategy })
  });
  return envelope.data;
}

export async function compareBacktests(symbol: string, strategyIds: string[], customStrategy?: CustomStrategyConfig): Promise<BacktestComparison[]> {
  const envelope = await request<{ data: { symbol: string; comparisons: BacktestComparison[] } }>("/backtests/compare", {
    method: "POST",
    body: JSON.stringify({ symbol, strategy_ids: strategyIds, initial_capital: 100000, fee_bps: 1, slippage_bps: 2, custom_strategy: customStrategy })
  });
  return envelope.data.comparisons;
}

export async function runPaper(symbols: string[], strategyId?: string, customStrategy?: CustomStrategyConfig): Promise<PaperSnapshot> {
  const envelope = await request<{ data: PaperSnapshot }>("/paper/run", {
    method: "POST",
    body: JSON.stringify({ symbols, cash: 100000, strategy_id: strategyId, custom_strategy: customStrategy })
  });
  return envelope.data;
}

export async function fetchPaperRuns(): Promise<PaperRunSummary[]> {
  const envelope = await request<{ data: PaperRunSummary[] }>("/paper/runs");
  return envelope.data;
}

export async function fetchPaperRun(runId: number): Promise<PaperRunDetail> {
  const envelope = await request<{ data: PaperRunDetail }>(`/paper/runs/${runId}`);
  return envelope.data;
}

function strategyQuery(strategyId?: string, customStrategy?: CustomStrategyConfig) {
  if (!strategyId) {
    return "";
  }
  const params = new URLSearchParams({ strategy_id: strategyId });
  if (strategyId === "custom_scorecard" && customStrategy) {
    params.set("custom_name", customStrategy.name);
    params.set("min_signal_score", String(customStrategy.min_signal_score));
    params.set("max_rsi", String(customStrategy.max_rsi));
    params.set("require_above_sma20", String(customStrategy.require_above_sma20));
    params.set("require_positive_macd", String(customStrategy.require_positive_macd));
    if (customStrategy.min_rsi != null) params.set("min_rsi", String(customStrategy.min_rsi));
    if (customStrategy.min_adx != null) params.set("min_adx", String(customStrategy.min_adx));
    if (customStrategy.min_momentum_score != null) params.set("min_momentum_score", String(customStrategy.min_momentum_score));
  }
  return `?${params.toString()}`;
}
