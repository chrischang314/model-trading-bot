import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  BarChart3,
  Database,
  LineChart as LineIcon,
  Play,
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
import { fetchOverview, fetchTimeseries, ingest, runBacktest, runPaper } from "./api";
import type { BacktestResult, OverviewRow, PaperSnapshot, SignalPoint } from "./types";

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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const symbols = useMemo(() => overview.map((row) => row.sym), [overview]);
  const latest = overview.find((row) => row.sym === selectedSymbol) ?? overview[0];

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
        runPaper(rows.map((row) => row.sym))
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

  useEffect(() => {
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
        <Metric icon={<Server size={18} />} label="RSI 14" value={latest?.rsi_14 == null ? "-" : latest.rsi_14.toFixed(1)} />
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
                <YAxis width={64} tickFormatter={(value) => `$${value}`} tickLine={false} axisLine={false} domain={["dataMin", "dataMax"]} />
                <Tooltip formatter={(value) => (typeof value === "number" ? value.toFixed(2) : value)} />
                <Line type="monotone" dataKey="close" stroke="#111827" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="sma_20" stroke="#0f9f9a" strokeWidth={1.7} dot={false} />
                <Line type="monotone" dataKey="sma_50" stroke="#d97706" strokeWidth={1.7} dot={false} />
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
                  <th>Close</th>
                  <th>RSI</th>
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
                    <td>{money.format(row.close)}</td>
                    <td>{row.rsi_14?.toFixed(1) ?? "-"}</td>
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
