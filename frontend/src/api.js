const BASE = import.meta.env.VITE_API_URL || "/api";

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),
  repos: () => request("/repos"),
  ask: (body) => request("/ask", { method: "POST", body: JSON.stringify(body) }),
  compare: (body) => request("/compare", { method: "POST", body: JSON.stringify(body) }),
  evidence: (repo, id) =>
    request(`/evidence?repo=${encodeURIComponent(repo)}&id=${encodeURIComponent(id)}`),
  evalSummary: () => request("/eval/summary"),
  evalResults: () => request("/eval/results"),
  checkUpdates: (slug) => request(`/repos/${slug}/check-updates`),
  dismissUpdate: (slug) => request(`/repos/${slug}/dismiss-update`, { method: "POST" }),
  simulatePush: (slug, body = {}) => request(`/repos/${slug}/simulate-push`, { method: "POST", body: JSON.stringify(body) }),
  syncRepo: (slug) => request(`/repos/${slug}/sync`, { method: "POST" }),
  k8sStatus: () => request("/k8s/status"),
  k8sSimulateLoad: () => request("/k8s/simulate-load", { method: "POST" }),
  k8sResetLoad: () => request("/k8s/reset-load", { method: "POST" }),
  k8sManifests: () => request("/k8s/manifests"),
  engines: () => request("/engines"),
  sourcegraphStatus: () => request("/sourcegraph/status"),
  sourcegraphSearch: (body) => request("/sourcegraph/search", { method: "POST", body: JSON.stringify(body) }),
  sourcegraphLinks: (repo, id) =>
    request(`/sourcegraph/links?repo=${encodeURIComponent(repo)}&id=${encodeURIComponent(id)}`),
};

// RAG engine: ReadMind's own pipeline, or the same retrieval run through LangChain / LlamaIndex
export const ENGINES = [
  { id: "native", label: "ReadMind" },
  { id: "langchain", label: "LangChain" },
  { id: "llamaindex", label: "LlamaIndex" },
];

// Fixed order + fixed colour per condition (colour follows the condition, never its rank)
export const CONDITIONS = [
  { id: "llm_only", label: "LLM only", short: "LLM only", color: "var(--series-1)" },
  { id: "code_only", label: "LLM + current code", short: "+ Code", color: "var(--series-2)" },
  { id: "full_history", label: "LLM + code + history (RAG)", short: "+ History", color: "var(--series-3)" },
];

export const TYPE_LABELS = {
  code: "Code",
  doc: "Docs",
  commit: "Commit",
  issue: "Issue",
  pr: "Pull request",
  review: "Review",
};
