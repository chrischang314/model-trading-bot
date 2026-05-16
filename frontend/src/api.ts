import type {
  BacktestResult,
  OverviewRow,
  PaperSnapshot,
  SignalCatalogItem,
  SignalPoint,
  StrategyInfo,
  UniverseResponse
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json();
}

export async function fetchOverview(): Promise<OverviewRow[]> {
  const envelope = await request<{ data: OverviewRow[] }>("/overview");
  return envelope.data;
}

export async function fetchTimeseries(symbol: string): Promise<SignalPoint[]> {
  const envelope = await request<{ data: SignalPoint[] }>(`/timeseries/${symbol}`);
  return envelope.data;
}

export async function ingest(symbols: string[]): Promise<void> {
  await request("/ingest", {
    method: "POST",
    body: JSON.stringify({ symbols, period: "2y" })
  });
}

export async function addSymbols(symbols: string[]): Promise<void> {
  await request("/symbols", {
    method: "POST",
    body: JSON.stringify({ symbols, period: "2y" })
  });
}

export async function fetchStrategy(): Promise<StrategyInfo> {
  const envelope = await request<{ data: StrategyInfo }>("/strategy");
  return envelope.data;
}

export async function fetchSignalCatalog(): Promise<SignalCatalogItem[]> {
  const envelope = await request<{ data: SignalCatalogItem[] }>("/signals/catalog");
  return envelope.data;
}

export async function fetchLatestSignals(): Promise<OverviewRow[]> {
  const envelope = await request<{ data: OverviewRow[] }>("/signals/latest");
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

export async function runBacktest(symbol: string): Promise<BacktestResult> {
  const envelope = await request<{ data: BacktestResult }>("/backtests", {
    method: "POST",
    body: JSON.stringify({ symbol, initial_capital: 100000, fee_bps: 1, slippage_bps: 2 })
  });
  return envelope.data;
}

export async function runPaper(symbols: string[]): Promise<PaperSnapshot> {
  const envelope = await request<{ data: PaperSnapshot }>("/paper/run", {
    method: "POST",
    body: JSON.stringify({ symbols, cash: 100000 })
  });
  return envelope.data;
}
