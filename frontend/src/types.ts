export type SignalValue = string | number | null;

export type OverviewRow = {
  [key: string]: SignalValue;
  date: string;
  sym: string;
  close: number;
  return_1d: number | null;
  return_5d: number | null;
  return_21d: number | null;
  return_63d: number | null;
  ema_12: number | null;
  ema_26: number | null;
  ema_50: number | null;
  sma_20: number | null;
  sma_50: number | null;
  sma_200: number | null;
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
  realized_vol_20: number | null;
  realized_vol_63: number | null;
  stoch_k: number | null;
  stoch_d: number | null;
  williams_r_14: number | null;
  cci_20: number | null;
  adx_14: number | null;
  plus_di_14: number | null;
  minus_di_14: number | null;
  obv: number | null;
  volume_z: number | null;
  rolling_vwap_20: number | null;
  momentum_20d: number | null;
  momentum_252_skip_21: number | null;
  zscore_20: number | null;
  donchian_high_20: number | null;
  donchian_low_20: number | null;
  donchian_breakout: number | null;
  keltner_mid: number | null;
  keltner_upper: number | null;
  keltner_lower: number | null;
  gap_return: number | null;
  intraday_return: number | null;
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
  [key: string]: SignalValue;
  date: string;
  sym: string;
  close: number;
  return_1d: number | null;
  return_5d: number | null;
  return_21d: number | null;
  return_63d: number | null;
  ema_12: number | null;
  ema_26: number | null;
  ema_50: number | null;
  sma_20: number | null;
  sma_50: number | null;
  sma_200: number | null;
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
  realized_vol_20: number | null;
  realized_vol_63: number | null;
  stoch_k: number | null;
  stoch_d: number | null;
  williams_r_14: number | null;
  cci_20: number | null;
  adx_14: number | null;
  plus_di_14: number | null;
  minus_di_14: number | null;
  obv: number | null;
  volume_z: number | null;
  rolling_vwap_20: number | null;
  momentum_20d: number | null;
  momentum_252_skip_21: number | null;
  zscore_20: number | null;
  donchian_high_20: number | null;
  donchian_low_20: number | null;
  donchian_breakout: number | null;
  keltner_mid: number | null;
  keltner_upper: number | null;
  keltner_lower: number | null;
  gap_return: number | null;
  intraday_return: number | null;
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
  strategy?: StrategyInfo;
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

export type BacktestComparison = {
  symbol: string;
  metrics: Record<string, number | null>;
  strategy: StrategyInfo;
  final_equity: number;
  trade_count: number;
};

export type PaperSnapshot = {
  run_id?: number;
  run_at?: string;
  cash: number;
  equity: number;
  positions: Array<{ sym: string; quantity: number; last_price: number; market_value: number }>;
  orders: Array<{ sym: string; side: string; notional: number; reason: string }>;
};

export type PaperRunSummary = {
  id: number;
  user_id: number;
  run_at: string;
  symbols: string[];
  strategy_id: string;
  requested_cash: number;
  cash: number;
  equity: number;
  position_count: number;
  order_count: number;
  warnings: string[];
  error_flags: Record<string, unknown>;
};

export type PaperRunDetail = PaperRunSummary & {
  custom_strategy: CustomStrategyConfig | null;
  positions: PaperSnapshot["positions"];
  orders: PaperSnapshot["orders"];
  snapshot: PaperSnapshot;
};

export type LocalUser = {
  id: number;
  username: string;
  created_at: string;
  updated_at: string;
};

export type CustomStrategyConfig = {
  name: string;
  min_signal_score: number;
  max_rsi: number;
  min_rsi: number | null;
  require_above_sma20: boolean;
  require_positive_macd: boolean;
  min_adx: number | null;
  min_momentum_score: number | null;
};

export type StrategyInfo = {
  id: string;
  name: string;
  label: string;
  kind: "built_in" | "custom";
  description: string;
  position_rule: string;
  components: Array<{
    key: string;
    label: string;
    signals: string[];
    range: [number, number];
  }>;
  indicator_notes: string[];
  custom?: CustomStrategyConfig;
  saved_strategy_id?: number;
  updated_at?: string;
};

export type UserState = {
  user: LocalUser;
  profile: {
    user_id: number;
    paper_cash: number;
    selected_strategy_id: string;
    created_at: string;
    updated_at: string;
  };
  strategies: Array<{
    id: number;
    strategy_id: string;
    user_id: number;
    name: string;
    label: string;
    config: CustomStrategyConfig;
    created_at: string;
    updated_at: string;
  }>;
  paper_portfolio: {
    snapshot: PaperSnapshot;
    cash: number;
    strategy_id: string;
    custom_strategy: CustomStrategyConfig | null;
    updated_at: string;
  } | null;
};

export type SignalCatalogItem = {
  key: string;
  label: string;
  group: string;
  description: string;
  formula?: string;
  interpretation?: string;
};

export type UniverseMember = {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
};

export type UniverseResponse = {
  source: string;
  as_of: string;
  count: number;
  members: UniverseMember[];
};

export type DiagnosticsFrame = {
  ok: boolean;
  rows: number;
  symbols: number;
  latest_date: string | null;
  missing_symbols: string[];
  age_days: number | null;
  stale: boolean;
  error?: string;
};

export type SystemDiagnostics = {
  app: string;
  generated_at: string;
  storage_ok: boolean;
  auth_ok: boolean;
  health: Record<string, unknown>;
  symbols: {
    count: number;
    items: string[];
  };
  bars: DiagnosticsFrame;
  signals: DiagnosticsFrame;
  universe: {
    ok: boolean;
    path: string;
    source: string;
    as_of: string | null;
    count: number;
    stale: boolean;
    error?: string;
  };
};
