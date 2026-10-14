import { useState, useEffect, useCallback } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import { api } from "../api/client";

const RANGE_OPTIONS = [
  { label: "7d", value: 7 },
  { label: "30d", value: 30 },
  { label: "90d", value: 90 },
];

const PROVIDER_COLORS = {
  anthropic: "#d97757",
  openai: "#10a37f",
  ollama: "#6366f1",
};
const FALLBACK_COLORS = ["#d97757", "#10a37f", "#6366f1", "#f59e0b", "#ec4899"];

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatNumber(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export default function UsageChart() {
  const [range, setRange] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (days) => {
    setLoading(true);
    try {
      const res = await api.usageStats(days);
      setData(res);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(range); }, [range, load]);

  if (loading && !data) {
    return <div className="usage-chart-card loading">Loading usage…</div>;
  }
  if (error) {
    return <div className="usage-chart-card alert error visible">{error}</div>;
  }
  if (!data || data.totals.calls === 0) {
    return (
      <div className="usage-chart-card empty-state">
        No LLM usage yet. Once your agents start running, token usage will show up here.
      </div>
    );
  }

  const chartData = data.daily.map((d) => ({ ...d, label: formatDate(d.date) }));

  return (
    <div className="usage-chart-card">
      <div className="usage-chart-header">
        <div>
          <h3>LLM Token Usage</h3>
          <div className="usage-chart-subtitle">
            {formatNumber(data.totals.total_tokens)} tokens · {data.totals.calls} calls
          </div>
        </div>
        <div className="range-toggle">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={opt.value === range ? "active" : ""}
              onClick={() => setRange(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="usage-chart-body">
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="tokenGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#d97757" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#d97757" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={formatNumber} tick={{ fontSize: 12 }} axisLine={false} tickLine={false} width={44} />
            <Tooltip formatter={(value) => [formatNumber(value), "Tokens"]} contentStyle={{ borderRadius: 8, fontSize: 13 }} />
            <Area type="monotone" dataKey="total_tokens" stroke="#d97757" strokeWidth={2} fill="url(#tokenGradient)" />
          </AreaChart>
        </ResponsiveContainer>

        {data.by_provider.length > 0 && (
          <div className="usage-chart-breakdown">
            <ResponsiveContainer width={140} height={140}>
              <PieChart>
                <Pie data={data.by_provider} dataKey="total_tokens" nameKey="provider" innerRadius={38} outerRadius={60} paddingAngle={2}>
                  {data.by_provider.map((entry, i) => (
                    <Cell key={entry.provider} fill={PROVIDER_COLORS[entry.provider] || FALLBACK_COLORS[i % FALLBACK_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => formatNumber(value)} />
              </PieChart>
            </ResponsiveContainer>
            <ul className="usage-legend">
              {data.by_provider.map((entry, i) => (
                <li key={entry.provider}>
                  <span className="dot" style={{ background: PROVIDER_COLORS[entry.provider] || FALLBACK_COLORS[i % FALLBACK_COLORS.length] }} />
                  {entry.provider} · {formatNumber(entry.total_tokens)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}