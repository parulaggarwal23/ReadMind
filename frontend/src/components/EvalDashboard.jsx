import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, CONDITIONS } from "../api";

// Recharts writes colours into SVG attributes, where CSS variables don't resolve,
// so read the themed series colours once (and again when the colour scheme changes).
function useSeriesColors() {
  const read = () => {
    const s = getComputedStyle(document.documentElement);
    return CONDITIONS.map((_, i) => s.getPropertyValue(`--series-${i + 1}`).trim() || "#888");
  };
  const [colors, setColors] = useState(read);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => setColors(read());
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return colors;
}

const RATE_METRICS = [
  { key: "completeness", label: "Completeness", better: "higher" },
  { key: "hallucination_rate", label: "Hallucination rate", better: "lower" },
  { key: "precision_at_k", label: "Evidence precision@k", better: "higher" },
  { key: "recall_at_k", label: "Evidence recall@k", better: "higher" },
];
const SCORE_METRICS = [
  { key: "accuracy", label: "Accuracy", better: "higher" },
  { key: "relevance", label: "Relevance", better: "higher" },
];
const TABLE_METRICS = [
  ...SCORE_METRICS.map((m) => ({ ...m, fmt: (v) => v.toFixed(2) })),
  ...RATE_METRICS.map((m) => ({ ...m, fmt: (v) => `${(v * 100).toFixed(1)}%` })),
  { key: "mrr", label: "MRR", fmt: (v) => v.toFixed(3), better: "higher" },
  { key: "citation_precision", label: "Valid citations", fmt: (v) => `${(v * 100).toFixed(1)}%`, better: "higher" },
  { key: "latency_p50_ms", label: "Latency p50", fmt: (v) => `${(v / 1000).toFixed(2)} s`, better: "lower" },
  { key: "latency_p95_ms", label: "Latency p95", fmt: (v) => `${(v / 1000).toFixed(2)} s`, better: "lower" },
];

function chartRows(summary, metrics, scale = 1) {
  return metrics.map((m) => {
    const row = { metric: m.label };
    CONDITIONS.forEach((c) => {
      const v = summary.conditions[c.id]?.[m.key];
      row[c.id] = v == null ? null : +(v * scale).toFixed(2);
    });
    return row;
  });
}

function MetricChart({ title, data, domain, unit, colors }) {
  return (
    <div className="card chart-card">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} barGap={2} barCategoryGap="22%">
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="metric" tickLine={false} axisLine={{ stroke: "var(--grid)" }} tick={{ fill: "var(--text-2)", fontSize: 12 }} />
          <YAxis domain={domain} tickLine={false} axisLine={false} tick={{ fill: "var(--text-2)", fontSize: 12 }} unit={unit} width={44} />
          <Tooltip
            cursor={{ fill: "var(--hover)" }}
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text-1)" }}
            formatter={(v, name) => [v == null ? "—" : `${v}${unit || ""}`, CONDITIONS.find((c) => c.id === name)?.label]}
          />
          <Legend formatter={(id) => <span style={{ color: "var(--text-2)" }}>{CONDITIONS.find((c) => c.id === id)?.label}</span>} />
          {CONDITIONS.map((c, i) => (
            <Bar key={c.id} dataKey={c.id} fill={colors[i]} radius={[4, 4, 0, 0]} maxBarSize={36} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function EvalDashboard() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const colors = useSeriesColors();

  useEffect(() => {
    api.evalSummary().then(setSummary).catch((e) => setError(e.message));
  }, []);

  const best = useMemo(() => {
    if (!summary) return {};
    const out = {};
    TABLE_METRICS.forEach((m) => {
      const vals = CONDITIONS.map((c) => summary.conditions[c.id]?.[m.key]).filter((v) => v != null);
      if (vals.length) out[m.key] = m.better === "lower" ? Math.min(...vals) : Math.max(...vals);
    });
    return out;
  }, [summary]);

  if (error)
    return (
      <div className="alert">
        No evaluation results yet ({error}). Build <code>data/eval/benchmark.jsonl</code>, then run{" "}
        <code>python -m evaluation.run_eval</code>.
      </div>
    );
  if (!summary) return <div className="card skeleton tall" />;

  const present = CONDITIONS.filter((c) => summary.conditions[c.id]);
  const full = summary.conditions.full_history;
  const base = summary.conditions.llm_only;

  return (
    <div className="stack">
      <div className="kpis">
        <div className="card kpi">
          <span className="kpi-value">{summary.n_questions}</span>
          <span className="kpi-label">benchmark questions</span>
        </div>
        {full && base && full.accuracy != null && base.accuracy != null && (
          <div className="card kpi">
            <span className="kpi-value">{full.accuracy.toFixed(2)} <small>vs {base.accuracy.toFixed(2)}</small></span>
            <span className="kpi-label">accuracy (1–5): history RAG vs LLM only</span>
          </div>
        )}
        {full && base && full.hallucination_rate != null && base.hallucination_rate != null && (
          <div className="card kpi">
            <span className="kpi-value">
              {(full.hallucination_rate * 100).toFixed(0)}% <small>vs {(base.hallucination_rate * 100).toFixed(0)}%</small>
            </span>
            <span className="kpi-label">hallucination rate: history RAG vs LLM only</span>
          </div>
        )}
      </div>

      <div className="chart-grid">
        <MetricChart title="Answer quality (LLM judge, 1–5)" data={chartRows(summary, SCORE_METRICS)} domain={[0, 5]} colors={colors} />
        <MetricChart title="Rates (%)" data={chartRows(summary, RATE_METRICS, 100)} domain={[0, 100]} unit="%" colors={colors} />
      </div>

      <div className="card">
        <h3>All metrics</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Metric</th>
                {present.map((c) => (
                  <th key={c.id}><span className="swatch" style={{ background: c.color }} />{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {TABLE_METRICS.map((m) => (
                <tr key={m.key}>
                  <td>{m.label} <span className="muted small">({m.better} is better)</span></td>
                  {present.map((c) => {
                    const v = summary.conditions[c.id][m.key];
                    return (
                      <td key={c.id} className={`num ${v != null && v === best[m.key] && present.length > 1 ? "best" : ""}`}>
                        {v == null ? "—" : m.fmt(v)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {summary.tests?.length > 0 && (
        <div className="card">
          <h3>Paired significance tests (Wilcoxon signed-rank)</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Metric</th><th>Comparison</th><th>n</th><th>Mean A</th><th>Mean B</th><th>p-value</th></tr>
              </thead>
              <tbody>
                {summary.tests.map((t, i) => (
                  <tr key={i}>
                    <td>{t.metric}</td>
                    <td>{CONDITIONS.find((c) => c.id === t.a)?.short} vs {CONDITIONS.find((c) => c.id === t.b)?.short}</td>
                    <td className="num">{t.n}</td>
                    <td className="num">{t.mean_a?.toFixed(3) ?? "—"}</td>
                    <td className="num">{t.mean_b?.toFixed(3) ?? "—"}</td>
                    <td className={`num ${t.p_value != null && t.p_value < 0.05 ? "best" : ""}`}>
                      {t.p_value == null ? "n/a" : t.p_value < 0.001 ? "< 0.001" : t.p_value.toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {Object.keys(summary.per_category || {}).length > 0 && (
        <div className="card">
          <h3>Accuracy by question category</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Category</th>{present.map((c) => <th key={c.id}>{c.short}</th>)}</tr>
              </thead>
              <tbody>
                {Object.entries(summary.per_category).map(([cat, vals]) => (
                  <tr key={cat}>
                    <td>{cat.replace(/_/g, " ")}</td>
                    {present.map((c) => <td key={c.id} className="num">{vals[c.id]?.toFixed(2) ?? "—"}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {summary.human && (
        <div className="card">
          <h3>Human evaluation ({summary.human.n_raters} raters{summary.human.kappa_accuracy != null ? `, weighted κ = ${summary.human.kappa_accuracy}` : ""})</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Condition</th><th>Accuracy (1–5)</th><th>Usefulness (1–5)</th><th>n</th></tr></thead>
              <tbody>
                {present.map((c) => {
                  const h = summary.human.conditions[c.id];
                  return h ? (
                    <tr key={c.id}><td>{c.label}</td><td className="num">{h.accuracy}</td><td className="num">{h.usefulness}</td><td className="num">{h.n}</td></tr>
                  ) : null;
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
