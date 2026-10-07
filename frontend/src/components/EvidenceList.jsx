import { TYPE_LABELS } from "../api";

export default function EvidenceList({ items, cited = [], onOpen }) {
  const isCited = (id) => cited.some((c) => c === id || id.startsWith(c) || c.startsWith(id));
  return (
    <ul className="evidence-list">
      {items.map((e) => (
        <li key={e.id}>
          <button className="evidence-item" onClick={() => onOpen?.(e.id)}>
            <div className="evidence-top">
              <span className={`type-badge t-${e.type}`}>{TYPE_LABELS[e.type] || e.type}</span>
              <span className="evidence-title">{e.title || e.id}</span>
              {isCited(e.id) && <span className="cited-flag">cited</span>}
              <span className="muted mono small">{e.date ? e.date.slice(0, 10) : ""}</span>
            </div>
            <div className="evidence-snippet">{e.snippet}</div>
          </button>
        </li>
      ))}
    </ul>
  );
}
