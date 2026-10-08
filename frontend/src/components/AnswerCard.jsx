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
    let cleanError = result.error;
    if (result.error.includes("429") || result.error.includes("RESOURCE_EXHAUSTED")) {
      cleanError = "API Rate Limit Exceeded (429). The Gemini API free tier limits requests per minute/day. Please wait a moment and try again, or use a different API key.";
    }

    return (
      <div className="card answer-card">
        <div className="answer-head">
          <span className="cond-tag" style={{ "--c": cond?.color }}>{result.condition_label}</span>
        </div>
        <div className="alert error" style={{ padding: '15px', lineHeight: '1.5' }}>
          <strong>Error: </strong> {cleanError}
        </div>
      </div>
    );
  }

  // Define the pipeline steps based on the condition
  const getPipelineSteps = (condition) => {
    switch(condition) {
      case 'llm_only':
        return [
          { title: "User Query Received", desc: `Input received: "${result.question}"` },
          { title: "Direct LLM Prompting", desc: "The query is sent directly to the Gemini LLM with zero external context." },
          { title: "Response Generation", desc: `The LLM synthesized an answer using only its pre-trained baseline knowledge in ${result.latency_ms.generation}ms.` }
        ];
      case 'code_only':
        return [
          { title: "User Query Received", desc: `Input received: "${result.question}"` },
          { title: "Query Embedding", desc: "The query was embedded into a vector space using the local intfloat/e5-small-v2 model." },
          { title: "Vector Search (ChromaDB)", desc: `Searched ChromaDB and retrieved ${result.evidence.length} relevant AST code chunks in ${result.latency_ms.retrieval}ms.` },
          { title: "Prompt Construction", desc: `Injected the ${result.evidence.length} code chunks into the context prompt.` },
          { title: "Response Generation", desc: `The Gemini LLM synthesized an answer using the provided code context in ${result.latency_ms.generation}ms.` }
        ];
      case 'full_history':
        return [
          { title: "User Query Received", desc: `Input received: "${result.question}"` },
          { title: "Query Embedding", desc: "The query was embedded into a vector space using the local intfloat/e5-small-v2 model." },
          { title: "Vector Search (ChromaDB)", desc: "Searched ChromaDB and retrieved the most relevant AST code chunks based on semantic similarity." },
          { title: "Knowledge Graph Traversal", desc: `Traversed the NetworkX directed graph to find linked Git Commits, Pull Requests, and Issue discussions, yielding ${result.evidence.length} total evidence nodes in ${result.latency_ms.retrieval}ms.` },
          { title: "Prompt Construction", desc: `Injected all ${result.evidence.length} evidence nodes into the historical context prompt.` },
          { title: "Response Generation", desc: `The Gemini LLM synthesized a highly accurate, evidence-based answer in ${result.latency_ms.generation}ms.` }
        ];
      default:
        return [];
    }
  };

  const steps = getPipelineSteps(result.condition);
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

      <details className="working-details" open={!compact}>
        <summary>⚙️ View Working Pipeline</summary>
        <div className="working-content">
          
          <div className="pipeline-timeline">
            {steps.map((step, idx) => (
              <div className="pipeline-step" key={idx}>
                <div className="step-number">{idx + 1}</div>
                <div className="step-content">
                  <div className="step-title">{step.title}</div>
                  <div className="step-desc">{step.desc}</div>
                </div>
              </div>
            ))}
          </div>

          {result.condition !== "llm_only" && (
            <>
              <h4 style={{ margin: '20px 0 10px 0', fontSize: '0.9em', color: 'var(--text-2)' }}>Backend Metrics</h4>
              <div className="metrics-row">
                <Metric label="citations valid" value={pct(v.citation_precision)} tone={v.invalid?.length ? "bad" : "good"} />
                <Metric label="claims cited" value={pct(v.grounded_ratio)} />
                <Metric label="invalid citations" value={v.invalid?.length ?? 0} tone={v.invalid?.length ? "bad" : ""} />
                {!compact && <Metric label="retrieval" value={`${Math.round(result.latency_ms.retrieval)} ms`} />}
                {!compact && <Metric label="generation" value={`${Math.round(result.latency_ms.generation)} ms`} />}
              </div>
            </>
          )}

          {result.evidence && result.evidence.length > 0 && (
            <div className="evidence-section" style={{ marginTop: '20px' }}>
              <h4 style={{ margin: '0 0 10px 0', fontSize: '0.9em', color: 'var(--text-2)' }}>Retrieved evidence ({result.evidence.length})</h4>
              <EvidenceList items={result.evidence} cited={v.valid || []} onOpen={onCite} />
            </div>
          )}
        </div>
      </details>
    </div>
  );
}
