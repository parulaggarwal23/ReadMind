import { useEffect, useState } from "react";
import { api, CONDITIONS, ENGINES } from "../api";
import AnswerCard from "./AnswerCard";

const EXAMPLES = [
  "Why was the authentication logic implemented this way?",
  "Which issue led to the most recent change in the retry handling?",
  "Has this module had bugs before, and what caused them?",
  "What should I watch out for if I refactor the config loader?",
];

export default function AskPanel({ repo, onCite, prefill }) {
  const [question, setQuestion] = useState("");
  const [condition, setCondition] = useState("full_history");
  const [engine, setEngine] = useState("native");
  const [available, setAvailable] = useState({ native: true });

  // "Ask why" from the Code Navigation tab pre-fills the question
  useEffect(() => {
    if (prefill?.question) setQuestion(prefill.question);
  }, [prefill]);

  useEffect(() => {
    api
      .engines()
      .then((list) => setAvailable(Object.fromEntries(list.map((e) => [e.id, e.available]))))
      .catch(() => setAvailable({ native: true }));
  }, []);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function submit(e) {
    e?.preventDefault();
    if (question.trim().length < 3 || loading) return;
    setLoading(true);
    setError("");
    try {
      setResult(await api.ask({ repo, question, condition, engine }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="stack">
      <form className="card ask-form" onSubmit={submit}>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && submit()}
          placeholder="Ask why the code is the way it is… e.g. “Why does login rotate the session id?”"
          rows={3}
        />
        <div className="form-row">
          <div className="segmented" role="radiogroup" aria-label="Condition">
            {CONDITIONS.map((c) => (
              <button
                type="button"
                key={c.id}
                role="radio"
                aria-checked={condition === c.id}
                className={condition === c.id ? "seg active" : "seg"}
                onClick={() => setCondition(c.id)}
              >
                <span className="swatch" style={{ background: c.color }} />
                {c.label}
              </button>
            ))}
          </div>
          <label className="engine-select">
            <span className="muted">RAG engine</span>
            <select value={engine} onChange={(e) => setEngine(e.target.value)} aria-label="RAG engine">
              {ENGINES.map((en) => (
                <option key={en.id} value={en.id} disabled={available[en.id] === false}>
                  {en.label}
                  {available[en.id] === false ? " (not installed)" : ""}
                </option>
              ))}
            </select>
          </label>
          <button className="primary" disabled={loading || question.trim().length < 3}>
            {loading ? "Retrieving & answering…" : "Ask"}
          </button>
        </div>
        <div className="examples">
          {EXAMPLES.map((x) => (
            <button type="button" key={x} className="chip" onClick={() => setQuestion(x)}>
              {x}
            </button>
          ))}
        </div>
      </form>

      {error && <div className="alert error">{error}</div>}
      {loading && <div className="card skeleton" />}
      {result && !loading && <AnswerCard result={result} onCite={onCite} />}
    </div>
  );
}
