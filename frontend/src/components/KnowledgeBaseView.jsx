import React from "react";

export default function KnowledgeBaseView({ currentRepo, repos, onSelectRepo }) {
  const [repoInput, setRepoInput] = React.useState("");
  const [isValidating, setIsValidating] = React.useState(false);
  
  // Modal state
  const [modalData, setModalData] = React.useState(null);
  const [modalTitle, setModalTitle] = React.useState("");
  const [modalType, setModalType] = React.useState("");
  const [modalEndpoint, setModalEndpoint] = React.useState("chunks");
  const [modalTotal, setModalTotal] = React.useState(0);
  const [modalPage, setModalPage] = React.useState(0);
  const [modalLoading, setModalLoading] = React.useState(false);
  const [modalIcon, setModalIcon] = React.useState("📄");
  const [modalColor, setModalColor] = React.useState("var(--accent)");
  const [filterQuery, setFilterQuery] = React.useState("");

  const fetchModalData = async ({
    endpoint = "chunks",
    type = null,
    page = 0,
    title = null,
    icon = "📄",
    color = "var(--accent)",
    totalCount = 0
  }) => {
    try {
      setModalLoading(true);
      if (title) setModalTitle(title);
      if (icon) setModalIcon(icon);
      if (color) setModalColor(color);
      setModalEndpoint(endpoint);
      setModalType(type || "");
      if (totalCount) setModalTotal(totalCount);
      
      let url = "";
      if (endpoint === "embeddings") {
        url = `/api/repos/${currentRepo.slug}/sample-embeddings?skip=${page * 10}&limit=10`;
      } else {
        const typeParam = type && type !== "all" ? `&type=${encodeURIComponent(type)}` : "";
        url = `/api/repos/${currentRepo.slug}/sample-chunks?skip=${page * 10}&limit=10${typeParam}`;
      }
      
      const res = await fetch(url);
      const data = await res.json();
      
      if (Array.isArray(data)) {
        setModalData(data);
        if (!totalCount) setModalTotal(data.length);
      } else {
        setModalData(data.items || []);
        if (data.total !== undefined) {
          setModalTotal(data.total);
        }
      }
      setModalPage(page);
    } catch (e) {
      alert("Error: " + e.message);
      setModalData(null);
    } finally {
      setModalLoading(false);
    }
  };

  // Close modal on Escape key, navigate on arrows
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if (!modalData) return;
      if (e.key === "Escape") {
        setModalData(null);
        setFilterQuery("");
      } else if (e.key === "ArrowLeft" && modalPage > 0 && !modalLoading) {
        fetchModalData({
          endpoint: modalEndpoint,
          type: modalType,
          page: modalPage - 1,
          title: modalTitle,
          icon: modalIcon,
          color: modalColor,
          totalCount: modalTotal
        });
      } else if (e.key === "ArrowRight" && (modalPage + 1) * 10 < modalTotal && !modalLoading) {
        fetchModalData({
          endpoint: modalEndpoint,
          type: modalType,
          page: modalPage + 1,
          title: modalTitle,
          icon: modalIcon,
          color: modalColor,
          totalCount: modalTotal
        });
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [modalData, modalPage, modalLoading, modalEndpoint, modalType, modalTitle, modalIcon, modalColor, modalTotal]);

  const handleVerifyRepo = async () => {
    let trimmed = repoInput.trim();
    if (!trimmed) {
      alert("Please enter a repository name (e.g., facebook/react)");
      return;
    }

    if (trimmed.includes("github.com/")) {
      try {
        const urlObj = new URL(trimmed.startsWith("http") ? trimmed : `https://${trimmed}`);
        const pathParts = urlObj.pathname.split("/").filter(Boolean);
        if (pathParts.length >= 2) {
          trimmed = `${pathParts[0]}/${pathParts[1]}`;
        }
      } catch (e) {
        trimmed = trimmed.split("github.com/")[1].split("/").slice(0, 2).join("/");
      }
    }

    if (trimmed.endsWith(".git")) {
      trimmed = trimmed.replace(".git", "");
    }

    setIsValidating(true);
    try {
      const verifyRes = await fetch(`/api/repos/verify-github?repo=${encodeURIComponent(trimmed)}`);
      const verifyData = await verifyRes.json();
      
      if (!verifyData.valid) {
        alert(verifyData.error || `❌ Repository '${trimmed}' could not be verified on GitHub.`);
        setIsValidating(false);
        return;
      }
      
      const targetRepo = verifyData.repo || trimmed;
      const ingestRes = await fetch("/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo: targetRepo })
      });
      
      if (ingestRes.ok) {
        const result = await ingestRes.json();
        alert(`✅ Ingestion Complete!\n\nThe Knowledge Base has been successfully updated with the history of ${targetRepo}.\n\nThe page will now refresh to show the new stats.`);
        window.location.reload();
      } else {
        const err = await ingestRes.text();
        alert(`⚠️ Ingestion failed: ${err}`);
        setIsValidating(false);
      }
    } catch (e) {
      alert(`⚠️ Network error: ${e.message}`);
      setIsValidating(false);
    }
  };

  if (!currentRepo) return null;

  const { counts = {}, total = 0 } = currentRepo;
  const codeDocsCount = (counts.code || 0) + (counts.doc || 0);

  const dataSources = [
    {
      title: "Source Code & Docs",
      icon: "📄",
      type: "code,doc",
      count: codeDocsCount || (counts.code || 0),
      description: "Functions, classes, and documentation extracted directly from the repository files.",
      color: "var(--t-code)"
    },
    {
      title: "Git Commits",
      icon: "📦",
      type: "commit",
      count: counts.commit || 0,
      description: "Historical commit messages and code diffs showing how the code evolved over time.",
      color: "var(--t-commit)"
    },
    {
      title: "Pull Requests",
      icon: "🔄",
      type: "pr",
      count: counts.pr || 0,
      description: "PR titles, descriptions, and the discussions that happened before code was merged.",
      color: "var(--t-pr)"
    },
    {
      title: "GitHub Issues",
      icon: "🐛",
      type: "issue",
      count: counts.issue || 0,
      description: "Bug reports, feature requests, and developer conversations about problems.",
      color: "var(--t-issue)"
    },
    {
      title: "Code Reviews",
      icon: "👀",
      type: "review",
      count: counts.review || 0,
      description: "Inline comments left by reviewers on specific lines of code.",
      color: "var(--t-review)"
    }
  ];

  const totalPages = Math.ceil(modalTotal / 10);
  const pageStart = modalTotal === 0 ? 0 : modalPage * 10 + 1;
  const pageEnd = Math.min((modalPage + 1) * 10, modalTotal);

  // Filter items in view if user types in search filter
  const displayedItems = Array.isArray(modalData)
    ? modalData.filter(item => {
        if (!filterQuery.trim()) return true;
        const q = filterQuery.toLowerCase();
        return (
          (item.id && item.id.toLowerCase().includes(q)) ||
          (item.title && item.title.toLowerCase().includes(q)) ||
          (item.text && item.text.toLowerCase().includes(q))
        );
      })
    : [];

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
        <p className="muted">Click on any category card below to inspect all its indexed records in detail.</p>
      </div>

      {/* 5 Category Cards */}
      <div className="kb-grid">
        {dataSources.map((source, i) => {
          const isClickable = source.count > 0;
          return (
            <div 
              key={i} 
              className="glass-card kb-card" 
              style={{ 
                borderTop: `4px solid ${source.color}`,
                cursor: isClickable ? "pointer" : "default",
                position: "relative",
                transition: "all 0.2s ease"
              }}
              onClick={() => {
                if (isClickable) {
                  setFilterQuery("");
                  fetchModalData({
                    endpoint: "chunks",
                    type: source.type,
                    page: 0,
                    title: source.title,
                    icon: source.icon,
                    color: source.color,
                    totalCount: source.count
                  });
                }
              }}
              title={isClickable ? `Click to view all ${source.title}` : "No items indexed"}
            >
              <div className="kb-card-header">
                <span className="kb-icon">{source.icon}</span>
                <h3>{source.title}</h3>
              </div>
              <div className="kb-count" style={{ color: source.color }}>
                {source.count.toLocaleString()} <span style={{ fontSize: "14px", color: "var(--text-2)" }}>items</span>
              </div>
              <p className="kb-desc">{source.description}</p>
              
              <div style={{
                marginTop: "auto",
                paddingTop: "14px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                borderTop: "1px dashed var(--border)",
                fontSize: "13px",
                fontWeight: "600",
                color: isClickable ? source.color : "var(--text-3)"
              }}>
                <span>{isClickable ? `Explore ${source.title}` : "No records indexed"}</span>
                <span>{isClickable ? "View →" : "—"}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* RAG Architecture & Technical Internals */}
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
            onClick={() => {
              setFilterQuery("");
              fetchModalData({
                endpoint: "chunks",
                type: "all",
                page: 0,
                title: "All Document Chunks",
                icon: "📄",
                color: "var(--accent)",
                totalCount: total
              });
            }}
            onMouseOver={e => e.currentTarget.style.background = "var(--surface-3)"}
            onMouseOut={e => e.currentTarget.style.background = "var(--surface-2)"}
            title="Click to view all raw chunk data"
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
            onClick={() => {
              setFilterQuery("");
              fetchModalData({
                endpoint: "embeddings",
                page: 0,
                title: "Sample Vector Embeddings",
                icon: "🔢",
                color: "var(--series-2)",
                totalCount: total
              });
            }}
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

      {/* Modal Popup for Details */}
      {modalData && (
        <div 
          style={{ 
            position: "fixed", 
            top: 0, 
            left: 0, 
            width: "100%", 
            height: "100%", 
            background: "rgba(0, 0, 0, 0.82)", 
            backdropFilter: "blur(4px)",
            display: "flex", 
            justifyContent: "center", 
            alignItems: "center", 
            zIndex: 1000 
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setModalData(null);
              setFilterQuery("");
            }
          }}
        >
          <div 
            className="glass-card" 
            style={{ 
              width: "92%", 
              maxWidth: "1050px", 
              height: "88%", 
              padding: "28px", 
              overflow: "hidden", 
              display: "flex", 
              flexDirection: "column", 
              position: "relative", 
              background: "var(--surface-1)",
              border: `1px solid ${modalColor}40`,
              boxShadow: `0 20px 50px rgba(0, 0, 0, 0.6), 0 0 25px ${modalColor}15`
            }}
          >
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
              <div>
                <h2 style={{ margin: "0 0 6px 0", color: "var(--text-1)", display: "flex", alignItems: "center", gap: "10px", fontSize: "22px" }}>
                  <span style={{ color: modalColor }}>{modalIcon}</span> 
                  {modalTitle}
                  <span style={{ fontSize: "14px", color: "var(--text-3)", fontWeight: "normal", fontFamily: "monospace" }}>
                    · {currentRepo.slug}
                  </span>
                </h2>
                <p style={{ color: "var(--text-2)", margin: 0, fontSize: "13.5px" }}>
                  Showing {pageStart} to {pageEnd} of {modalTotal.toLocaleString()} items
                </p>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <input
                  type="text"
                  placeholder="Filter in current page..."
                  value={filterQuery}
                  onChange={(e) => setFilterQuery(e.target.value)}
                  style={{
                    background: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    borderRadius: "6px",
                    padding: "6px 12px",
                    fontSize: "13px",
                    color: "var(--text-1)",
                    width: "200px"
                  }}
                />
                <button 
                  onClick={() => {
                    setModalData(null);
                    setFilterQuery("");
                  }} 
                  style={{ 
                    background: "var(--surface-2)", 
                    color: "var(--text-1)", 
                    padding: "6px 14px", 
                    borderRadius: "6px", 
                    cursor: "pointer", 
                    border: "1px solid var(--border)", 
                    fontWeight: "bold",
                    fontSize: "13px"
                  }}
                  title="Close (Esc)"
                >
                  Close ✕
                </button>
              </div>
            </div>

            {/* Content List */}
            <div 
              style={{ 
                overflowY: "auto", 
                flex: 1, 
                paddingRight: "10px", 
                display: "flex", 
                flexDirection: "column", 
                gap: "16px", 
                opacity: modalLoading ? 0.4 : 1, 
                transition: "opacity 0.2s ease",
                marginTop: "12px"
              }}
            >
              {modalLoading && displayedItems.length === 0 ? (
                <div style={{ color: "var(--text-2)", textAlign: "center", padding: "60px", fontSize: "16px" }}>
                  ⏳ Loading records from backend...
                </div>
              ) : displayedItems.length > 0 ? (
                displayedItems.map((item, index) => {
                  const itemIndex = modalPage * 10 + index + 1;
                  const itemTypeColor = 
                    item.type === "commit" ? "var(--t-commit)" :
                    item.type === "pr" ? "var(--t-pr)" :
                    item.type === "issue" ? "var(--t-issue)" :
                    item.type === "review" ? "var(--t-review)" :
                    item.type === "code" || item.type === "doc" ? "var(--t-code)" :
                    modalColor;

                  return (
                    <div 
                      key={item.id || index} 
                      style={{ 
                        background: "var(--surface-2)", 
                        border: "1px solid var(--border)", 
                        borderRadius: "8px", 
                        overflow: "hidden", 
                        display: "flex", 
                        flexShrink: 0,
                        boxShadow: "0 2px 8px rgba(0,0,0,0.15)"
                      }}
                    >
                      {/* Left Index Column */}
                      <div 
                        style={{ 
                          background: "var(--surface-3)", 
                          padding: "18px 12px", 
                          width: "55px", 
                          display: "flex", 
                          alignItems: "center", 
                          justifyContent: "center", 
                          fontSize: "16px", 
                          fontWeight: "bold", 
                          color: itemTypeColor, 
                          borderRight: "1px solid var(--border)", 
                          flexShrink: 0 
                        }}
                      >
                        {itemIndex}
                      </div>

                      {/* Right Item Detail */}
                      <div style={{ padding: "18px 22px", flex: 1, overflow: "hidden" }}>
                        {/* Meta row */}
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                            <span style={{ 
                              fontSize: "11px", 
                              fontWeight: "700", 
                              color: itemTypeColor, 
                              background: "var(--surface-3)", 
                              padding: "4px 10px", 
                              borderRadius: "4px", 
                              textTransform: "uppercase", 
                              letterSpacing: "0.8px",
                              border: `1px solid ${itemTypeColor}30`
                            }}>
                              TYPE: {item.type || "unknown"}
                            </span>
                            {item.date && (
                              <span style={{ fontSize: "12px", color: "var(--text-2)" }}>
                                📅 {item.date.includes("T") ? item.date.split("T")[0] : item.date}
                              </span>
                            )}
                          </div>

                          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                            {item.url && (
                              <a 
                                href={item.url} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                style={{
                                  fontSize: "12px",
                                  color: "var(--accent)",
                                  textDecoration: "none",
                                  background: "var(--surface-3)",
                                  padding: "3px 8px",
                                  borderRadius: "4px",
                                  border: "1px solid var(--border)",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px"
                                }}
                                onMouseOver={e => e.currentTarget.style.textDecoration = "underline"}
                                onMouseOut={e => e.currentTarget.style.textDecoration = "none"}
                              >
                                🔗 Open in GitHub
                              </a>
                            )}
                            <span style={{ fontSize: "12px", color: "var(--text-3)", fontFamily: "monospace", background: "rgba(0,0,0,0.25)", padding: "3px 8px", borderRadius: "4px" }}>
                              {item.id}
                            </span>
                          </div>
                        </div>

                        {/* Title */}
                        {item.title && (
                          <h4 style={{ margin: "0 0 10px 0", color: "var(--text-1)", fontSize: "15px", lineHeight: "1.4" }}>
                            {item.title}
                          </h4>
                        )}

                        {/* Files touched tag if present */}
                        {item.files && item.files.length > 0 && (
                          <div style={{ fontSize: "12px", color: "var(--text-2)", marginBottom: "10px" }}>
                            <span style={{ color: "var(--text-3)" }}>📁 Files: </span>
                            {item.files.slice(0, 3).join(", ")}
                            {item.files.length > 3 && <span style={{ color: "var(--accent)" }}> (+{item.files.length - 3} more)</span>}
                          </div>
                        )}

                        {/* Text / Embedding view */}
                        {item.embedding ? (
                          <div>
                            <div style={{ fontSize: "12px", color: "var(--text-2)", marginBottom: "6px", fontWeight: "600" }}>
                              384-Dimensional Dense Vector Array:
                            </div>
                            <pre style={{ margin: 0, background: "#0a0a0a", padding: "14px", borderRadius: "6px", color: "#a8c7fa", fontSize: "13px", whiteSpace: "pre-wrap", wordBreak: "break-all", border: "1px solid #222" }}>
                              [{item.embedding.join(", ")}]
                            </pre>
                          </div>
                        ) : (
                          <pre style={{ 
                            margin: 0, 
                            background: "#0a0a0a", 
                            padding: "14px 16px", 
                            borderRadius: "6px", 
                            color: "#e2e8f0", 
                            fontSize: "13px", 
                            whiteSpace: "pre-wrap", 
                            wordBreak: "break-word", 
                            maxHeight: "300px", 
                            overflowY: "auto", 
                            border: "1px solid #222", 
                            lineHeight: "1.5",
                            fontFamily: "JetBrains Mono, monospace"
                          }}>
                            {item.text || "(No textual content)"}
                          </pre>
                        )}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div style={{ color: "var(--text-2)", textAlign: "center", padding: "40px", fontSize: "15px" }}>
                  {filterQuery ? `No records found matching "${filterQuery}"` : "No records available."}
                </div>
              )}
            </div>

            {/* Pagination Controls */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "16px", paddingTop: "16px", borderTop: "1px solid var(--border)" }}>
              <button 
                disabled={modalPage === 0 || modalLoading}
                onClick={() => {
                  fetchModalData({
                    endpoint: modalEndpoint,
                    type: modalType,
                    page: modalPage - 1,
                    title: modalTitle,
                    icon: modalIcon,
                    color: modalColor,
                    totalCount: modalTotal
                  });
                }}
                style={{ 
                  padding: "8px 18px", 
                  background: "var(--surface-2)", 
                  color: "var(--text-1)", 
                  border: "1px solid var(--border)", 
                  borderRadius: "6px", 
                  cursor: modalPage === 0 || modalLoading ? "not-allowed" : "pointer", 
                  opacity: modalPage === 0 || modalLoading ? 0.4 : 1, 
                  fontWeight: "bold",
                  fontSize: "13px"
                }}
              >
                ← Previous 10
              </button>

              <div style={{ color: "var(--text-2)", display: "flex", alignItems: "center", gap: "8px", fontWeight: "600", fontSize: "13.5px" }}>
                <span>Page {modalPage + 1} of {totalPages || 1}</span>
                {modalLoading && <span style={{ fontSize: "12px", color: modalColor }}>⏳ Fetching...</span>}
              </div>

              <button 
                disabled={modalPage + 1 >= totalPages || modalLoading}
                onClick={() => {
                  fetchModalData({
                    endpoint: modalEndpoint,
                    type: modalType,
                    page: modalPage + 1,
                    title: modalTitle,
                    icon: modalIcon,
                    color: modalColor,
                    totalCount: modalTotal
                  });
                }}
                style={{ 
                  padding: "8px 18px", 
                  background: "var(--surface-2)", 
                  color: "var(--text-1)", 
                  border: "1px solid var(--border)", 
                  borderRadius: "6px", 
                  cursor: modalPage + 1 >= totalPages || modalLoading ? "not-allowed" : "pointer", 
                  opacity: modalPage + 1 >= totalPages || modalLoading ? 0.4 : 1, 
                  fontWeight: "bold",
                  fontSize: "13px"
                }}
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
