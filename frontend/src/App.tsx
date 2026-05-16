import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactElement, ReactNode } from "react";
import {
  Activity,
  BarChart3,
  ChevronDown,
  ChevronRight,
  Database,
  Gauge,
  Layers,
  LineChart as LineIcon,
  Play,
  Plus,
  RefreshCw,
  Search,
  Server,
  SlidersHorizontal,
  Wallet
} from "lucide-react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
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
  fetchLatestSignals,
  fetchOverview,
  fetchSignalCatalog,
  fetchSp500Universe,
  fetchStrategies,
  fetchStrategy,
  fetchTimeseries,
  ingest,
  refreshSp500Universe,
  runBacktest,
  runPaper
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
  const [selectedStrategyId, setSelectedStrategyId] = useState(DEFAULT_STRATEGY_ID);
  const [customStrategy, setCustomStrategy] = useState<CustomStrategyConfig>(DEFAULT_CUSTOM_STRATEGY);
  const [catalog, setCatalog] = useState<SignalCatalogItem[]>([]);
  const [universe, setUniverse] = useState<UniverseResponse | null>(null);
  const [newSymbol, setNewSymbol] = useState("");
  const [signalFilter, setSignalFilter] = useState("");
  const [appLoading, setAppLoading] = useState(true);
  const [symbolLoading, setSymbolLoading] = useState(false);
  const [addingSymbol, setAddingSymbol] = useState(false);
  const [refreshingData, setRefreshingData] = useState(false);
  const [syncingUniverse, setSyncingUniverse] = useState(false);
  const [backtestRunning, setBacktestRunning] = useState(false);
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
  const priceDomain = useMemo<[number, number]>(() => {
    const values = series
      .flatMap((point) => [point.close, point.sma_20, point.sma_50, point.bb_upper, point.bb_lower, point.keltner_upper, point.keltner_lower])
      .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
    if (!values.length) {
      return [0, 1];
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * 0.06, max * 0.01);
    return [Math.floor(min - padding), Math.ceil(max + padding)];
  }, [series]);

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
    const custom = strategyId === CUSTOM_STRATEGY_ID ? nextCustom : undefined;
    setSelectedStrategyId(strategyId);
    setStatus("Switching strategy and recalculating views...");
    setError(null);
    try {
      await reloadOverview(selectedSymbol, strategyId, custom);
      setStatus(`Strategy switched to ${strategyId === CUSTOM_STRATEGY_ID ? nextCustom.name : strategies.find((item) => item.id === strategyId)?.label ?? strategyId}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Strategy switch failed");
    }
  }

  async function applyCustomStrategy() {
    await changeStrategy(CUSTOM_STRATEGY_ID, customStrategy);
  }

  useEffect(() => {
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
          priceDomain={priceDomain}
          scoreTone={scoreTone}
        />
      ) : null}

      {page === "signals" ? (
        <SignalsPage
          catalog={catalog}
          displayedSignals={displayedSignals}
          signalFilter={signalFilter}
          setSignalFilter={setSignalFilter}
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
          backtestRunning={backtestRunning}
          runSelectedBacktest={runSelectedBacktest}
        />
      ) : null}
    </main>
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

function StockPage({
  latest,
  selectedSymbol,
  series,
  strategy,
  priceDomain,
  scoreTone
}: {
  latest: OverviewRow | undefined;
  selectedSymbol: string;
  series: SignalPoint[];
  strategy: StrategyInfo | null;
  priceDomain: [number, number];
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
          <PriceChart series={series} priceDomain={priceDomain} />
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
  signalFilter,
  setSignalFilter,
  chooseSymbol
}: {
  catalog: SignalCatalogItem[];
  displayedSignals: OverviewRow[];
  signalFilter: string;
  setSignalFilter: (value: string) => void;
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

function BacktestingPage({
  selectedSymbol,
  backtest,
  latest,
  strategy,
  customStrategy,
  setCustomStrategy,
  applyCustomStrategy,
  backtestRunning,
  runSelectedBacktest
}: {
  selectedSymbol: string;
  backtest: BacktestResult | null;
  latest: OverviewRow | undefined;
  strategy: StrategyInfo | null;
  customStrategy: CustomStrategyConfig;
  setCustomStrategy: (value: CustomStrategyConfig) => void;
  applyCustomStrategy: () => void;
  backtestRunning: boolean;
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
        disabled={backtestRunning}
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

function StrategyControlPanel({
  strategy,
  customStrategy,
  setCustomStrategy,
  applyCustomStrategy,
  disabled
}: {
  strategy: StrategyInfo | null;
  customStrategy: CustomStrategyConfig;
  setCustomStrategy: (value: CustomStrategyConfig) => void;
  applyCustomStrategy: () => void;
  disabled: boolean;
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

function PriceChart({ series, priceDomain }: { series: SignalPoint[]; priceDomain: [number, number] }) {
  return (
    <div className="chartBox tall">
      <ResponsiveContainer>
        <ComposedChart data={series} margin={{ top: 12, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#e6e8ec" vertical={false} />
          <XAxis dataKey="date" minTickGap={32} tickLine={false} axisLine={false} />
          <YAxis width={72} tickFormatter={(value) => money.format(Number(value))} tickLine={false} axisLine={false} domain={priceDomain} />
          <Tooltip formatter={(value) => (typeof value === "number" ? value.toFixed(2) : value)} />
          <Line type="monotone" dataKey="close" stroke="#111827" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="sma_20" stroke="#0f9f9a" strokeWidth={1.7} dot={false} />
          <Line type="monotone" dataKey="sma_50" stroke="#d97706" strokeWidth={1.7} dot={false} />
          <Line type="monotone" dataKey="sma_200" stroke="#6366f1" strokeWidth={1.5} dot={false} />
          <Line type="monotone" dataKey="bb_upper" stroke="#94a3b8" strokeWidth={1} dot={false} strokeDasharray="4 4" />
          <Line type="monotone" dataKey="bb_lower" stroke="#94a3b8" strokeWidth={1} dot={false} strokeDasharray="4 4" />
          <Line type="monotone" dataKey="keltner_upper" stroke="#cbd5e1" strokeWidth={1} dot={false} strokeDasharray="2 3" />
          <Line type="monotone" dataKey="keltner_lower" stroke="#cbd5e1" strokeWidth={1} dot={false} strokeDasharray="2 3" />
          <Line type="stepAfter" dataKey="position" yAxisId="position" stroke="#10b981" strokeWidth={1.4} dot={false} />
          <YAxis yAxisId="position" orientation="right" hide domain={[0, 8]} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
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
  return (
    <div className={`chartBox ${compactMode ? "" : "tall"}`}>
      <ResponsiveContainer>
        <LineChart data={backtest?.equity_curve ?? []} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#e6e8ec" vertical={false} />
          <XAxis dataKey="date" minTickGap={32} tickLine={false} axisLine={false} />
          <YAxis width={70} tickFormatter={(value) => compact.format(value)} tickLine={false} axisLine={false} />
          <Tooltip formatter={(value) => (typeof value === "number" ? money.format(value) : value)} />
          <Line type="monotone" dataKey="equity" stroke="#0f766e" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="benchmark_equity" stroke="#6b7280" strokeWidth={1.7} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
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
