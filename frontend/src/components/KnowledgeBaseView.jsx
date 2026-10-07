import React from "react";

export default function KnowledgeBaseView({ currentRepo, repos, onSelectRepo }) {
  const [repoInput, setRepoInput] = React.useState("");
  const [isValidating, setIsValidating] = React.useState(false);
  const [modalData, setModalData] = React.useState(null);
  const [modalTitle, setModalTitle] = React.useState("");
  const [modalType, setModalType] = React.useState("");
  const [modalPage, setModalPage] = React.useState(0);
  const [modalLoading, setModalLoading] = React.useState(false);

  const fetchModalData = async (type, newPage, title) => {
    try {
      setModalLoading(true);
      if (title) setModalTitle(title);
      setModalType(type);
      
      // If we don't have data yet, show a loading placeholder
      if (!modalData) {
        setModalData({ status: "fetching data from backend..." });
      }
      
      const url = `/api/repos/${currentRepo.slug}/sample-${type}?skip=${newPage * 10}&limit=10`;
      const res = await fetch(url);
      const data = await res.json();
      
      setModalData(data);
      setModalPage(newPage);
    } catch (e) {
      alert("Error: " + e.message);
      setModalData(null);
    } finally {
      setModalLoading(false);
    }
  };

  const handleVerifyRepo = async () => {
    let trimmed = repoInput.trim();
    if (!trimmed) {
      alert("Please enter a repository name (e.g., facebook/react)");
      return;
    }

    // If the user pasted a full URL, extract just the owner/repo part
    if (trimmed.includes("github.com/")) {
      try {
        const urlObj = new URL(trimmed.startsWith("http") ? trimmed : `https://${trimmed}`);
        const pathParts = urlObj.pathname.split("/").filter(Boolean);
        if (pathParts.length >= 2) {
          trimmed = `${pathParts[0]}/${pathParts[1]}`;
        }
      } catch (e) {
        // Fallback if URL parsing fails
        trimmed = trimmed.split("github.com/")[1].split("/").slice(0, 2).join("/");
      }
    }

    // Remove any trailing .git
    if (trimmed.endsWith(".git")) {
      trimmed = trimmed.replace(".git", "");
    }

    setIsValidating(true);
    try {
      const res = await fetch(`https://api.github.com/repos/${trimmed}`);
      if (res.status === 404) {
        alert(`❌ Repository '${trimmed}' was not found on GitHub. Please check the spelling!`);
        setIsValidating(false);
      } else if (res.ok) {
        // Now trigger the actual ingestion
        setIsValidating(true); // Keep it loading
        try {
          // Note: This fetch will block until the backend finishes ingesting (which can take minutes)
          const ingestRes = await fetch("/api/ingest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ repo: trimmed })
          });
          
          if (ingestRes.ok) {
            alert(`✅ Ingestion Complete!\n\nThe Knowledge Base has been successfully updated with the history of ${trimmed}.\n\nThe page will now refresh to show the new stats.`);
            window.location.reload();
          } else {
            const err = await ingestRes.text();
            alert(`⚠️ Ingestion failed: ${err}`);
            setIsValidating(false);
          }
        } catch (ingestErr) {
          alert(`⚠️ Error communicating with backend for ingestion: ${ingestErr.message}`);
          setIsValidating(false);
        }
      } else {
        alert("⚠️ Could not verify repository due to API limits. Try again later.");
        setIsValidating(false);
      }
    } catch (e) {
      alert("Network error while trying to reach GitHub.");
      setIsValidating(false);
    }
  };

  if (!currentRepo) return null;

  const { counts, total } = currentRepo;

  const dataSources = [
    {
      title: "Source Code & Docs",
      icon: "📄",
      count: counts.code || 0,
      description: "Functions, classes, and documentation extracted directly from the repository files.",
      color: "var(--t-code)"
    },
    {
      title: "Git Commits",
      icon: "📦",
      count: counts.commit || 0,
      description: "Historical commit messages and code diffs showing how the code evolved over time.",
      color: "var(--t-commit)"
    },
    {
      title: "Pull Requests",
      icon: "🔄",
      count: counts.pr || 0,
      description: "PR titles, descriptions, and the discussions that happened before code was merged.",
      color: "var(--t-pr)"
    },
    {
      title: "GitHub Issues",
      icon: "🐛",
      count: counts.issue || 0,
      description: "Bug reports, feature requests, and developer conversations about problems.",
      color: "var(--t-issue)"
    },
    {
      title: "Code Reviews",
      icon: "👀",
      count: counts.review || 0,
      description: "Inline comments left by reviewers on specific lines of code.",
      color: "var(--t-review)"
    }
  ];

  return (
    <div className="kb-view stack">
      <div className="glass-card" style={{ padding: "24px", marginBottom: "10px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "20px" }}>
        <div style={{ flex: 1, minWidth: "300px" }}>
          <h3 style={{ margin: "0 0 8px 0", color: "var(--accent)" }}>✨ Add Your Own Repository</h3>
          <p style={{ margin: "0 0 16px 0", fontSize: "14px", color: "var(--text-2)" }}>
            Enter a public GitHub repository link to download its complete history into the Knowledge Base.
          </p>
          <div style={{ display: "flex", gap: "10px" }}>
            <input 
              type="text" 
              placeholder="e.g. parulaggarwal23/PolicyPal-AI" 
              value={repoInput}
              onChange={e => setRepoInput(e.target.value)}
              style={{ flex: 1, maxWidth: "350px", background: "var(--surface-2)" }}
            />
            <button 
              className="primary"
              onClick={handleVerifyRepo}
              disabled={isValidating}
            >
              {isValidating ? "Downloading History (Takes 1-3 mins)..." : "Verify & Add"}
            </button>
          </div>
        </div>
      </div>

      <div className="glass-card" style={{ padding: "24px" }}>
        <h3 style={{ margin: "0 0 16px 0" }}>Currently Loaded Repositories</h3>
        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
          {repos.map(r => (
            <button
              key={r.slug}
              className={`seg ${currentRepo.slug === r.slug ? "active" : ""}`}
              onClick={() => onSelectRepo(r.slug)}
              style={{
                background: currentRepo.slug === r.slug ? "var(--accent)" : "var(--surface-2)",
                color: currentRepo.slug === r.slug ? "var(--accent-ink)" : "var(--text-1)",
                border: "none", padding: "10px 16px", borderRadius: "8px", fontWeight: "600",
                cursor: "pointer", transition: "all 0.2s"
              }}
            >
              {r.slug}
            </button>
          ))}
        </div>
      </div>

      <div className="kb-header glass-card" style={{ padding: "30px", textAlign: "center", marginTop: "20px", position: "relative" }}>
        <h2>Knowledge Base Stats: <code>{currentRepo.slug}</code></h2>
        <button 
          style={{ 
            position: "absolute", top: "20px", right: "20px",
            padding: "8px 12px", background: "rgba(239, 68, 68, 0.15)", color: "#ef4444", 
            border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "6px", cursor: "pointer", 
            fontWeight: "bold", transition: "all 0.2s"
          }}
          onMouseOver={e => e.currentTarget.style.background = "rgba(239, 68, 68, 0.25)"}
          onMouseOut={e => e.currentTarget.style.background = "rgba(239, 68, 68, 0.15)"}
          onClick={async () => {
            if (window.confirm(`Are you sure you want to completely remove ${currentRepo.slug} from the Knowledge Base?`)) {
              try {
                const res = await fetch(`/api/repos/${currentRepo.slug}`, { method: 'DELETE' });
                if (res.ok) {
                  window.location.reload();
                } else {
                  alert("Failed to delete repository.");
                }
              } catch (err) {
                alert("Network error.");
              }
            }
          }}
        >
          🗑️ Delete Repo
        </button>
        <p className="muted">This is the exact data indexed and linked in the graph for the AI to retrieve.</p>
      </div>

      <div className="kb-grid">
        {dataSources.map((source, i) => (
          <div key={i} className="glass-card kb-card" style={{ borderTop: `4px solid ${source.color}` }}>
            <div className="kb-card-header">
              <span className="kb-icon">{source.icon}</span>
              <h3>{source.title}</h3>
            </div>
            <div className="kb-count" style={{ color: source.color }}>
              {source.count.toLocaleString()} <span style={{fontSize: "14px", color: "var(--text-2)"}}>items</span>
            </div>
            <p className="kb-desc">{source.description}</p>
          </div>
        ))}
      </div>

      <div className="glass-card" style={{ padding: "30px", marginTop: "30px", borderTop: "4px solid var(--accent)" }}>
        <h3 style={{ margin: "0 0 16px 0", color: "var(--accent)", display: "flex", alignItems: "center", gap: "10px" }}>
          <span>🧠</span> RAG Architecture & Technical Internals
        </h3>
        <p style={{ color: "var(--text-secondary)", marginBottom: "24px", lineHeight: "1.5" }}>
          This section exposes the underlying technical architecture of the Knowledge Base. 
          These metrics demonstrate how the repository history is processed, chunked, and stored for AI retrieval.
        </p>

        <div style={{ display: "flex", gap: "20px", flexWrap: "wrap" }}>
          <div 
            className="glass-card" 
            style={{ flex: 1, minWidth: "200px", background: "var(--surface-2)", padding: "20px", textAlign: "center", cursor: "pointer", transition: "all 0.2s" }}
            onClick={() => fetchModalData("chunks", 0, `Sample Document Chunks`)}
            onMouseOver={e => e.currentTarget.style.background = "var(--surface-3)"}
            onMouseOut={e => e.currentTarget.style.background = "var(--surface-2)"}
            title="Click to view raw chunk data"
          >
            <h4 style={{ margin: "0 0 8px 0", color: "var(--text-2)", fontSize: "14px", textTransform: "uppercase", letterSpacing: "1px" }}>Total Document Chunks</h4>
            <div style={{ fontSize: "2.5rem", fontWeight: "800", color: "var(--text-1)" }}>
              {total.toLocaleString()}
            </div>
            <p style={{ fontSize: "12px", color: "var(--text-3)", marginTop: "8px" }}>
              Parsed nodes (Click to view samples)
            </p>
          </div>

          <div 
            className="glass-card" 
            style={{ flex: 1, minWidth: "200px", background: "var(--surface-2)", padding: "20px", textAlign: "center", cursor: "pointer", transition: "all 0.2s" }}
            onClick={() => fetchModalData("embeddings", 0, `Sample Vector Embeddings`)}
            onMouseOver={e => e.currentTarget.style.background = "var(--surface-3)"}
            onMouseOut={e => e.currentTarget.style.background = "var(--surface-2)"}
            title="Click to view raw vector embeddings"
          >
            <h4 style={{ margin: "0 0 8px 0", color: "var(--text-2)", fontSize: "14px", textTransform: "uppercase", letterSpacing: "1px" }}>Vector Embeddings</h4>
            <div style={{ fontSize: "2.5rem", fontWeight: "800", color: "var(--text-1)" }}>
              {total.toLocaleString()}
            </div>
            <p style={{ fontSize: "12px", color: "var(--text-3)", marginTop: "8px" }}>
              Stored in ChromaDB (Click to view)
            </p>
          </div>

          <div className="glass-card" style={{ flex: 1, minWidth: "200px", background: "var(--surface-2)", padding: "20px", textAlign: "center" }}>
            <h4 style={{ margin: "0 0 8px 0", color: "var(--text-2)", fontSize: "14px", textTransform: "uppercase", letterSpacing: "1px" }}>Vector Dimensions</h4>
            <div style={{ fontSize: "2.5rem", fontWeight: "800", color: "var(--text-1)" }}>
              384
            </div>
            <p style={{ fontSize: "12px", color: "var(--text-3)", marginTop: "8px" }}>
              Dense vectors (BAAI/bge-small-en-v1.5)
            </p>
          </div>
          
          <div className="glass-card" style={{ flex: 1, minWidth: "200px", background: "var(--surface-2)", padding: "20px", textAlign: "center", display: "flex", flexDirection: "column", justifyContent: "center" }}>
            <h4 style={{ margin: "0 0 8px 0", color: "var(--text-2)", fontSize: "14px", textTransform: "uppercase", letterSpacing: "1px" }}>Retrieval Strategy</h4>
            <div style={{ fontSize: "1.1rem", fontWeight: "bold", color: "var(--text-1)", lineHeight: "1.4" }}>
              BM25 + Vector + Graph
            </div>
            <p style={{ fontSize: "12px", color: "var(--text-3)", marginTop: "8px" }}>
              Reciprocal Rank Fusion (RRF)
            </p>
          </div>
        </div>
      </div>

      {modalData && (
        <div style={{ position: "fixed", top: 0, left: 0, width: "100%", height: "100%", background: "rgba(0,0,0,0.8)", display: "flex", justifyContent: "center", alignItems: "center", zIndex: 1000 }}>
          <div className="glass-card" style={{ width: "90%", maxWidth: "1000px", height: "85%", padding: "30px", overflow: "hidden", display: "flex", flexDirection: "column", position: "relative", background: "var(--surface-1)" }}>
            <button 
              onClick={() => setModalData(null)} 
              style={{ position: "absolute", top: "20px", right: "20px", background: "var(--surface-2)", color: "var(--text-1)", padding: "8px 16px", borderRadius: "6px", cursor: "pointer", border: "1px solid var(--border)", fontWeight: "bold" }}
            >
              Close
            </button>
            <h2 style={{ marginTop: 0, color: "var(--text-1)", marginBottom: "8px", display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ color: "var(--accent)" }}>{modalTitle.includes("Embeddings") ? "🔢" : "📄"}</span> 
              {modalTitle}
            </h2>
            <p style={{ color: "var(--text-2)", marginBottom: "20px", fontSize: "14px", borderBottom: "1px solid var(--border)", paddingBottom: "16px" }}>
              Showing {modalPage * 10 + 1} to {Math.min((modalPage + 1) * 10, total)} of {total.toLocaleString()} indexed items
            </p>
            
            <div style={{ overflowY: "auto", flex: 1, paddingRight: "10px", display: "flex", flexDirection: "column", gap: "16px", opacity: modalLoading ? 0.5 : 1, transition: "opacity 0.2s" }}>
              {Array.isArray(modalData) ? modalData.map((item, index) => (
                <div key={index} style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "8px", overflow: "hidden", display: "flex", flexShrink: 0 }}>
                  <div style={{ background: "var(--surface-3)", padding: "20px", width: "60px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "20px", fontWeight: "bold", color: "var(--accent)", borderRight: "1px solid var(--border)", flexShrink: 0 }}>
                    {modalPage * 10 + index + 1}
                  </div>
                  <div style={{ padding: "20px", flex: 1, overflow: "hidden" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "16px", alignItems: "center" }}>
                      <span style={{ fontSize: "12px", fontWeight: "bold", color: "var(--accent)", background: "var(--surface-3)", padding: "6px 12px", borderRadius: "6px", textTransform: "uppercase", letterSpacing: "1px" }}>
                        TYPE: {item.type || "unknown"}
                      </span>
                      <span style={{ fontSize: "13px", color: "var(--text-3)", fontFamily: "monospace", background: "rgba(0,0,0,0.2)", padding: "4px 8px", borderRadius: "4px" }}>
                        ID: {item.id}
                      </span>
                    </div>
                    
                    {item.embedding ? (
                      <div>
                        <div style={{ fontSize: "13px", color: "var(--text-2)", marginBottom: "8px", fontWeight: "600" }}>384-Dimensional Vector Array (Dense):</div>
                        <pre style={{ margin: 0, background: "#0a0a0a", padding: "16px", borderRadius: "8px", color: "#a8c7fa", fontSize: "14px", whiteSpace: "pre-wrap", wordBreak: "break-all", border: "1px solid #222" }}>
                          [{item.embedding.join(", ")}]
                        </pre>
                      </div>
                    ) : (
                      <div>
                        {item.title && <h4 style={{ margin: "0 0 12px 0", color: "var(--text-1)", fontSize: "16px" }}>{item.title}</h4>}
                        <pre style={{ margin: 0, background: "#0a0a0a", padding: "16px", borderRadius: "8px", color: "#e2e8f0", fontSize: "13.5px", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: "350px", overflowY: "auto", border: "1px solid #222", lineHeight: "1.5" }}>
                          {item.text}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              )) : (
                <div style={{ color: "var(--text-2)", textAlign: "center", padding: "40px" }}>
                  Loading data from backend...
                </div>
              )}
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "20px", paddingTop: "20px", borderTop: "1px solid var(--border)" }}>
              <button 
                disabled={modalPage === 0 || modalLoading}
                onClick={() => fetchModalData(modalType, modalPage - 1)}
                style={{ padding: "8px 16px", background: "var(--surface-2)", color: "var(--text-1)", border: "1px solid var(--border)", borderRadius: "6px", cursor: modalPage === 0 ? "not-allowed" : "pointer", opacity: modalPage === 0 ? 0.5 : 1, fontWeight: "bold" }}
              >
                ← Previous 10
              </button>
              <div style={{ color: "var(--text-2)", display: "flex", alignItems: "center", fontWeight: "bold" }}>
                Page {modalPage + 1}
              </div>
              <button 
                disabled={!Array.isArray(modalData) || modalData.length < 10 || modalLoading}
                onClick={() => fetchModalData(modalType, modalPage + 1)}
                style={{ padding: "8px 16px", background: "var(--surface-2)", color: "var(--text-1)", border: "1px solid var(--border)", borderRadius: "6px", cursor: (!Array.isArray(modalData) || modalData.length < 10) ? "not-allowed" : "pointer", opacity: (!Array.isArray(modalData) || modalData.length < 10) ? 0.5 : 1, fontWeight: "bold" }}
              >
                Next 10 →
              </button>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}
