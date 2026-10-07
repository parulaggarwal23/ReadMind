import { useState } from "react";
import { api } from "../api";
import AnswerCard from "./AnswerCard";

export default function CompareView({ repo, onCite }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");

  async function run(e) {
    e.preventDefault();
    if (question.trim().length < 3) return;
    setLoading(true);
    setError("");
    try {
      setResults(await api.compare({ repo, question }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="stack">
      <form className="card compare-form" onSubmit={run}>
        <p className="muted">
          Runs the same question through all three experimental conditions with the same LLM, so you can
          see what repository history adds.
        </p>
        <div className="form-row">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Question to compare across conditions…"
          />
          <button className="primary" disabled={loading || question.trim().length < 3}>
            {loading ? "Running 3 conditions…" : "Compare"}
          </button>
        </div>
      </form>
      {error && <div className="alert error">{error}</div>}
      {loading && (
        <div className="compare-grid">
          {[0, 1, 2].map((i) => <div key={i} className="card skeleton" />)}
        </div>
      )}
      {results && !loading && (
        <div className="compare-grid">
          {results.map((r) => (
            <AnswerCard key={r.condition} result={r} onCite={onCite} compact />
          ))}
        </div>
      )}
    </div>
  );
}
