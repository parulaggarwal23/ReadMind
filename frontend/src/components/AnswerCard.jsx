import { CONDITIONS } from "../api";
import AnswerText from "./AnswerText";
import EvidenceList from "./EvidenceList";

function Metric({ label, value, tone }) {
  return (
    <div className={`metric ${tone || ""}`}>
      <span className="metric-value">{value}</span>
      <span className="metric-label">{label}</span>
    </div>
  );
}

export default function AnswerCard({ result, onCite, compact = false }) {
  const cond = CONDITIONS.find((c) => c.id === result.condition);
  if (result.error) {
    return (
      <div className="card answer-card">
        <div className="answer-head">
          <span className="cond-tag" style={{ "--c": cond?.color }}>{result.condition_label}</span>
        </div>
        <div className="alert error">{result.error}</div>
      </div>
    );
  }
  const v = result.verification || {};
  const evidenceIds = result.evidence.map((e) => e.id);
  const pct = (x) => (x == null ? "—" : `${Math.round(x * 100)}%`);

  return (
    <div className="card answer-card">
      <div className="answer-head">
        <span className="cond-tag" style={{ "--c": cond?.color }}>{result.condition_label}</span>
        <span className="muted mono">{(result.latency_ms.total / 1000).toFixed(1)} s</span>
      </div>

      <AnswerText text={result.answer} evidenceIds={result.condition === "llm_only" ? null : evidenceIds} onCite={onCite} />

      {result.condition !== "llm_only" && (
        <div className="metrics-row">
          <Metric label="citations valid" value={pct(v.citation_precision)} tone={v.invalid?.length ? "bad" : "good"} />
          <Metric label="claims cited" value={pct(v.grounded_ratio)} />
          <Metric label="invalid citations" value={v.invalid?.length ?? 0} tone={v.invalid?.length ? "bad" : ""} />
          {!compact && <Metric label="retrieval" value={`${Math.round(result.latency_ms.retrieval)} ms`} />}
          {!compact && <Metric label="generation" value={`${Math.round(result.latency_ms.generation)} ms`} />}
        </div>
      )}

      {result.evidence.length > 0 && (
        <details className="evidence-details" open={!compact}>
          <summary>Retrieved evidence ({result.evidence.length})</summary>
          <EvidenceList items={result.evidence} cited={v.valid || []} onOpen={onCite} />
        </details>
      )}
    </div>
  );
}
