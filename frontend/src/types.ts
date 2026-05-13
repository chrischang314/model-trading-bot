export type OverviewRow = {
  date: string;
  sym: string;
  close: number;
  ema_12: number | null;
  ema_26: number | null;
  sma_20: number | null;
  sma_50: number | null;
  rsi_14: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_hist: number | null;
  bb_mid: number | null;
  bb_upper: number | null;
  bb_lower: number | null;
  bb_width: number | null;
  atr_14: number | null;
  atr_pct: number | null;
  stoch_k: number | null;
  stoch_d: number | null;
  obv: number | null;
  volume_z: number | null;
  momentum_20d: number | null;
  distance_52w_high: number | null;
  trend_score: number | null;
  momentum_score: number | null;
  volatility_score: number | null;
  volume_score: number | null;
  signal_score: number | null;
  signal_reason: string | null;
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
  ema_12: number | null;
  ema_26: number | null;
  sma_20: number | null;
  sma_50: number | null;
  rsi_14: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_hist: number | null;
  bb_mid: number | null;
  bb_upper: number | null;
  bb_lower: number | null;
  bb_width: number | null;
  atr_14: number | null;
  atr_pct: number | null;
  stoch_k: number | null;
  stoch_d: number | null;
  obv: number | null;
  volume_z: number | null;
  momentum_20d: number | null;
  distance_52w_high: number | null;
  trend_score: number | null;
  momentum_score: number | null;
  volatility_score: number | null;
  volume_score: number | null;
  signal_score: number | null;
  signal_reason: string | null;
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

export type StrategyInfo = {
  name: string;
  position_rule: string;
  components: Array<{
    key: "trend_score" | "momentum_score" | "volatility_score" | "volume_score";
    label: string;
    signals: string[];
    range: [number, number];
  }>;
  indicator_notes: string[];
};
