import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactElement, ReactNode } from "react";
import {
  Activity,
  BarChart3,
  ChevronDown,
  ChevronRight,
  Database,
  Gauge,
  LogOut,
  Layers,
  LineChart as LineIcon,
  Play,
  Plus,
  RefreshCw,
  Search,
  Server,
  SlidersHorizontal,
  UserRound,
  Wallet
} from "lucide-react";
import {
  Bar,
  Brush,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import {
  addSymbols,
  fetchUserState,
  fetchLatestSignals,
  fetchOverview,
  fetchSignalCatalog,
  fetchSp500Universe,
  fetchStrategies,
  fetchStrategy,
  fetchTimeseries,
  ingest,
  login,
  refreshSp500Universe,
  resetModelAccount,
  runBacktest,
  runPaper,
  saveUserStrategy,
  setApiUser
} from "./api";
import type {
  BacktestResult,
  CustomStrategyConfig,
  OverviewRow,
  PaperSnapshot,
  SignalCatalogItem,
  SignalPoint,
  SignalValue,
  StrategyInfo,
  LocalUser,
  UniverseResponse
} from "./types";

const DEFAULT_SYMBOLS = ["AAPL", "AMZN", "META", "NFLX", "GOOGL"];
const DEFAULT_STRATEGY_ID = "multi_factor_scorecard";
const CUSTOM_STRATEGY_ID = "custom_scorecard";
const DEFAULT_CUSTOM_STRATEGY: CustomStrategyConfig = {
  name: "Custom scorecard",
  min_signal_score: 5,
  max_rsi: 78,
  min_rsi: null,
  require_above_sma20: true,
  require_positive_macd: false,
  min_adx: null,
  min_momentum_score: null
};
const PAGES = ["home", "stock", "signals", "backtesting"] as const;
type Page = (typeof PAGES)[number];

const SYSTEM_LESSON_STEPS = [
  {
    id: "data",
    label: "Data",
    principle: "Every trading model starts as a market data pipeline.",
    mechanism: "The backend fetches daily bars, stores them through the storage adapter, and keeps a cached S&P 500 universe for ticker discovery.",
    watch: "Bad inputs create convincing but useless signals, so production systems spend a lot of effort on validation, adjustment, and lineage."
  },
  {
    id: "signals",
    label: "Signals",
    principle: "Indicators compress noisy price history into comparable features.",
    mechanism: "The signal engine calculates trend, momentum, volatility, and volume fields, then stores the full matrix so each decision can be inspected later.",
    watch: "A signal is not a trade by itself. It needs context, thresholds, and risk controls before it becomes a position."
  },
  {
    id: "strategy",
    label: "Strategy",
    principle: "A strategy turns many indicators into a repeatable rule.",
    mechanism: "Built-in and custom scorecards combine component scores into a long or cash stance, with a text reason attached to the latest decision.",
    watch: "Simple rules are easier to explain and debug. Complexity should earn its seat."
  },
  {
    id: "backtest",
    label: "Backtest",
    principle: "A backtest is a simulator for rules, timing, costs, and risk.",
    mechanism: "Positions are applied on the next bar, fees and slippage are deducted, and equity is compared with a buy-and-hold benchmark.",
    watch: "Great-looking historical returns can still be overfit, biased, or impossible to trade at scale."
  },
  {
    id: "paper",
    label: "Paper",
    principle: "Paper trading connects a strategy to portfolio accounting without sending live orders.",
    mechanism: "The paper engine creates a one-step allocation snapshot, showing intended orders, positions, cash, and mark-to-market equity.",
    watch: "Execution, fills, borrow, taxes, outages, and limits are intentionally outside this toy app."
  }
] as const;
type SystemLessonId = (typeof SYSTEM_LESSON_STEPS)[number]["id"];

const PRICE_RANGE_OPTIONS = [
  ["3M", 63],
  ["6M", 126],
  ["1Y", 252],
  ["All", null]
] as const;
type PriceRangeLabel = (typeof PRICE_RANGE_OPTIONS)[number][0];

const PRICE_LAYER_CONFIG = [
  { key: "close", label: "Close", color: "#111827" },
  { key: "sma20", label: "SMA 20", color: "#0f766e" },
  { key: "sma50", label: "SMA 50", color: "#d97706" },
  { key: "sma200", label: "SMA 200", color: "#4f46e5" },
  { key: "bollinger", label: "Bollinger", color: "#be123c" },
  { key: "keltner", label: "Keltner", color: "#64748b" },
  { key: "position", label: "Position", color: "#10b981" }
] as const;
type PriceLayerKey = (typeof PRICE_LAYER_CONFIG)[number]["key"];

const EQUITY_LAYER_CONFIG = [
  { key: "equity", label: "Strategy", color: "#0f766e" },
  { key: "benchmark", label: "Benchmark", color: "#64748b" },
  { key: "drawdown", label: "Drawdown", color: "#dc2626" },
  { key: "position", label: "Position", color: "#10b981" }
] as const;
type EquityLayerKey = (typeof EQUITY_LAYER_CONFIG)[number]["key"];

const SIGNAL_MATRIX_COLUMNS = [
  ["signal_score", "Score"],
  ["trend_score", "Trend"],
  ["momentum_score", "Momentum"],
  ["volatility_score", "Vol"],
  ["volume_score", "Volume"],
  ["close", "Close"],
  ["sma_20", "SMA 20"],
  ["sma_50", "SMA 50"],
  ["sma_200", "SMA 200"],
  ["rsi_14", "RSI"],
  ["macd_hist", "MACD Hist"],
  ["adx_14", "ADX"],
  ["stoch_k", "Stoch %K"],
  ["williams_r_14", "Williams %R"],
  ["cci_20", "CCI"],
  ["bb_width", "BB Width"],
  ["atr_pct", "ATR %"],
  ["realized_vol_20", "20D Vol"],
  ["volume_z", "Vol Z"],
  ["momentum_20d", "20D Mom"],
  ["momentum_252_skip_21", "12-1 Mom"],
  ["zscore_20", "Z 20"],
  ["distance_52w_high", "52W Dist"]
] as const;

const SIGNAL_TREND_EXTRAS = [
  ["signal_score", "Score", "strategy"],
  ["trend_score", "Trend Score", "strategy"],
  ["momentum_score", "Momentum Score", "strategy"],
  ["volatility_score", "Volatility Score", "strategy"],
  ["volume_score", "Volume Score", "strategy"],
  ["close", "Close", "price"],
  ["return_1d", "1D Return", "returns"],
  ["return_21d", "21D Return", "returns"],
  ["return_63d", "63D Return", "returns"]
] as const;

const SIGNAL_TREND_PRESETS: Record<string, string[]> = {
  Scores: ["signal_score", "trend_score", "momentum_score", "volatility_score", "volume_score"],
  Trend: ["close", "sma_20", "sma_50", "sma_200", "macd_hist", "adx_14", "donchian_breakout"],
  Momentum: ["rsi_14", "stoch_k", "stoch_d", "williams_r_14", "cci_20", "momentum_20d", "momentum_252_skip_21"],
  Volatility: ["bb_width", "atr_pct", "realized_vol_20", "realized_vol_63", "keltner_upper", "keltner_lower"],
  Volume: ["obv", "volume_z", "rolling_vwap_20"],
  Returns: ["return_1d", "return_21d", "return_63d", "distance_52w_high"]
};

const SIGNAL_TREND_COLORS = [
  "#0f766e",
  "#2563eb",
  "#d97706",
  "#7c3aed",
  "#dc2626",
  "#059669",
  "#4f46e5",
  "#9333ea",
  "#b45309",
  "#0e7490",
  "#be123c",
  "#64748b"
];

type SignalTrendScale = "normalized" | "raw";
type SignalTrendOption = { key: string; label: string; group: string };
type TrendChartPoint = {
  date: string;
  position: number | null;
  [key: string]: string | number | null;
};

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const pct = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 });

export function App() {
  const [page, setPage] = useState<Page>("home");
  const [overview, setOverview] = useState<OverviewRow[]>([]);
  const [latestSignals, setLatestSignals] = useState<OverviewRow[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState(DEFAULT_SYMBOLS[0]);
  const [series, setSeries] = useState<SignalPoint[]>([]);
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [paper, setPaper] = useState<PaperSnapshot | null>(null);
  const [strategy, setStrategy] = useState<StrategyInfo | null>(null);
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [currentUser, setCurrentUser] = useState<LocalUser | null>(null);
  const [selectedStrategyId, setSelectedStrategyId] = useState(DEFAULT_STRATEGY_ID);
  const [customStrategy, setCustomStrategy] = useState<CustomStrategyConfig>(DEFAULT_CUSTOM_STRATEGY);
  const [catalog, setCatalog] = useState<SignalCatalogItem[]>([]);
  const [universe, setUniverse] = useState<UniverseResponse | null>(null);
  const [newSymbol, setNewSymbol] = useState("");
  const [loginName, setLoginName] = useState("");
  const [signalFilter, setSignalFilter] = useState("");
  const [appLoading, setAppLoading] = useState(true);
  const [authLoading, setAuthLoading] = useState(false);
  const [symbolLoading, setSymbolLoading] = useState(false);
  const [addingSymbol, setAddingSymbol] = useState(false);
  const [refreshingData, setRefreshingData] = useState(false);
  const [syncingUniverse, setSyncingUniverse] = useState(false);
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [savingStrategy, setSavingStrategy] = useState(false);
  const [resettingAccount, setResettingAccount] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const symbols = useMemo(() => overview.map((row) => row.sym), [overview]);
  const latest = overview.find((row) => row.sym === selectedSymbol) ?? overview[0];
  const scoreTone = (latest?.signal_score ?? 0) >= 5 ? "positive" : (latest?.signal_score ?? 0) < 0 ? "negative" : "neutral";
  const universeOptions = useMemo(() => universe?.members.map((member) => member.symbol) ?? [], [universe]);
  const selectedCustomStrategy = selectedStrategyId === CUSTOM_STRATEGY_ID ? customStrategy : undefined;
  const displayedSignals = useMemo(() => {
    const needle = signalFilter.trim().toUpperCase();
    if (!needle) {
      return latestSignals;
    }
    return latestSignals.filter((row) => row.sym.includes(needle) || String(row.signal_reason ?? "").toUpperCase().includes(needle));
  }, [latestSignals, signalFilter]);

  async function loadApp(symbol = selectedSymbol) {
    setAppLoading(true);
    setError(null);
    try {
      const [rows, signalRows, strategyInfo, strategyRows, catalogRows, universeRows] = await Promise.all([
        fetchOverview(selectedStrategyId, selectedCustomStrategy),
        fetchLatestSignals(selectedStrategyId, selectedCustomStrategy),
        fetchStrategy(selectedStrategyId, selectedCustomStrategy),
        fetchStrategies(),
        fetchSignalCatalog(),
        fetchSp500Universe(false).catch(() => null)
      ]);
      setOverview(rows);
      setLatestSignals(signalRows);
      setStrategy(strategyInfo);
      setStrategies(strategyRows);
      setCatalog(catalogRows);
      if (universeRows) {
        setUniverse(universeRows);
      }
      const active = rows.some((row) => row.sym === symbol) ? symbol : rows[0]?.sym ?? DEFAULT_SYMBOLS[0];
      setSelectedSymbol(active);
      await loadSymbol(active, rows, true, selectedStrategyId, selectedCustomStrategy);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Initial load failed");
    } finally {
      setAppLoading(false);
    }
  }

  async function loadSymbol(
    symbol: string,
    rows = overview,
    includePaper = false,
    strategyId = selectedStrategyId,
    custom = strategyId === CUSTOM_STRATEGY_ID ? customStrategy : undefined
  ) {
    setSymbolLoading(true);
    setError(null);
    try {
      const requests: [Promise<SignalPoint[]>, Promise<BacktestResult>, Promise<PaperSnapshot> | null] = [
        fetchTimeseries(symbol, strategyId, custom),
        runBacktest(symbol, strategyId, custom),
        includePaper ? runPaper(rows.length ? rows.map((row) => row.sym) : DEFAULT_SYMBOLS, strategyId, custom) : null
      ];
      const [points, backtestResult, paperSnapshot] = await Promise.all(requests.map((request) => request ?? Promise.resolve(null)));
      setSelectedSymbol(symbol);
      setSeries(points as SignalPoint[]);
      setBacktest(backtestResult as BacktestResult);
      if (paperSnapshot) {
        setPaper(paperSnapshot as PaperSnapshot);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Symbol load failed");
    } finally {
      setSymbolLoading(false);
    }
  }

  async function reloadOverview(
    nextSymbol = selectedSymbol,
    strategyId = selectedStrategyId,
    custom = strategyId === CUSTOM_STRATEGY_ID ? customStrategy : undefined
  ) {
    const [rows, signalRows, strategyInfo] = await Promise.all([
      fetchOverview(strategyId, custom),
      fetchLatestSignals(strategyId, custom),
      fetchStrategy(strategyId, custom)
    ]);
    setOverview(rows);
    setLatestSignals(signalRows);
    setStrategy(strategyInfo);
    await loadSymbol(nextSymbol, rows, true, strategyId, custom);
  }

  async function refreshData() {
    setRefreshingData(true);
    setStatus("Refreshing market data for watched symbols...");
    setError(null);
    try {
      const activeSymbols = symbols.length ? symbols : DEFAULT_SYMBOLS;
      await ingest(activeSymbols);
      await reloadOverview(selectedSymbol);
      setStatus("Market data refreshed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshingData(false);
    }
  }

  async function chooseSymbol(symbol: string) {
    await loadSymbol(symbol, overview, false);
  }

  async function handleAddSymbol(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const symbol = newSymbol.trim().toUpperCase();
    if (!/^[A-Z0-9._-]{1,12}$/.test(symbol)) {
      setError("Enter a ticker using letters, numbers, '.', '_' or '-'.");
      return;
    }
    setAddingSymbol(true);
    setStatus(`Fetching daily bars and recalculating signals for ${symbol}...`);
    setError(null);
    try {
      await addSymbols([symbol]);
      setNewSymbol("");
      await reloadOverview(symbol);
      setPage("stock");
      setStatus(`${symbol} added to the watched universe.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ticker add failed");
    } finally {
      setAddingSymbol(false);
    }
  }

  async function syncUniverse() {
    setSyncingUniverse(true);
    setStatus("Re-polling the S&P 500 constituent list...");
    setError(null);
    try {
      const result = await refreshSp500Universe();
      setUniverse(result);
      setStatus(`S&P 500 universe synced: ${result.count} listings.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Universe sync failed");
    } finally {
      setSyncingUniverse(false);
    }
  }

  async function runSelectedBacktest() {
    setBacktestRunning(true);
    setStatus(`Running ${strategy?.label ?? "strategy"} backtest for ${selectedSymbol}...`);
    setError(null);
    try {
      setBacktest(await runBacktest(selectedSymbol, selectedStrategyId, selectedCustomStrategy));
      setStatus(`Backtest updated for ${selectedSymbol} using ${strategy?.label ?? "selected strategy"}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backtest failed");
    } finally {
      setBacktestRunning(false);
    }
  }

  async function changeStrategy(strategyId: string, nextCustom = customStrategy) {
    const selected = strategies.find((item) => item.id === strategyId);
    const effectiveCustom = selected?.custom ?? nextCustom;
    const custom = strategyId === CUSTOM_STRATEGY_ID ? effectiveCustom : undefined;
    if (selected?.custom) {
      setCustomStrategy(selected.custom);
    }
    setSelectedStrategyId(strategyId);
    setStatus("Switching strategy and recalculating views...");
    setError(null);
    try {
      await reloadOverview(selectedSymbol, strategyId, custom);
      setStatus(`Strategy switched to ${selected?.label ?? (strategyId === CUSTOM_STRATEGY_ID ? effectiveCustom.name : strategyId)}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Strategy switch failed");
    }
  }

  async function applyCustomStrategy() {
    await changeStrategy(CUSTOM_STRATEGY_ID, customStrategy);
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const username = loginName.trim();
    if (!username) {
      setError("Enter a local username.");
      return;
    }
    setAuthLoading(true);
    setError(null);
    try {
      const state = await login(username);
      setCurrentUser(state.user);
      setLoginName(state.user.username);
      window.localStorage.setItem("modelTradingBotUser", JSON.stringify(state.user));
      window.localStorage.setItem("sharedLocalUser", JSON.stringify(state.user));
      if (state.paper_portfolio?.snapshot) {
        setPaper(state.paper_portfolio.snapshot);
      }
      await loadApp(selectedSymbol);
      setStatus(`Signed in as ${state.user.username}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setAuthLoading(false);
    }
  }

  function logout() {
    setCurrentUser(null);
    setApiUser(null);
    window.localStorage.removeItem("modelTradingBotUser");
    window.localStorage.removeItem("sharedLocalUser");
    setStatus("Signed out. Using demo defaults until you sign in again.");
    loadApp(selectedSymbol);
  }

  async function saveCurrentStrategy() {
    setSavingStrategy(true);
    setError(null);
    try {
      const saved = await saveUserStrategy(customStrategy);
      setCustomStrategy(saved.custom ?? customStrategy);
      setStrategies(await fetchStrategies());
      await changeStrategy(saved.id, saved.custom ?? customStrategy);
      setStatus(`${saved.label} saved to ${currentUser?.username ?? "this local account"}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Strategy save failed");
    } finally {
      setSavingStrategy(false);
    }
  }

  async function resetAccount() {
    const confirmed = window.confirm("Reset this model-trading-bot account to defaults? Saved scorecards and the paper portfolio snapshot will be cleared.");
    if (!confirmed) {
      return;
    }
    setResettingAccount(true);
    setError(null);
    try {
      const state = await resetModelAccount();
      setCurrentUser(state.user);
      setCustomStrategy(DEFAULT_CUSTOM_STRATEGY);
      setSelectedStrategyId(DEFAULT_STRATEGY_ID);
      setPaper(null);
      await loadApp(DEFAULT_SYMBOLS[0]);
      setStatus(`${state.user.username}'s model-trading-bot account was reset to defaults.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Account reset failed");
    } finally {
      setResettingAccount(false);
    }
  }

  useEffect(() => {
    const stored = window.localStorage.getItem("modelTradingBotUser") || window.localStorage.getItem("sharedLocalUser");
    if (stored) {
      try {
        const user = JSON.parse(stored) as LocalUser;
        setCurrentUser(user);
        setLoginName(user.username);
        setApiUser(user.id);
        fetchUserState()
          .then((state) => {
            setCurrentUser(state.user);
            if (state.paper_portfolio?.snapshot) {
              setPaper(state.paper_portfolio.snapshot);
            }
          })
          .catch(() => {
            window.localStorage.removeItem("modelTradingBotUser");
            window.localStorage.removeItem("sharedLocalUser");
            setApiUser(null);
          });
      } catch {
        window.localStorage.removeItem("modelTradingBotUser");
        window.localStorage.removeItem("sharedLocalUser");
      }
    }
    loadApp(DEFAULT_SYMBOLS[0]);
  }, []);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">toy market-data stack</p>
          <h1>Model Trading Bot</h1>
        </div>
        <div className="toolbar">
          <AuthControl
            currentUser={currentUser}
            loginName={loginName}
            setLoginName={setLoginName}
            handleLogin={handleLogin}
            logout={logout}
            authLoading={authLoading}
          />
          <label className="selectWrap" title="Symbol">
            <BarChart3 size={16} />
            <select value={selectedSymbol} onChange={(event) => chooseSymbol(event.target.value)} disabled={symbolLoading}>
              {(symbols.length ? symbols : DEFAULT_SYMBOLS).map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <label className="selectWrap strategyWrap" title="Strategy">
            <SlidersHorizontal size={16} />
            <select value={selectedStrategyId} onChange={(event) => changeStrategy(event.target.value)} disabled={appLoading || symbolLoading}>
              {(strategies.length ? strategies : [{ id: DEFAULT_STRATEGY_ID, label: "Scorecard" } as StrategyInfo]).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <form className="tickerForm" onSubmit={handleAddSymbol}>
            <input
              aria-label="Add ticker"
              list="sp500-symbols"
              value={newSymbol}
              onChange={(event) => setNewSymbol(event.target.value.toUpperCase())}
              placeholder="Ticker"
              disabled={addingSymbol}
            />
            <datalist id="sp500-symbols">
              {universeOptions.map((symbol) => (
                <option key={symbol} value={symbol} />
              ))}
            </datalist>
            <button className="commandButton compact" type="submit" disabled={addingSymbol || !newSymbol.trim()} title="Add ticker">
              {addingSymbol ? <RefreshCw size={17} className="spin" /> : <Plus size={17} />}
              {addingSymbol ? "Adding" : "Add"}
            </button>
          </form>
          <button className="commandButton compact" type="button" onClick={refreshData} disabled={refreshingData} title="Refresh watched data">
            <RefreshCw size={17} className={refreshingData ? "spin" : ""} />
            {refreshingData ? "Refreshing" : "Refresh"}
          </button>
          <button className="commandButton compact" type="button" onClick={syncUniverse} disabled={syncingUniverse} title="Sync S&P 500 list">
            {syncingUniverse ? <RefreshCw size={17} className="spin" /> : <Database size={17} />}
            {syncingUniverse ? "Syncing" : "S&P 500"}
          </button>
        </div>
      </header>

      <nav className="pageTabs">
        {PAGES.map((item) => (
          <button key={item} type="button" className={page === item ? "activeTab" : ""} onClick={() => setPage(item)}>
            {labelPage(item)}
          </button>
        ))}
      </nav>

      {error ? <div className="alert">{error}</div> : null}
      {status ? <div className="statusLine">{status}</div> : null}

      {page === "home" ? (
        <HomePage
          appLoading={appLoading}
          latest={latest}
          overview={overview}
          universe={universe}
          strategy={strategy}
          backtest={backtest}
          paper={paper}
          chooseSymbol={(symbol) => {
            setPage("stock");
            chooseSymbol(symbol);
          }}
        />
      ) : null}

      {page === "stock" ? (
        <StockPage
          latest={latest}
          selectedSymbol={selectedSymbol}
          series={series}
          strategy={strategy}
          scoreTone={scoreTone}
        />
      ) : null}

      {page === "signals" ? (
        <SignalsPage
          catalog={catalog}
          displayedSignals={displayedSignals}
          selectedSymbol={selectedSymbol}
          symbols={symbols.length ? symbols : DEFAULT_SYMBOLS}
          series={series}
          signalFilter={signalFilter}
          setSignalFilter={setSignalFilter}
          inspectSymbol={(symbol) => {
            chooseSymbol(symbol);
          }}
          chooseSymbol={(symbol) => {
            setPage("stock");
            chooseSymbol(symbol);
          }}
        />
      ) : null}

      {page === "backtesting" ? (
        <BacktestingPage
          selectedSymbol={selectedSymbol}
          backtest={backtest}
          latest={latest}
          strategy={strategy}
          customStrategy={customStrategy}
          setCustomStrategy={setCustomStrategy}
          applyCustomStrategy={applyCustomStrategy}
          saveCurrentStrategy={saveCurrentStrategy}
          resetAccount={resetAccount}
          backtestRunning={backtestRunning}
          savingStrategy={savingStrategy}
          resettingAccount={resettingAccount}
          runSelectedBacktest={runSelectedBacktest}
        />
      ) : null}
    </main>
  );
}

function AuthControl({
  currentUser,
  loginName,
  setLoginName,
  handleLogin,
  logout,
  authLoading
}: {
  currentUser: LocalUser | null;
  loginName: string;
  setLoginName: (value: string) => void;
  handleLogin: (event: FormEvent<HTMLFormElement>) => void;
  logout: () => void;
  authLoading: boolean;
}) {
  if (currentUser) {
    return (
      <div className="authChip" data-testid="auth-chip">
        <UserRound size={16} />
        <span>{currentUser.username}</span>
        <button type="button" onClick={logout} title="Sign out">
          <LogOut size={15} />
        </button>
      </div>
    );
  }
  return (
    <form className="authForm" onSubmit={handleLogin} data-testid="auth-form">
      <input
        aria-label="Local username"
        value={loginName}
        onChange={(event) => setLoginName(event.target.value)}
        placeholder="Username"
        disabled={authLoading}
      />
      <button className="commandButton compact" type="submit" disabled={authLoading || !loginName.trim()}>
        <UserRound size={17} />
        {authLoading ? "Signing in" : "Login"}
      </button>
    </form>
  );
}

function HomePage({
  appLoading,
  latest,
  overview,
  universe,
  strategy,
  backtest,
  paper,
  chooseSymbol
}: {
  appLoading: boolean;
  latest: OverviewRow | undefined;
  overview: OverviewRow[];
  universe: UniverseResponse | null;
  strategy: StrategyInfo | null;
  backtest: BacktestResult | null;
  paper: PaperSnapshot | null;
  chooseSymbol: (symbol: string) => void;
}) {
  const leaders = [...overview].sort((a, b) => (Number(b.signal_score) || 0) - (Number(a.signal_score) || 0)).slice(0, 6);
  return (
    <>
      <section className="metricsGrid">
        <Metric icon={<Layers size={18} />} label="S&P Universe" value={universe ? compact.format(universe.count) : appLoading ? "Loading" : "-"} />
        <Metric icon={<LineIcon size={18} />} label="Watched" value={String(overview.length)} />
        <Metric icon={<Activity size={18} />} label="Top Signal" value={leaders[0]?.sym ?? "-"} tone="positive" />
        <Metric icon={<Gauge size={18} />} label="Top Score" value={fmt(leaders[0]?.signal_score)} tone="positive" />
        <Metric icon={<Wallet size={18} />} label="Paper Equity" value={paper ? money.format(paper.equity) : "-"} tone="positive" />
        <Metric icon={<Server size={18} />} label="Strategy" value={strategy?.label ?? "-"} />
      </section>

      <SystemLearningPanel
        latest={latest}
        leaders={leaders}
        overview={overview}
        universe={universe}
        strategy={strategy}
        backtest={backtest}
        paper={paper}
        chooseSymbol={chooseSymbol}
      />

      <section className="homeGrid">
        <div className="panel">
          <div className="panelHeader">
            <h2>Market Preview</h2>
            <span>{latest?.sym ?? "-"}</span>
          </div>
          <PreviewTable rows={leaders} chooseSymbol={chooseSymbol} />
        </div>
        <div className="panel">
          <div className="panelHeader">
            <h2>Backtest Preview</h2>
            <span>{backtest ? pct.format(backtest.metrics.total_return ?? 0) : "-"}</span>
          </div>
          <EquityChart backtest={backtest} compactMode />
        </div>
        <div className="panel">
          <div className="panelHeader">
            <h2>Universe</h2>
            <span>{universe?.as_of ? new Date(universe.as_of).toLocaleDateString() : "-"}</span>
          </div>
          <div className="universeSummary">
            <strong>{universe ? `${universe.count} S&P 500 listings cached` : "No S&P cache yet"}</strong>
            <p>The backend periodically re-polls the constituent table and uses it as the ticker search universe. Market data is still fetched only for watched symbols to keep the free data providers happy.</p>
          </div>
        </div>
      </section>
    </>
  );
}

function SystemLearningPanel({
  latest,
  leaders,
  overview,
  universe,
  strategy,
  backtest,
  paper,
  chooseSymbol
}: {
  latest: OverviewRow | undefined;
  leaders: OverviewRow[];
  overview: OverviewRow[];
  universe: UniverseResponse | null;
  strategy: StrategyInfo | null;
  backtest: BacktestResult | null;
  paper: PaperSnapshot | null;
  chooseSymbol: (symbol: string) => void;
}) {
  const [activeLesson, setActiveLesson] = useState<SystemLessonId>("data");
  const lesson = SYSTEM_LESSON_STEPS.find((item) => item.id === activeLesson) ?? SYSTEM_LESSON_STEPS[0];
  const readout = buildLessonReadout(activeLesson, { latest, leaders, overview, universe, strategy, backtest, paper });
  const topSymbol = leaders[0]?.sym;

  return (
    <section className="panel learningPanel" data-testid="system-learning-panel">
      <div className="panelHeader">
        <div>
          <h2>Trading System Walkthrough</h2>
          <span>{lesson.label}</span>
        </div>
        {topSymbol ? (
          <button className="commandButton compact" type="button" onClick={() => chooseSymbol(topSymbol)}>
            Inspect {topSymbol}
          </button>
        ) : null}
      </div>
      <div className="lessonShell">
        <div className="lessonRail" role="tablist" aria-label="Trading system stages">
          {SYSTEM_LESSON_STEPS.map((step, index) => (
            <button
              key={step.id}
              type="button"
              role="tab"
              aria-selected={activeLesson === step.id}
              className={activeLesson === step.id ? "activeLesson" : ""}
              onClick={() => setActiveLesson(step.id)}
            >
              <span>{index + 1}</span>
              {step.label}
            </button>
          ))}
        </div>
        <div className="lessonBody">
          <div className="lessonCard emphasis">
            <span>Principle</span>
            <strong>{lesson.principle}</strong>
          </div>
          <div className="lessonCard">
            <span>Current readout</span>
            <strong>{readout.primary}</strong>
            <p>{readout.secondary}</p>
          </div>
          <div className="lessonCard">
            <span>Mechanism</span>
            <p>{lesson.mechanism}</p>
          </div>
          <div className="lessonCard">
            <span>Risk Lens</span>
            <p>{lesson.watch}</p>
          </div>
        </div>
      </div>
    </section>
  );
}

function StockPage({
  latest,
  selectedSymbol,
  series,
  strategy,
  scoreTone
}: {
  latest: OverviewRow | undefined;
  selectedSymbol: string;
  series: SignalPoint[];
  strategy: StrategyInfo | null;
  scoreTone: string;
}) {
  return (
    <>
      <section className="metricsGrid">
        <Metric icon={<LineIcon size={18} />} label="Close" value={latest ? money.format(latest.close) : "-"} />
        <Metric
          icon={<Activity size={18} />}
          label="Signal"
          value={latest ? latest.trade_signal : "-"}
          tone={latest?.trade_signal === "BUY" ? "positive" : latest?.trade_signal === "SELL" ? "negative" : "neutral"}
        />
        <Metric icon={<Gauge size={18} />} label="Score" value={fmt(latest?.signal_score)} tone={scoreTone} />
        <Metric icon={<Server size={18} />} label="RSI 14" value={fmt(latest?.rsi_14)} />
        <Metric icon={<Database size={18} />} label="ADX" value={fmt(latest?.adx_14)} />
        <Metric icon={<Database size={18} />} label="ATR %" value={pctOrDash(latest?.atr_pct)} />
      </section>

      <section className="workspace">
        <div className="panel pricePanel">
          <div className="panelHeader">
            <h2>{selectedSymbol} Price</h2>
            <span>{latest ? pct.format(latest.period_return) : "-"}</span>
          </div>
          <PriceChart series={series} latest={latest} />
        </div>
        <IndicatorChart title="MACD" value={fmt(latest?.macd_hist)}>
          <ComposedChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#e6e8ec" vertical={false} />
            <XAxis dataKey="date" hide />
            <YAxis width={48} tickLine={false} axisLine={false} />
            <Tooltip formatter={(value) => (typeof value === "number" ? value.toFixed(3) : value)} />
            <ReferenceLine y={0} stroke="#9ca3af" />
            <Bar dataKey="macd_hist" fill="#9ca3af" barSize={3} />
            <Line type="monotone" dataKey="macd" stroke="#0f766e" dot={false} />
            <Line type="monotone" dataKey="macd_signal" stroke="#b45309" dot={false} />
          </ComposedChart>
        </IndicatorChart>
        <IndicatorChart title="RSI" value={fmt(latest?.rsi_14)}>
          <OscillatorChart data={series} lineKey="rsi_14" high={70} low={30} stroke="#2563eb" />
        </IndicatorChart>
      </section>

      <section className="analysisGrid">
        <AlgorithmPanel latest={latest} strategy={strategy} />
        <div className="panel">
          <div className="panelHeader">
            <h2>Momentum + Volatility</h2>
            <span>{fmt(latest?.stoch_k)}</span>
          </div>
          <div className="chartBox compact">
            <ResponsiveContainer>
              <OscillatorChart data={series} lineKey="stoch_k" secondaryKey="stoch_d" high={80} low={20} stroke="#7c3aed" />
            </ResponsiveContainer>
          </div>
          <div className="metricStrip slim">
            <SmallMetric label="BB Width" value={pctOrDash(latest?.bb_width)} />
            <SmallMetric label="20D Vol" value={pctOrDash(latest?.realized_vol_20)} />
            <SmallMetric label="12-1 Mom" value={pctOrDash(latest?.momentum_252_skip_21)} />
            <SmallMetric label="52W High" value={pctOrDash(latest?.distance_52w_high)} />
          </div>
        </div>
      </section>
    </>
  );
}

function SignalsPage({
  catalog,
  displayedSignals,
  selectedSymbol,
  symbols,
  series,
  signalFilter,
  setSignalFilter,
  inspectSymbol,
  chooseSymbol
}: {
  catalog: SignalCatalogItem[];
  displayedSignals: OverviewRow[];
  selectedSymbol: string;
  symbols: string[];
  series: SignalPoint[];
  signalFilter: string;
  setSignalFilter: (value: string) => void;
  inspectSymbol: (symbol: string) => void;
  chooseSymbol: (symbol: string) => void;
}) {
  const [expandedSignal, setExpandedSignal] = useState<string | null>(null);
  const groups = useMemo(() => {
    return catalog.reduce<Record<string, SignalCatalogItem[]>>((accumulator, item) => {
      accumulator[item.group] = [...(accumulator[item.group] ?? []), item];
      return accumulator;
    }, {});
  }, [catalog]);

  return (
    <section className="signalsLayout">
      <SignalTrendExplorer
        catalog={catalog}
        selectedSymbol={selectedSymbol}
        symbols={symbols}
        series={series}
        inspectSymbol={inspectSymbol}
      />

      <div className="panel">
        <div className="panelHeader">
          <h2>Signal Catalog</h2>
          <span>{catalog.length}</span>
        </div>
        <div className="catalogGrid">
          {Object.entries(groups).map(([group, items]) => (
            <div className="catalogGroup" key={group}>
              <h3>{titleCase(group)}</h3>
              {items.map((item) => (
                <div className="catalogItem" key={item.key}>
                  <button
                    className="catalogItemButton"
                    type="button"
                    aria-expanded={expandedSignal === item.key}
                    onClick={() => setExpandedSignal(expandedSignal === item.key ? null : item.key)}
                  >
                    <strong>{item.label}</strong>
                    {expandedSignal === item.key ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                  </button>
                  {expandedSignal === item.key ? (
                    <div className="catalogDetails">
                      <p>{item.description}</p>
                      {item.formula ? <span>{item.formula}</span> : null}
                      {item.interpretation ? <span>{item.interpretation}</span> : null}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="panel signalMatrixPanel">
        <div className="panelHeader matrixHeader">
          <h2>Latest Signal Matrix</h2>
          <label className="searchBox">
            <Search size={15} />
            <input value={signalFilter} onChange={(event) => setSignalFilter(event.target.value)} placeholder="Filter symbols or reasons" />
          </label>
        </div>
        <div className="tableWrap wide">
          <table>
            <thead>
              <tr>
                <th>Sym</th>
                <th>Signal</th>
                {SIGNAL_MATRIX_COLUMNS.map(([key, label]) => (
                  <th key={key}>{label}</th>
                ))}
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {displayedSignals.map((row) => (
                <tr key={row.sym} onClick={() => chooseSymbol(row.sym)}>
                  <td>{row.sym}</td>
                  <td>
                    <span className={`pill ${String(row.trade_signal).toLowerCase()}`}>{row.trade_signal}</span>
                  </td>
                  {SIGNAL_MATRIX_COLUMNS.map(([key]) => (
                    <td key={key}>{formatSignalValue(key, row[key])}</td>
                  ))}
                  <td className="reasonCell">{row.signal_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function SignalTrendExplorer({
  catalog,
  selectedSymbol,
  symbols,
  series,
  inspectSymbol
}: {
  catalog: SignalCatalogItem[];
  selectedSymbol: string;
  symbols: string[];
  series: SignalPoint[];
  inspectSymbol: (symbol: string) => void;
}) {
  const [selectedKeys, setSelectedKeys] = useState<string[]>(["signal_score", "trend_score", "momentum_score", "rsi_14", "macd_hist"]);
  const [scale, setScale] = useState<SignalTrendScale>("normalized");
  const [showPosition, setShowPosition] = useState(true);
  const options = useMemo(() => buildSignalTrendOptions(catalog), [catalog]);
  const colorByKey = useMemo(
    () => new Map(options.map((option, index) => [option.key, SIGNAL_TREND_COLORS[index % SIGNAL_TREND_COLORS.length]])),
    [options]
  );
  const selectedOptions = selectedKeys
    .map((key) => options.find((option) => option.key === key))
    .filter((option): option is SignalTrendOption => Boolean(option));
  const chartData = useMemo(() => buildSignalTrendData(series, selectedKeys, scale), [series, selectedKeys, scale]);
  const legendHeight = selectedOptions.length > 20 ? 84 : selectedOptions.length > 10 ? 58 : 32;

  function toggleSignal(key: string) {
    setSelectedKeys((current) => {
      if (current.includes(key)) {
        return current.length === 1 ? current : current.filter((item) => item !== key);
      }
      return [...current, key];
    });
  }

  function applyPreset(name: string) {
    if (name === "All") {
      setSelectedKeys(options.map((option) => option.key));
      return;
    }
    const keys = (SIGNAL_TREND_PRESETS[name] ?? []).filter((key) => options.some((option) => option.key === key));
    if (keys.length) {
      setSelectedKeys(keys);
    }
  }

  return (
    <div className="panel signalTrendPanel" data-testid="signal-trend-explorer">
      <div className="panelHeader matrixHeader">
        <div>
          <h2>Signal Trend Explorer</h2>
          <span>{selectedSymbol}</span>
        </div>
        <div className="signalTrendControls">
          <label className="selectWrap compactSelect" title="Trend symbol">
            <BarChart3 size={15} />
            <select value={selectedSymbol} onChange={(event) => inspectSymbol(event.target.value)}>
              {symbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <div className="segmentedControl">
            <button type="button" className={scale === "normalized" ? "activeSegment" : ""} onClick={() => setScale("normalized")}>
              Normalized
            </button>
            <button type="button" className={scale === "raw" ? "activeSegment" : ""} onClick={() => setScale("raw")}>
              Raw
            </button>
          </div>
          <label className="inlineCheck">
            <input type="checkbox" checked={showPosition} onChange={(event) => setShowPosition(event.target.checked)} />
            <span>Position</span>
          </label>
        </div>
      </div>

      <div className="presetRow">
        {[...Object.keys(SIGNAL_TREND_PRESETS), "All"].map((name) => (
          <button key={name} type="button" onClick={() => applyPreset(name)}>
            {name}
          </button>
        ))}
      </div>

      <div className="signalPicker">
        {options.map((option) => {
          const active = selectedKeys.includes(option.key);
          return (
            <button
              key={option.key}
              type="button"
              className={active ? "activeSignalChip" : ""}
              onClick={() => toggleSignal(option.key)}
              title={option.group}
            >
              <span style={{ backgroundColor: colorByKey.get(option.key) ?? "#111827" }} />
              {option.label}
            </button>
          );
        })}
      </div>

      <div className="chartBox signalTrendChart" data-testid="signal-trend-chart">
        <ResponsiveContainer>
          <LineChart data={chartData} margin={{ top: 12, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#e6e8ec" vertical={false} />
            <XAxis dataKey="date" minTickGap={32} tickLine={false} axisLine={false} />
            <YAxis yAxisId="main" width={64} domain={scale === "normalized" ? [0, 100] : ["auto", "auto"]} tickLine={false} axisLine={false} />
            <YAxis yAxisId="position" orientation="right" hide domain={[0, 8]} />
            <Tooltip content={<SignalTrendTooltip scale={scale} options={selectedOptions} />} />
            <Legend verticalAlign="top" height={legendHeight} />
            <ReferenceLine yAxisId="main" y={scale === "normalized" ? 50 : 0} stroke="#cbd5e1" strokeDasharray="4 4" />
            {selectedOptions.map((option) => (
              <Line
                key={option.key}
                yAxisId="main"
                type="monotone"
                dataKey={option.key}
                name={option.label}
                stroke={colorByKey.get(option.key) ?? "#111827"}
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            ))}
            {showPosition ? (
              <Line
                yAxisId="position"
                type="stepAfter"
                dataKey="position"
                name="Position"
                stroke="#10b981"
                strokeWidth={1.6}
                dot={false}
                isAnimationActive={false}
              />
            ) : null}
            <Brush dataKey="date" height={28} stroke="#0f766e" travellerWidth={10} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="trendSummary">
        <span>{chartData.length} observations</span>
        <span>{selectedOptions.length} signals selected</span>
        <span>{scale === "normalized" ? "Each line is scaled 0-100 for comparison" : "Raw indicator units"}</span>
      </div>
    </div>
  );
}

function BacktestingPage({
  selectedSymbol,
  backtest,
  latest,
  strategy,
  customStrategy,
  setCustomStrategy,
  applyCustomStrategy,
  saveCurrentStrategy,
  resetAccount,
  backtestRunning,
  savingStrategy,
  resettingAccount,
  runSelectedBacktest
}: {
  selectedSymbol: string;
  backtest: BacktestResult | null;
  latest: OverviewRow | undefined;
  strategy: StrategyInfo | null;
  customStrategy: CustomStrategyConfig;
  setCustomStrategy: (value: CustomStrategyConfig) => void;
  applyCustomStrategy: () => void;
  saveCurrentStrategy: () => void;
  resetAccount: () => void;
  backtestRunning: boolean;
  savingStrategy: boolean;
  resettingAccount: boolean;
  runSelectedBacktest: () => void;
}) {
  return (
    <section className="backtestLayout">
      <div className="panel backtestHero">
        <div className="panelHeader">
          <h2>{selectedSymbol} Backtest</h2>
          <button className="commandButton compact" type="button" onClick={runSelectedBacktest} disabled={backtestRunning}>
            {backtestRunning ? <RefreshCw size={17} className="spin" /> : <Play size={17} />}
            Run Backtest
          </button>
        </div>
        <EquityChart backtest={backtest} />
        <div className="metricStrip">
          <SmallMetric label="Return" value={backtest ? pct.format(backtest.metrics.total_return ?? 0) : "-"} />
          <SmallMetric label="Benchmark" value={backtest ? pct.format(backtest.metrics.benchmark_return ?? 0) : "-"} />
          <SmallMetric label="Sharpe" value={fmt(backtest?.metrics.sharpe)} />
          <SmallMetric label="Drawdown" value={pct.format(backtest?.metrics.max_drawdown ?? 0)} />
        </div>
      </div>

      <BacktestAnatomyPanel backtest={backtest} />

      <div className="panel">
        <div className="panelHeader">
          <h2>Trade Log</h2>
          <span>{backtest?.trades.length ?? 0}</span>
        </div>
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Side</th>
                <th>Price</th>
                <th>Equity</th>
              </tr>
            </thead>
            <tbody>
              {(backtest?.trades ?? []).slice(-20).map((trade) => (
                <tr key={`${trade.date}-${trade.side}-${trade.price}`}>
                  <td>{trade.date}</td>
                  <td>{trade.side}</td>
                  <td>{money.format(trade.price)}</td>
                  <td>{money.format(trade.equity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <StrategyControlPanel
        strategy={strategy}
        customStrategy={customStrategy}
        setCustomStrategy={setCustomStrategy}
        applyCustomStrategy={applyCustomStrategy}
        saveCurrentStrategy={saveCurrentStrategy}
        resetAccount={resetAccount}
        disabled={backtestRunning}
        savingStrategy={savingStrategy}
        resettingAccount={resettingAccount}
      />

      <div className="panel">
        <div className="panelHeader">
          <h2>Current Rule State</h2>
          <span>{fmt(latest?.signal_score)}</span>
        </div>
        <div className="reasonLine">{latest?.signal_reason ?? "-"}</div>
      </div>
    </section>
  );
}

function BacktestAnatomyPanel({ backtest }: { backtest: BacktestResult | null }) {
  const trades = backtest?.trades ?? [];
  const [tradeIndex, setTradeIndex] = useState(0);
  const safeIndex = trades.length ? Math.min(tradeIndex, trades.length - 1) : 0;
  const trade = trades[safeIndex];
  const curvePoint = backtest?.equity_curve.find((point) => point.date === trade?.date);
  const worstDrawdown = (backtest?.equity_curve ?? []).reduce(
    (worst, point) => (point.drawdown < worst.drawdown ? point : worst),
    { date: "-", drawdown: 0, equity: 0, benchmark_equity: 0, position: 0 }
  );

  useEffect(() => {
    setTradeIndex(Math.max(0, trades.length - 1));
  }, [backtest?.symbol, trades.length]);

  return (
    <div className="panel anatomyPanel" data-testid="backtest-anatomy">
      <div className="panelHeader">
        <h2>Trade Anatomy</h2>
        <span>{trades.length ? `${safeIndex + 1} / ${trades.length}` : "No trades"}</span>
      </div>
      {trade ? (
        <>
          <div className="tradeStepper">
            <button type="button" onClick={() => setTradeIndex(Math.max(0, safeIndex - 1))} disabled={safeIndex === 0}>
              Previous
            </button>
            <button type="button" onClick={() => setTradeIndex(Math.min(trades.length - 1, safeIndex + 1))} disabled={safeIndex >= trades.length - 1}>
              Next
            </button>
          </div>
          <div className="tradeFocus">
            <strong>
              {trade.side} {trade.sym}
            </strong>
            <span>{trade.date}</span>
            <span>{money.format(trade.price)}</span>
          </div>
          <div className="anatomyFlow">
            <div>
              <span>1</span>
              <strong>Signal Snapshot</strong>
              <p>The rule state is read after the bar closes.</p>
            </div>
            <div>
              <span>2</span>
              <strong>Next-Bar Position</strong>
              <p>The simulated trade changes exposure on the following observation.</p>
            </div>
            <div>
              <span>3</span>
              <strong>Cost Haircut</strong>
              <p>Fees and slippage reduce the theoretical fill.</p>
            </div>
            <div>
              <span>4</span>
              <strong>Equity Mark</strong>
              <p>Cash, position, and benchmark equity are reconciled.</p>
            </div>
          </div>
          <div className="metricStrip slim">
            <SmallMetric label="Trade Equity" value={money.format(trade.equity)} />
            <SmallMetric label="Curve Equity" value={curvePoint ? money.format(curvePoint.equity) : "-"} />
            <SmallMetric label="Position" value={trade.position ? "Long" : "Cash"} />
            <SmallMetric label="Worst DD" value={`${pct.format(worstDrawdown.drawdown)} on ${worstDrawdown.date}`} />
          </div>
        </>
      ) : (
        <div className="emptyState">
          <strong>No trade events yet</strong>
          <p>The selected strategy stayed in one stance for the available history.</p>
        </div>
      )}
    </div>
  );
}

function StrategyControlPanel({
  strategy,
  customStrategy,
  setCustomStrategy,
  applyCustomStrategy,
  saveCurrentStrategy,
  resetAccount,
  disabled,
  savingStrategy,
  resettingAccount
}: {
  strategy: StrategyInfo | null;
  customStrategy: CustomStrategyConfig;
  setCustomStrategy: (value: CustomStrategyConfig) => void;
  applyCustomStrategy: () => void;
  saveCurrentStrategy: () => void;
  resetAccount: () => void;
  disabled: boolean;
  savingStrategy: boolean;
  resettingAccount: boolean;
}) {
  function updateNumber(
    key: "min_signal_score" | "max_rsi" | "min_rsi" | "min_adx" | "min_momentum_score",
    value: string
  ) {
    const fallback = key === "min_signal_score" ? DEFAULT_CUSTOM_STRATEGY.min_signal_score : key === "max_rsi" ? DEFAULT_CUSTOM_STRATEGY.max_rsi : null;
    setCustomStrategy({ ...customStrategy, [key]: value === "" ? fallback : Number(value) } as CustomStrategyConfig);
  }

  return (
    <div className="panel strategyPanel">
      <div className="panelHeader">
        <h2>Strategy</h2>
        <span>{strategy?.label ?? "-"}</span>
      </div>
      <div className="strategySummary">
        <strong>{strategy?.description ?? "-"}</strong>
        <p>{strategy?.position_rule ?? "-"}</p>
      </div>
      <div className="accountActions">
        <button className="commandButton compact" type="button" onClick={saveCurrentStrategy} disabled={savingStrategy || strategy?.id !== CUSTOM_STRATEGY_ID}>
          {savingStrategy ? <RefreshCw size={17} className="spin" /> : <Database size={17} />}
          Save Scorecard
        </button>
        <button className="commandButton compact danger" type="button" onClick={resetAccount} disabled={resettingAccount}>
          {resettingAccount ? <RefreshCw size={17} className="spin" /> : <RefreshCw size={17} />}
          Reset Account
        </button>
      </div>
      {strategy?.id === CUSTOM_STRATEGY_ID ? (
        <form
          className="customStrategyForm"
          onSubmit={(event) => {
            event.preventDefault();
            applyCustomStrategy();
          }}
        >
          <label>
            <span>Name</span>
            <input value={customStrategy.name} onChange={(event) => setCustomStrategy({ ...customStrategy, name: event.target.value })} />
          </label>
          <label>
            <span>Min Score</span>
            <input inputMode="decimal" value={customStrategy.min_signal_score} onChange={(event) => updateNumber("min_signal_score", event.target.value)} />
          </label>
          <label>
            <span>Max RSI</span>
            <input inputMode="decimal" value={customStrategy.max_rsi} onChange={(event) => updateNumber("max_rsi", event.target.value)} />
          </label>
          <label>
            <span>Min RSI</span>
            <input inputMode="decimal" value={customStrategy.min_rsi ?? ""} onChange={(event) => updateNumber("min_rsi", event.target.value)} />
          </label>
          <label>
            <span>Min ADX</span>
            <input inputMode="decimal" value={customStrategy.min_adx ?? ""} onChange={(event) => updateNumber("min_adx", event.target.value)} />
          </label>
          <label>
            <span>Min Momentum</span>
            <input
              inputMode="decimal"
              value={customStrategy.min_momentum_score ?? ""}
              onChange={(event) => updateNumber("min_momentum_score", event.target.value)}
            />
          </label>
          <label className="checkRow">
            <input
              type="checkbox"
              checked={customStrategy.require_above_sma20}
              onChange={(event) => setCustomStrategy({ ...customStrategy, require_above_sma20: event.target.checked })}
            />
            <span>Close above SMA 20</span>
          </label>
          <label className="checkRow">
            <input
              type="checkbox"
              checked={customStrategy.require_positive_macd}
              onChange={(event) => setCustomStrategy({ ...customStrategy, require_positive_macd: event.target.checked })}
            />
            <span>MACD positive</span>
          </label>
          <button className="commandButton compact" type="submit" disabled={disabled}>
            <SlidersHorizontal size={17} />
            Apply Custom
          </button>
        </form>
      ) : null}
    </div>
  );
}

function PriceChart({ series, latest }: { series: SignalPoint[]; latest: OverviewRow | undefined }) {
  const [range, setRange] = useState<PriceRangeLabel>("1Y");
  const [activeLayers, setActiveLayers] = useState<PriceLayerKey[]>(["close", "sma20", "sma50", "sma200", "position"]);
  const activeLayerSet = useMemo(() => new Set(activeLayers), [activeLayers]);
  const rangeDays = PRICE_RANGE_OPTIONS.find(([label]) => label === range)?.[1] ?? null;
  const chartData = useMemo(() => (rangeDays == null ? series : series.slice(-rangeDays)), [rangeDays, series]);
  const priceDomain = useMemo(() => buildPriceDomain(chartData, activeLayerSet), [activeLayerSet, chartData]);
  const latestPoint = chartData[chartData.length - 1];
  const trendState =
    latest?.close != null && latest?.sma_20 != null ? (latest.close >= latest.sma_20 ? "Above SMA 20" : "Below SMA 20") : "Trend pending";
  const momentumState =
    typeof latest?.rsi_14 === "number" ? (latest.rsi_14 >= 70 ? "RSI overbought" : latest.rsi_14 <= 30 ? "RSI oversold" : "RSI neutral") : "RSI pending";
  const positionState = latestPoint?.position ? "Long exposure" : "Cash stance";

  function toggleLayer(key: PriceLayerKey) {
    setActiveLayers((current) => {
      if (current.includes(key)) {
        return current.length === 1 ? current : current.filter((item) => item !== key);
      }
      return [...current, key];
    });
  }

  return (
    <>
      <div className="chartControlBar" data-testid="price-chart-controls">
        <div className="segmentedControl">
          {PRICE_RANGE_OPTIONS.map(([label]) => (
            <button key={label} type="button" className={range === label ? "activeSegment" : ""} onClick={() => setRange(label)}>
              {label}
            </button>
          ))}
        </div>
        <div className="layerToggles">
          {PRICE_LAYER_CONFIG.map((layer) => (
            <button
              key={layer.key}
              type="button"
              className={activeLayerSet.has(layer.key) ? "activeLayer" : ""}
              onClick={() => toggleLayer(layer.key)}
            >
              <span style={{ backgroundColor: layer.color }} />
              {layer.label}
            </button>
          ))}
        </div>
      </div>
      <div className="chartBox tall interactiveChart" data-testid="price-chart">
        <ResponsiveContainer>
          <ComposedChart data={chartData} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#e6e8ec" vertical={false} />
            <XAxis dataKey="date" minTickGap={32} tickLine={false} axisLine={false} />
            <YAxis width={72} tickFormatter={(value) => money.format(Number(value))} tickLine={false} axisLine={false} domain={priceDomain} />
            <YAxis yAxisId="position" orientation="right" hide domain={[0, 8]} />
            <Tooltip content={<PriceTooltip />} />
            <Legend verticalAlign="top" height={32} />
            {activeLayerSet.has("close") ? <Line type="monotone" dataKey="close" name="Close" stroke="#111827" strokeWidth={2.2} dot={false} isAnimationActive={false} /> : null}
            {activeLayerSet.has("sma20") ? <Line type="monotone" dataKey="sma_20" name="SMA 20" stroke="#0f766e" strokeWidth={1.8} dot={false} isAnimationActive={false} /> : null}
            {activeLayerSet.has("sma50") ? <Line type="monotone" dataKey="sma_50" name="SMA 50" stroke="#d97706" strokeWidth={1.8} dot={false} isAnimationActive={false} /> : null}
            {activeLayerSet.has("sma200") ? <Line type="monotone" dataKey="sma_200" name="SMA 200" stroke="#4f46e5" strokeWidth={1.5} dot={false} isAnimationActive={false} /> : null}
            {activeLayerSet.has("bollinger") ? (
              <>
                <Line type="monotone" dataKey="bb_upper" name="Bollinger Upper" stroke="#be123c" strokeWidth={1} dot={false} strokeDasharray="4 4" isAnimationActive={false} />
                <Line type="monotone" dataKey="bb_lower" name="Bollinger Lower" stroke="#be123c" strokeWidth={1} dot={false} strokeDasharray="4 4" isAnimationActive={false} />
              </>
            ) : null}
            {activeLayerSet.has("keltner") ? (
              <>
                <Line type="monotone" dataKey="keltner_upper" name="Keltner Upper" stroke="#64748b" strokeWidth={1} dot={false} strokeDasharray="2 3" isAnimationActive={false} />
                <Line type="monotone" dataKey="keltner_lower" name="Keltner Lower" stroke="#64748b" strokeWidth={1} dot={false} strokeDasharray="2 3" isAnimationActive={false} />
              </>
            ) : null}
            {activeLayerSet.has("position") ? (
              <Line yAxisId="position" type="stepAfter" dataKey="position" name="Position" stroke="#10b981" strokeWidth={1.6} dot={false} isAnimationActive={false} />
            ) : null}
            <Brush dataKey="date" height={28} stroke="#0f766e" travellerWidth={10} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="chartPrinciples">
        <SmallMetric label="Trend Filter" value={trendState} />
        <SmallMetric label="Momentum State" value={momentumState} />
        <SmallMetric label="Model Stance" value={positionState} />
        <SmallMetric label="Visible Bars" value={compact.format(chartData.length)} />
      </div>
    </>
  );
}

function IndicatorChart({ title, value, children }: { title: string; value: string; children: ReactElement }) {
  return (
    <div className="panel">
      <div className="panelHeader">
        <h2>{title}</h2>
        <span>{value}</span>
      </div>
      <div className="chartBox">
        <ResponsiveContainer>{children}</ResponsiveContainer>
      </div>
    </div>
  );
}

function OscillatorChart({
  data,
  lineKey,
  secondaryKey,
  high,
  low,
  stroke,
  width,
  height
}: {
  data: SignalPoint[];
  lineKey: string;
  secondaryKey?: string;
  high: number;
  low: number;
  stroke: string;
  width?: number;
  height?: number;
}) {
  return (
    <LineChart width={width} height={height} data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
      <CartesianGrid stroke="#e6e8ec" vertical={false} />
      <XAxis dataKey="date" hide />
      <YAxis width={42} domain={[0, 100]} tickLine={false} axisLine={false} />
      <Tooltip formatter={(value) => (typeof value === "number" ? value.toFixed(1) : value)} />
      <ReferenceLine y={high} stroke="#dc2626" strokeDasharray="4 4" />
      <ReferenceLine y={low} stroke="#16a34a" strokeDasharray="4 4" />
      <Line type="monotone" dataKey={lineKey} stroke={stroke} strokeWidth={2} dot={false} />
      {secondaryKey ? <Line type="monotone" dataKey={secondaryKey} stroke="#64748b" strokeWidth={1.7} dot={false} /> : null}
    </LineChart>
  );
}

function AlgorithmPanel({ latest, strategy }: { latest: OverviewRow | undefined; strategy: StrategyInfo | null }) {
  return (
    <div className="panel algorithmPanel">
      <div className="panelHeader">
        <h2>Algorithm</h2>
        <span>{latest?.signal_score == null ? "-" : `${latest.signal_score.toFixed(0)} score`}</span>
      </div>
      <div className="scoreRows">
        {(strategy?.components ?? []).map((component) => {
          const raw = latest?.[component.key];
          const value = typeof raw === "number" ? raw : 0;
          const width = scoreWidth(value, component.range);
          return (
            <div className="scoreRow" key={component.key}>
              <div className="scoreLabel">
                <strong>{component.label}</strong>
                <span>{value.toFixed(0)}</span>
              </div>
              <div className="scoreTrack">
                <span style={{ width: `${width}%` }} />
              </div>
              <small>{component.signals.join(" + ")}</small>
            </div>
          );
        })}
      </div>
      <div className="reasonLine">{latest?.signal_reason ?? strategy?.position_rule ?? "-"}</div>
    </div>
  );
}

function EquityChart({ backtest, compactMode = false }: { backtest: BacktestResult | null; compactMode?: boolean }) {
  const [activeLayers, setActiveLayers] = useState<EquityLayerKey[]>(compactMode ? ["equity", "benchmark"] : ["equity", "benchmark", "drawdown"]);
  const activeLayerSet = useMemo(() => new Set(activeLayers), [activeLayers]);

  function toggleLayer(key: EquityLayerKey) {
    setActiveLayers((current) => {
      if (current.includes(key)) {
        return current.length === 1 ? current : current.filter((item) => item !== key);
      }
      return [...current, key];
    });
  }

  return (
    <>
      {!compactMode ? (
        <div className="chartControlBar">
          <div className="layerToggles">
            {EQUITY_LAYER_CONFIG.map((layer) => (
              <button
                key={layer.key}
                type="button"
                className={activeLayerSet.has(layer.key) ? "activeLayer" : ""}
                onClick={() => toggleLayer(layer.key)}
              >
                <span style={{ backgroundColor: layer.color }} />
                {layer.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <div className={`chartBox ${compactMode ? "" : "tall interactiveChart"}`} data-testid={compactMode ? undefined : "equity-chart"}>
        <ResponsiveContainer>
          <LineChart data={backtest?.equity_curve ?? []} margin={{ top: 8, right: 8, bottom: compactMode ? 0 : 2, left: 0 }}>
            <CartesianGrid stroke="#e6e8ec" vertical={false} />
            <XAxis dataKey="date" minTickGap={32} tickLine={false} axisLine={false} />
            <YAxis yAxisId="equity" width={70} tickFormatter={(value) => compact.format(value)} tickLine={false} axisLine={false} />
            {activeLayerSet.has("drawdown") ? <YAxis yAxisId="drawdown" orientation="right" width={54} tickFormatter={(value) => pct.format(Number(value))} tickLine={false} axisLine={false} /> : null}
            <YAxis yAxisId="position" orientation="right" hide domain={[0, 8]} />
            <Tooltip
              formatter={(value, name) => {
                if (name === "Drawdown") return pct.format(Number(value));
                if (name === "Position") return Number(value) ? "Long" : "Cash";
                return typeof value === "number" ? money.format(value) : value;
              }}
            />
            {!compactMode ? <Legend verticalAlign="top" height={30} /> : null}
            {activeLayerSet.has("equity") ? <Line yAxisId="equity" type="monotone" dataKey="equity" name="Strategy" stroke="#0f766e" strokeWidth={2} dot={false} isAnimationActive={false} /> : null}
            {activeLayerSet.has("benchmark") ? (
              <Line yAxisId="equity" type="monotone" dataKey="benchmark_equity" name="Benchmark" stroke="#64748b" strokeWidth={1.7} dot={false} isAnimationActive={false} />
            ) : null}
            {activeLayerSet.has("drawdown") ? <Line yAxisId="drawdown" type="monotone" dataKey="drawdown" name="Drawdown" stroke="#dc2626" strokeWidth={1.4} dot={false} isAnimationActive={false} /> : null}
            {activeLayerSet.has("position") ? <Line yAxisId="position" type="stepAfter" dataKey="position" name="Position" stroke="#10b981" strokeWidth={1.4} dot={false} isAnimationActive={false} /> : null}
            {!compactMode ? <Brush dataKey="date" height={28} stroke="#0f766e" travellerWidth={10} /> : null}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

function PreviewTable({ rows, chooseSymbol }: { rows: OverviewRow[]; chooseSymbol: (symbol: string) => void }) {
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Sym</th>
            <th>Signal</th>
            <th>Score</th>
            <th>Close</th>
            <th>Return</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.sym} onClick={() => chooseSymbol(row.sym)}>
              <td>{row.sym}</td>
              <td>
                <span className={`pill ${String(row.trade_signal).toLowerCase()}`}>{row.trade_signal}</span>
              </td>
              <td>{fmt(row.signal_score)}</td>
              <td>{money.format(row.close)}</td>
              <td className={row.period_return >= 0 ? "green" : "red"}>{pct.format(row.period_return)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Metric({ icon, label, value, tone }: { icon: ReactNode; label: string; value: string; tone?: string }) {
  return (
    <article className={`metric ${tone ?? ""}`}>
      <div className="metricIcon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

function SmallMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="smallMetric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PriceTooltip({
  active,
  label,
  payload
}: {
  active?: boolean;
  label?: string;
  payload?: Array<{ color?: string; dataKey?: string; name?: string; value?: number; payload?: SignalPoint }>;
}) {
  if (!active || !payload?.length) {
    return null;
  }
  const row = payload[0]?.payload;
  return (
    <div className="trendTooltip">
      <strong>{label}</strong>
      {payload
        .filter((item) => item.dataKey && item.dataKey !== "position")
        .slice(0, 8)
        .map((item) => (
          <span key={String(item.dataKey)}>
            <i style={{ backgroundColor: item.color ?? "#111827" }} />
            {item.name ?? item.dataKey}: {typeof item.value === "number" ? money.format(item.value) : "-"}
          </span>
        ))}
      {row ? (
        <>
          <span>Signal: {row.trade_signal ?? "-"}</span>
          <span>Score: {formatSignalValue("signal_score", row.signal_score)}</span>
          <span>Position: {row.position ? "Long" : "Cash"}</span>
          <span>Volume: {typeof row.volume === "number" ? compact.format(row.volume) : "-"}</span>
        </>
      ) : null}
    </div>
  );
}

function buildPriceDomain(data: SignalPoint[], activeLayers: Set<PriceLayerKey>): [number, number] {
  const values: number[] = [];
  for (const point of data) {
    if (activeLayers.has("close")) values.push(...finiteValues([point.close]));
    if (activeLayers.has("sma20")) values.push(...finiteValues([point.sma_20]));
    if (activeLayers.has("sma50")) values.push(...finiteValues([point.sma_50]));
    if (activeLayers.has("sma200")) values.push(...finiteValues([point.sma_200]));
    if (activeLayers.has("bollinger")) values.push(...finiteValues([point.bb_upper, point.bb_lower]));
    if (activeLayers.has("keltner")) values.push(...finiteValues([point.keltner_upper, point.keltner_lower]));
  }
  if (!values.length) {
    return [0, 1];
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = Math.max((max - min) * 0.07, max * 0.01, 1);
  return [Math.floor(min - padding), Math.ceil(max + padding)];
}

function finiteValues(values: Array<SignalValue | undefined>) {
  return values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
}

function buildLessonReadout(
  lesson: SystemLessonId,
  context: {
    latest: OverviewRow | undefined;
    leaders: OverviewRow[];
    overview: OverviewRow[];
    universe: UniverseResponse | null;
    strategy: StrategyInfo | null;
    backtest: BacktestResult | null;
    paper: PaperSnapshot | null;
  }
) {
  const top = context.leaders[0];
  if (lesson === "data") {
    return {
      primary: `${context.overview.length} watched tickers, ${context.universe ? compact.format(context.universe.count) : "-"} cached listings`,
      secondary: context.universe?.as_of ? `Universe cache refreshed ${new Date(context.universe.as_of).toLocaleString()}` : "Universe cache is not available yet."
    };
  }
  if (lesson === "signals") {
    return {
      primary: top ? `${top.sym} leads with score ${fmt(top.signal_score)}` : "Signals pending",
      secondary: top?.signal_reason ?? "Load or ingest market data to calculate signal rows."
    };
  }
  if (lesson === "strategy") {
    return {
      primary: context.strategy?.label ?? "Strategy pending",
      secondary: context.strategy?.position_rule ?? context.latest?.signal_reason ?? "Select a strategy to see the active rule."
    };
  }
  if (lesson === "backtest") {
    return {
      primary: context.backtest ? `${pct.format(context.backtest.metrics.total_return ?? 0)} strategy return` : "Backtest pending",
      secondary: context.backtest
        ? `${pct.format(context.backtest.metrics.benchmark_return ?? 0)} benchmark, ${pct.format(context.backtest.metrics.max_drawdown ?? 0)} max drawdown`
        : "Run a symbol backtest to compare rules against buy-and-hold."
    };
  }
  return {
    primary: context.paper ? money.format(context.paper.equity) : "Paper account pending",
    secondary: context.paper ? `${context.paper.orders.length} intended orders and ${context.paper.positions.length} open positions` : "Paper trading creates orders without live execution."
  };
}

function SignalTrendTooltip({
  active,
  label,
  payload,
  scale,
  options
}: {
  active?: boolean;
  label?: string;
  payload?: Array<{ color?: string; dataKey?: string; value?: number; payload?: TrendChartPoint }>;
  scale: SignalTrendScale;
  options: SignalTrendOption[];
}) {
  if (!active || !payload?.length) {
    return null;
  }
  const optionByKey = new Map(options.map((option) => [option.key, option]));
  return (
    <div className="trendTooltip">
      <strong>{label}</strong>
      {payload
        .filter((item) => item.dataKey && item.dataKey !== "position")
        .map((item) => {
          const key = String(item.dataKey);
          const option = optionByKey.get(key);
          const raw = item.payload?.[`raw_${key}`];
          return (
            <span key={key}>
              <i style={{ backgroundColor: item.color ?? "#111827" }} />
              {option?.label ?? key}: {scale === "normalized" ? `${fmt(item.value)} (${formatSignalValue(key, raw as SignalValue)})` : formatSignalValue(key, item.value ?? null)}
            </span>
          );
        })}
      {payload.some((item) => item.dataKey === "position") ? <span>Position: {payload.find((item) => item.dataKey === "position")?.value ? "Long" : "Cash"}</span> : null}
    </div>
  );
}

function buildSignalTrendOptions(catalog: SignalCatalogItem[]): SignalTrendOption[] {
  const seen = new Set<string>();
  const options: SignalTrendOption[] = [];
  for (const [key, label, group] of SIGNAL_TREND_EXTRAS) {
    options.push({ key, label, group });
    seen.add(key);
  }
  for (const item of catalog) {
    if (!seen.has(item.key)) {
      options.push({ key: item.key, label: item.label, group: item.group });
      seen.add(item.key);
    }
  }
  return options;
}

function buildSignalTrendData(series: SignalPoint[], selectedKeys: string[], scale: SignalTrendScale): TrendChartPoint[] {
  const ranges = new Map<string, { min: number; max: number }>();
  for (const key of selectedKeys) {
    const values = series.map((point) => numericSignal(point[key])).filter((value): value is number => value != null);
    ranges.set(key, values.length ? { min: Math.min(...values), max: Math.max(...values) } : { min: 0, max: 0 });
  }
  return series.map((point) => {
    const row: TrendChartPoint = {
      date: point.date,
      position: typeof point.position === "number" ? point.position : null
    };
    for (const key of selectedKeys) {
      const raw = numericSignal(point[key]);
      row[`raw_${key}`] = raw;
      if (raw == null) {
        row[key] = null;
      } else if (scale === "normalized") {
        const range = ranges.get(key);
        row[key] = range && range.max !== range.min ? ((raw - range.min) / (range.max - range.min)) * 100 : 50;
      } else {
        row[key] = raw;
      }
    }
    return row;
  });
}

function numericSignal(value: SignalValue | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function labelPage(page: Page) {
  if (page === "home") return "Home";
  if (page === "stock") return "Stock";
  if (page === "signals") return "Signals";
  return "Backtesting";
}

function titleCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function fmt(value: SignalValue | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(2);
}

function pctOrDash(value: SignalValue | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return pct.format(value);
}

function formatSignalValue(key: string, value: SignalValue | undefined) {
  if (value == null || value === "") {
    return "-";
  }
  if (typeof value !== "number") {
    return value;
  }
  if (key === "signal_score" || key.endsWith("_score")) {
    return value.toFixed(2);
  }
  if (
    key.includes("return") ||
    key.includes("momentum") ||
    key.includes("pct") ||
    key.includes("width") ||
    key.startsWith("realized_vol") ||
    key.includes("distance")
  ) {
    return pct.format(value);
  }
  if (key === "close" || key.includes("sma") || key.includes("ema") || key.includes("keltner") || key.includes("donchian") || key.includes("vwap")) {
    return money.format(value);
  }
  return value.toFixed(Math.abs(value) >= 1000 ? 0 : 2);
}

function scoreWidth(value: number, range: [number, number]) {
  const [min, max] = range;
  return Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
}
