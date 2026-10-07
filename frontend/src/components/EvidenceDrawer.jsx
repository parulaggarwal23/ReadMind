import { useEffect, useState } from "react";
import { api, TYPE_LABELS } from "../api";

export default function EvidenceDrawer({ repo, docId, onNavigate, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
    api.evidence(repo, docId).then(setData).catch((e) => setError(e.message));
  }, [repo, docId]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const d = data?.doc;
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Evidence">
        <div className="drawer-head">
          <div>
            {d && <span className={`type-badge t-${d.type}`}>{TYPE_LABELS[d.type] || d.type}</span>}
            <h2>{d?.title || docId}</h2>
            <div className="muted mono small">{d?.id}{d?.date ? ` · ${d.date.slice(0, 10)}` : ""}</div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {error && <div className="alert error">{error}</div>}
        {!d && !error && <div className="skeleton tall" />}
        {d && (
          <>
            {d.url && (
              <a className="gh-link" href={d.url} target="_blank" rel="noreferrer">
                Open on GitHub ↗
              </a>
            )}
            <pre className="evidence-full">{d.text}</pre>
            {data.linked.length > 0 && (
              <>
                <h3>Linked history</h3>
                <ul className="linked-list">
                  {data.linked.map((l) => (
                    <li key={l.id}>
                      <button onClick={() => onNavigate(l.id)}>
                        <span className={`type-badge t-${l.type}`}>{TYPE_LABELS[l.type] || l.type}</span>
                        <span>{l.title || l.id}</span>
                        <span className="muted mono small">{l.date?.slice(0, 10)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </aside>
    </div>
  );
}
