const CITE_RE = /\[([^[\]]+)\]/g;
const ID_RE = /^(code|commit|issue|pr|review|doc):\S+$/;

function shortLabel(id) {
  const [type, rest] = [id.slice(0, id.indexOf(":")), id.slice(id.indexOf(":") + 1)];
  if (type === "issue" || type === "pr") return `${type === "pr" ? "PR" : "Issue"} #${rest}`;
  if (type === "commit") return rest.slice(0, 7);
  if (type === "code") return rest.split("/").pop();
  if (type === "review") return "review";
  return rest.split("/").pop();
}

function isValid(id, evidenceIds) {
  if (!evidenceIds) return true;
  return evidenceIds.some(
    (e) => e === id || (id.startsWith("commit:") && e.startsWith("commit:") && (e.startsWith(id) || id.startsWith(e)))
  );
}

/** Renders the LLM answer, turning [type:id] citations into clickable evidence chips.
 *  Citations to ids that were NOT in the retrieved evidence are shown as invalid (likely fabricated). */
export default function AnswerText({ text, evidenceIds, onCite }) {
  const paragraphs = (text || "").split(/\n{2,}/);

  const renderInline = (p, pi) => {
    const out = [];
    let last = 0;
    for (const m of p.matchAll(CITE_RE)) {
      const ids = m[1].split(/[,;]\s*/).map((s) => s.trim().replace(/`/g, ""));
      if (!ids.every((x) => ID_RE.test(x))) continue;
      out.push(p.slice(last, m.index));
      ids.forEach((id, i) => {
        const ok = isValid(id, evidenceIds);
        out.push(
          <button
            key={`${pi}-${m.index}-${i}`}
            className={`cite cite-${id.split(":")[0]} ${ok ? "" : "invalid"}`}
            onClick={() => ok && onCite?.(id)}
            title={ok ? `Open ${id}` : `${id} was not in the retrieved evidence (possible hallucination)`}
          >
            {shortLabel(id)}
          </button>
        );
      });
      last = m.index + m[0].length;
    }
    out.push(p.slice(last));
    return out;
  };

  return (
    <div className="answer-text">
      {paragraphs.map((p, i) => (
        <p key={i} className={/^recommendation:/i.test(p.trim()) ? "recommendation" : ""}>
          {renderInline(p, i)}
        </p>
      ))}
    </div>
  );
}
