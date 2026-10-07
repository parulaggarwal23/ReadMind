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
};

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
