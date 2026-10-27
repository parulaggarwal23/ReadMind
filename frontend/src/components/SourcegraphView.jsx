import { useEffect, useState } from "react";
import { api } from "../api";

// Sourcegraph = WHERE / WHAT (code search + precise navigation); ReadMind = WHY (history RAG).
const MODES = [
  { id: "keyword", label: "Code" },
  { id: "symbol", label: "Symbols" },
  { id: "structural", label: "Structural" },
  { id: "regexp", label: "Regex" },
  { id: "commit", label: "Commits" },
];

const PRESETS = [
  { mode: "symbol", query: "auth", label: "Symbols named auth*" },
  { mode: "keyword", query: "retry timeout", label: "Retry / timeout logic" },
  { mode: "structural", query: "try { ... } catch (:[e]) { }", label: "Empty catch blocks (JS/C)" },
  { mode: "regexp", query: "TODO|FIXME|HACK", label: "TODO / FIXME markers" },
  { mode: "commit", query: "fix", label: "Commits mentioning fix" },
];

export default function SourcegraphView({ repo, onAskWhy }) {
  const [status, setStatus] = useState(null);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("keyword");
  const [scope, setScope] = useState(repo ? "repo" : "all");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.sourcegraphStatus().then(setStatus).catch(() => setStatus({ reachable: false }));
  }, []);

  async function run(e, preset) {
    e?.preventDefault();
    const q = preset ? preset.query : query;
    const m = preset ? preset.mode : mode;
    if (preset) {
      setQuery(preset.query);
      setMode(preset.mode);
    }
    if (!q.trim() || loading) return;
    setLoading(true);
    setError("");
    try {
      setResult(await api.sourcegraphSearch({ query: q, mode: m, repo: scope === "repo" && repo ? repo : null }));
    } catch (err) {
      setError(err.message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="stack">
      <div className="card sg-head">
        <div>
          <h2 className="sg-title">Semantic code navigation · Sourcegraph</h2>
          <p className="muted small">
            Find <em>where</em> code lives across the indexed repositories, then ask ReadMind <em>why</em> it is
            that way. Go-to-definition and find-references use SCIP indexes uploaded by CI.
          </p>
        </div>
        <span className={`status ${status?.reachable ? "ok" : "down"}`}>
          <span className="dot" />
          {status === null
            ? "checking…"
            : status.reachable
              ? `Sourcegraph ${status.version}`
              : "Sourcegraph offline"}
        </span>
      </div>

      {status && !status.reachable && (
        <div className="alert">
          Sourcegraph is not reachable at <code>{status.url}</code>. Start it with{" "}
          <code>docker compose -f docker-compose.yml -f docker-compose.sourcegraph.yml up -d sourcegraph</code> and
          follow <code>sourcegraph/README.md</code>.
        </div>
      )}

      {status?.mode === "integrated" && (
        <div className="alert info" style={{ background: "rgba(56, 189, 248, 0.08)", borderColor: "rgba(56, 189, 248, 0.3)", color: "var(--text-1)" }}>
          ⚡ <strong>Integrated SCIP Semantic Engine Active</strong> — High-precision symbol, structural, regex, code, and commit navigation is running across all indexed repositories with direct repository links.
        </div>
      )}

      <form className="card" onSubmit={run}>
        <div className="form-row">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search code, symbols or commits… e.g. RepoIndex, session rotate, type:symbol retrieve"
          />
          <button className="primary" disabled={loading || !query.trim()}>
            {loading ? "Searching…" : "Search"}
          </button>
        </div>
        <div className="form-row sg-options">
          <div className="segmented" role="radiogroup" aria-label="Search mode">
            {MODES.map((m) => (
              <button
                type="button"
                key={m.id}
                role="radio"
                aria-checked={mode === m.id}
                className={mode === m.id ? "seg active" : "seg"}
                onClick={() => setMode(m.id)}
              >
                {m.label}
              </button>
            ))}
          </div>
          <select value={scope} onChange={(e) => setScope(e.target.value)} aria-label="Scope">
            <option value="repo" disabled={!repo}>Selected repo{repo ? ` (${repo})` : ""}</option>
            <option value="all">All repositories</option>
          </select>
        </div>
        <div className="examples">
          {PRESETS.map((p) => (
            <button type="button" key={p.label} className="chip" onClick={(e) => run(e, p)}>
              {p.label}
            </button>
          ))}
        </div>
      </form>

      {error && <div className="alert error">{error}</div>}
      {loading && <div className="card skeleton" />}

      {result && !loading && (
        <div className="card">
          <div className="sg-result-head">
            <span className="muted small">
              {result.match_count.toLocaleString()} matches{result.limit_hit ? " (limit hit)" : ""} ·{" "}
              <code className="mono small">{result.query}</code>
            </span>
            <a className="gh-link" href={result.web_url} target="_blank" rel="noreferrer">
              Open in Sourcegraph ↗
            </a>
          </div>
          {result.results.length === 0 && <p className="muted">No matches.</p>}
          <ul className="sg-results">
            {result.results.map((r, i) =>
              r.kind === "commit" ? (
                <li key={`c-${r.sha}-${i}`}>
                  <a href={r.url} target="_blank" rel="noreferrer" className="sg-path">
                    <span className="type-badge t-commit">Commit</span> {r.subject}
                  </a>
                  <div className="muted mono small">
                    {r.sha.slice(0, 10)} · {r.author} · {r.date?.slice(0, 10)}
                  </div>
                </li>
              ) : (
                <li key={`f-${r.repo}-${r.path}-${i}`}>
                  <div className="sg-file-row">
                    <a href={r.url} target="_blank" rel="noreferrer" className="sg-path mono">
                      {scope === "all" && <span className="muted">{r.repo.replace("github.com/", "")} · </span>}
                      {r.path}
                    </a>
                    {onAskWhy && repo && (
                      <button
                        type="button"
                        className="chip"
                        onClick={() => onAskWhy(`Why is ${r.path} implemented the way it is?`)}
                        title="Ask ReadMind (history RAG) about this file"
                      >
                        Ask why →
                      </button>
                    )}
                  </div>
                  {r.symbols.length > 0 && (
                    <div className="sg-symbols">
                      {r.symbols.map((s) => (
                        <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="chip mono">
                          {s.kind.toLowerCase()} {s.name}
                        </a>
                      ))}
                    </div>
                  )}
                  {r.lines.length > 0 && (
                    <pre className="sg-lines">
                      {r.lines.map((l) => `${String(l.line).padStart(5)}  ${l.preview}`).join("\n")}
                    </pre>
                  )}
                </li>
              ),
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
