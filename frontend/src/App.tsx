import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Activity,
  BarChart3,
  Database,
  Gauge,
  LineChart as LineIcon,
  Play,
  Plus,
  RefreshCw,
  Server,
  Wallet
} from "lucide-react";
import {
  Area,
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
import { addSymbols, fetchOverview, fetchStrategy, fetchTimeseries, ingest, runBacktest, runPaper } from "./api";
import type { BacktestResult, OverviewRow, PaperSnapshot, SignalPoint, StrategyInfo } from "./types";

const DEFAULT_SYMBOLS = ["AAPL", "AMZN", "META", "NFLX", "GOOGL"];

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const pct = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 });

export function App() {
  const [overview, setOverview] = useState<OverviewRow[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState(DEFAULT_SYMBOLS[0]);
  const [series, setSeries] = useState<SignalPoint[]>([]);
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [paper, setPaper] = useState<PaperSnapshot | null>(null);
  const [strategy, setStrategy] = useState<StrategyInfo | null>(null);
  const [newSymbol, setNewSymbol] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const symbols = useMemo(() => overview.map((row) => row.sym), [overview]);
  const latest = overview.find((row) => row.sym === selectedSymbol) ?? overview[0];
  const scoreTone = (latest?.signal_score ?? 0) >= 4 ? "positive" : (latest?.signal_score ?? 0) < 0 ? "negative" : "neutral";
  const priceDomain = useMemo<[number, number]>(() => {
    const values = series
      .flatMap((point) => [point.close, point.sma_20, point.sma_50, point.bb_upper, point.bb_lower])
      .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
    if (!values.length) {
      return [0, 1];
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * 0.06, max * 0.01);
    return [Math.floor(min - padding), Math.ceil(max + padding)];
  }, [series]);

  async function load(symbol = selectedSymbol) {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchOverview();
      setOverview(rows);
      const active = rows.some((row) => row.sym === symbol) ? symbol : rows[0]?.sym ?? DEFAULT_SYMBOLS[0];
      setSelectedSymbol(active);
      const [points, backtestResult, paperSnapshot] = await Promise.all([
        fetchTimeseries(active),
        runBacktest(active),
        runPaper(rows.length ? rows.map((row) => row.sym) : DEFAULT_SYMBOLS)
      ]);
      setSeries(points);
      setBacktest(backtestResult);
      setPaper(paperSnapshot);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  async function refreshData() {
    setLoading(true);
    setError(null);
    try {
      const activeSymbols = symbols.length ? symbols : DEFAULT_SYMBOLS;
      await ingest(activeSymbols);
      await load(selectedSymbol);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refresh failed");
      setLoading(false);
    }
  }

  async function chooseSymbol(symbol: string) {
    setSelectedSymbol(symbol);
    setLoading(true);
    setError(null);
    try {
      const [points, backtestResult] = await Promise.all([fetchTimeseries(symbol), runBacktest(symbol)]);
      setSeries(points);
      setBacktest(backtestResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Symbol load failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleAddSymbol(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const symbol = newSymbol.trim().toUpperCase();
    if (!/^[A-Z0-9._-]{1,12}$/.test(symbol)) {
      setError("Enter a ticker using letters, numbers, '.', '_' or '-'.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await addSymbols([symbol]);
      setNewSymbol("");
      await load(symbol);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ticker add failed");
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchStrategy()
      .then(setStrategy)
      .catch(() => undefined);
    load(DEFAULT_SYMBOLS[0]);
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
            <select value={selectedSymbol} onChange={(event) => chooseSymbol(event.target.value)}>
              {(symbols.length ? symbols : DEFAULT_SYMBOLS).map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <form className="tickerForm" onSubmit={handleAddSymbol}>
            <input
              aria-label="Add ticker"
              value={newSymbol}
              onChange={(event) => setNewSymbol(event.target.value.toUpperCase())}
              placeholder="Ticker"
              disabled={loading}
            />
            <button className="iconButton" type="submit" disabled={loading || !newSymbol.trim()} title="Add ticker">
              <Plus size={18} />
            </button>
          </form>
          <button className="iconButton" type="button" onClick={refreshData} disabled={loading} title="Refresh market data">
            <RefreshCw size={18} className={loading ? "spin" : ""} />
          </button>
          <button className="commandButton" type="button" onClick={() => chooseSymbol(selectedSymbol)} disabled={loading}>
            <Play size={17} />
            Run
          </button>
        </div>
      </header>

      {error ? <div className="alert">{error}</div> : null}

      <section className="metricsGrid">
        <Metric icon={<LineIcon size={18} />} label="Close" value={latest ? money.format(latest.close) : "-"} />
        <Metric
          icon={<Activity size={18} />}
          label="Signal"
          value={latest ? latest.trade_signal : "-"}
          tone={latest?.trade_signal === "BUY" ? "positive" : latest?.trade_signal === "SELL" ? "negative" : "neutral"}
        />
        <Metric
          icon={<Gauge size={18} />}
          label="Score"
          value={latest?.signal_score == null ? "-" : latest.signal_score.toFixed(0)}
          tone={scoreTone}
        />
        <Metric icon={<Server size={18} />} label="RSI 14" value={latest?.rsi_14 == null ? "-" : latest.rsi_14.toFixed(1)} />
        <Metric icon={<Database size={18} />} label="ATR %" value={latest?.atr_pct == null ? "-" : pct.format(latest.atr_pct)} />
        <Metric icon={<Database size={18} />} label="Volume" value={latest ? compact.format(latest.volume) : "-"} />
        <Metric
          icon={<Wallet size={18} />}
          label="Paper Equity"
          value={paper ? money.format(paper.equity) : "-"}
          tone="positive"
        />
      </section>

      <section className="workspace">
        <div className="panel pricePanel">
          <div className="panelHeader">
            <h2>{selectedSymbol} Price</h2>
            <span>{latest ? pct.format(latest.period_return) : "-"}</span>
          </div>
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
                <Line type="monotone" dataKey="bb_upper" stroke="#94a3b8" strokeWidth={1} dot={false} strokeDasharray="4 4" />
                <Line type="monotone" dataKey="bb_lower" stroke="#94a3b8" strokeWidth={1} dot={false} strokeDasharray="4 4" />
                <Area type="stepAfter" dataKey="position" yAxisId="position" fill="#d1fae5" stroke="#10b981" fillOpacity={0.35} />
                <YAxis yAxisId="position" orientation="right" hide domain={[0, 1]} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <div className="panelHeader">
            <h2>MACD</h2>
            <span>{latest?.macd_hist == null ? "-" : latest.macd_hist.toFixed(2)}</span>
          </div>
          <div className="chartBox">
            <ResponsiveContainer>
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
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <div className="panelHeader">
            <h2>RSI</h2>
            <span>{latest?.rsi_14 == null ? "-" : latest.rsi_14.toFixed(1)}</span>
          </div>
          <div className="chartBox">
            <ResponsiveContainer>
              <LineChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#e6e8ec" vertical={false} />
                <XAxis dataKey="date" hide />
                <YAxis width={42} domain={[0, 100]} tickLine={false} axisLine={false} />
                <Tooltip formatter={(value) => (typeof value === "number" ? value.toFixed(1) : value)} />
                <ReferenceLine y={70} stroke="#dc2626" strokeDasharray="4 4" />
                <ReferenceLine y={30} stroke="#16a34a" strokeDasharray="4 4" />
                <Line type="monotone" dataKey="rsi_14" stroke="#2563eb" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="analysisGrid">
        <div className="panel algorithmPanel">
          <div className="panelHeader">
            <h2>Algorithm</h2>
            <span>{latest?.signal_score == null ? "-" : `${latest.signal_score.toFixed(0)} / 10`}</span>
          </div>
          <div className="scoreRows">
            {(strategy?.components ?? []).map((component) => {
              const value = latest?.[component.key] ?? 0;
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

        <div className="panel">
          <div className="panelHeader">
            <h2>Stochastic</h2>
            <span>{latest?.stoch_k == null ? "-" : latest.stoch_k.toFixed(1)}</span>
          </div>
          <div className="chartBox compact">
            <ResponsiveContainer>
              <LineChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#e6e8ec" vertical={false} />
                <XAxis dataKey="date" hide />
                <YAxis width={42} domain={[0, 100]} tickLine={false} axisLine={false} />
                <Tooltip formatter={(value) => (typeof value === "number" ? value.toFixed(1) : value)} />
                <ReferenceLine y={80} stroke="#dc2626" strokeDasharray="4 4" />
                <ReferenceLine y={20} stroke="#16a34a" strokeDasharray="4 4" />
                <Line type="monotone" dataKey="stoch_k" stroke="#7c3aed" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="stoch_d" stroke="#64748b" strokeWidth={1.7} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="metricStrip slim">
            <SmallMetric label="BB Width" value={pctOrDash(latest?.bb_width)} />
            <SmallMetric label="Volume Z" value={fmt(latest?.volume_z)} />
            <SmallMetric label="20D Mom" value={pctOrDash(latest?.momentum_20d)} />
            <SmallMetric label="52W High" value={pctOrDash(latest?.distance_52w_high)} />
          </div>
        </div>
      </section>

      <section className="workspace lower">
        <div className="panel">
          <div className="panelHeader">
            <h2>Backtest</h2>
            <span>{backtest ? pct.format(backtest.metrics.total_return ?? 0) : "-"}</span>
          </div>
          <div className="chartBox">
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
          <div className="metricStrip">
            <SmallMetric label="Sharpe" value={fmt(backtest?.metrics.sharpe)} />
            <SmallMetric label="Drawdown" value={pct.format(backtest?.metrics.max_drawdown ?? 0)} />
            <SmallMetric label="Trades" value={String(backtest?.metrics.trade_count ?? 0)} />
            <SmallMetric label="Exposure" value={pct.format(backtest?.metrics.exposure ?? 0)} />
          </div>
        </div>

        <div className="panel tablePanel">
          <div className="panelHeader">
            <h2>Signals</h2>
            <span>{overview.length}</span>
          </div>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Sym</th>
                  <th>Signal</th>
                  <th>Score</th>
                  <th>Close</th>
                  <th>RSI</th>
                  <th>ATR</th>
                  <th>Return</th>
                </tr>
              </thead>
              <tbody>
                {overview.map((row) => (
                  <tr key={row.sym} onClick={() => chooseSymbol(row.sym)} className={row.sym === selectedSymbol ? "activeRow" : ""}>
                    <td>{row.sym}</td>
                    <td>
                      <span className={`pill ${row.trade_signal.toLowerCase()}`}>{row.trade_signal}</span>
                    </td>
                    <td>{row.signal_score?.toFixed(0) ?? "-"}</td>
                    <td>{money.format(row.close)}</td>
                    <td>{row.rsi_14?.toFixed(1) ?? "-"}</td>
                    <td>{pctOrDash(row.atr_pct)}</td>
                    <td className={row.period_return >= 0 ? "green" : "red"}>{pct.format(row.period_return)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel tablePanel">
          <div className="panelHeader">
            <h2>Paper</h2>
            <span>{paper ? money.format(paper.cash) : "-"}</span>
          </div>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Sym</th>
                  <th>Side</th>
                  <th>Notional</th>
                </tr>
              </thead>
              <tbody>
                {(paper?.orders ?? []).map((order) => (
                  <tr key={`${order.sym}-${order.side}`}>
                    <td>{order.sym}</td>
                    <td>{order.side}</td>
                    <td>{money.format(order.notional)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </main>
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

function fmt(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(2);
}

function pctOrDash(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return pct.format(value);
}

function scoreWidth(value: number, range: [number, number]) {
  const [min, max] = range;
  return Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
}
