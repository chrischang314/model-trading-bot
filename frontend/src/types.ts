export type OverviewRow = {
  date: string;
  sym: string;
  close: number;
  sma_20: number | null;
  sma_50: number | null;
  rsi_14: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_hist: number | null;
  trade_signal: "BUY" | "SELL" | "HOLD";
  position: number;
  volume: number;
  source: string;
  period_return: number;
};

export type SignalPoint = {
  date: string;
  sym: string;
  close: number;
  sma_20: number | null;
  sma_50: number | null;
  rsi_14: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_hist: number | null;
  trade_signal: string;
  position: number;
};

export type BacktestResult = {
  symbol: string;
  metrics: Record<string, number | null>;
  equity_curve: Array<{
    date: string;
    equity: number;
    benchmark_equity: number;
    drawdown: number;
    position: number;
  }>;
  trades: Array<{
    date: string;
    sym: string;
    side: string;
    price: number;
    position: number;
    equity: number;
  }>;
};

export type PaperSnapshot = {
  cash: number;
  equity: number;
  positions: Array<{ sym: string; quantity: number; last_price: number; market_value: number }>;
  orders: Array<{ sym: string; side: string; notional: number; reason: string }>;
};

