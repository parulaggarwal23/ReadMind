import { useEffect, useState } from "react";
import { api } from "./api";
import RepoSelector from "./components/RepoSelector";
import AskPanel from "./components/AskPanel";
import CompareView from "./components/CompareView";
import EvalDashboard from "./components/EvalDashboard";
import EvidenceDrawer from "./components/EvidenceDrawer";
import HeroExplanation from "./components/HeroExplanation";
import KnowledgeBaseView from "./components/KnowledgeBaseView";

const TABS = [
  { id: "knowledge", label: "Knowledge Base" },
  { id: "ask", label: "Ask" },
  { id: "compare", label: "Compare conditions" },
  { id: "eval", label: "Evaluation" },
];

export default function App() {
  const [repos, setRepos] = useState([]);
  const [repo, setRepo] = useState("");
  const [tab, setTab] = useState("knowledge");
  const [health, setHealth] = useState(null);
  const [activeModel, setActiveModel] = useState("gemini-2.5-flash");
  const [error, setError] = useState("");
  const [evidenceId, setEvidenceId] = useState(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api
      .repos()
      .then((list) => {
        setRepos(list);
        if (list.length) setRepo(list[0].slug);
      })
      .catch((e) => setError(`Cannot reach the backend: ${e.message}`));
  }, []);

  const current = repos.find((r) => r.slug === repo);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="logo" aria-hidden>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" />
              <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" />
            </svg>
          </div>
          <div>
            <h1>ReadMind</h1>
          </div>
        </div>
        <div className="topbar-right">
          <RepoSelector repos={repos} value={repo} onChange={setRepo} />
          <span className={`status ${health ? "ok" : "down"}`}>
            <span className="dot" />
            <select 
              value={activeModel} 
              onChange={(e) => setActiveModel(e.target.value)}
              style={{ background: 'transparent', border: 'none', color: 'inherit', font: 'inherit', outline: 'none', cursor: 'pointer' }}
            >
              <option value="gemini-2.5-flash">gemini · gemini-2.5-flash</option>
              <option value="qwen2.5-coder:7b">ollama · qwen2.5-coder:7b</option>
              <option value="claude-3-5-sonnet">anthropic · claude-3-5-sonnet</option>
            </select>
          </span>
        </div>
      </header>

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={tab === t.id ? "tab active" : "tab"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
        {current && (
          <span className="repo-stats">
            {Object.entries(current.counts)
              .map(([k, v]) => `${v.toLocaleString()} ${k}`)
              .join(" · ")}
          </span>
        )}
      </nav>

      <main>
        {error && <div className="alert error">{error}</div>}
        {!error && repos.length === 0 && tab !== "eval" && (
          <div className="alert">
            No indexed repositories yet. Add your repos to <code>backend/repos.yaml</code> and run{" "}
            <code>python -m ingestion.run_ingestion --repo all</code>.
          </div>
        )}
        {repo && (
          <>
            <div hidden={tab !== "knowledge"}>
              <KnowledgeBaseView currentRepo={current} repos={repos} onSelectRepo={setRepo} />
            </div>
            <div hidden={tab !== "ask"}>
              <AskPanel repo={repo} onCite={setEvidenceId} />
            </div>
            <div hidden={tab !== "compare"}>
              <CompareView repo={repo} onCite={setEvidenceId} />
            </div>
          </>
        )}
        {tab === "eval" && <EvalDashboard />}
      </main>

      {evidenceId && (
        <EvidenceDrawer
          repo={repo}
          docId={evidenceId}
          onNavigate={setEvidenceId}
          onClose={() => setEvidenceId(null)}
        />
      )}
    </div>
  );
}
