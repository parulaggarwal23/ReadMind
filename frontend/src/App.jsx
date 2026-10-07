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
          <div className="logo" aria-hidden>⎇</div>
          <div>
            <h1>RepoHistory RAG</h1>
            <p>Evidence-based answers from code, commits, issues, PRs and reviews</p>
          </div>
        </div>
        <div className="topbar-right">
          <RepoSelector repos={repos} value={repo} onChange={setRepo} />
          <span className={`status ${health ? "ok" : "down"}`}>
            <span className="dot" />
            {health ? `${health.provider} · ${health.model}` : "API offline"}
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
