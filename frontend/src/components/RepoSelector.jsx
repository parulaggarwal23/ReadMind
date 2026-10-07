export default function RepoSelector({ repos, value, onChange }) {
  return (
    <label className="repo-select">
      <span>Repository</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} disabled={!repos.length}>
        {!repos.length && <option>—</option>}
        {repos.map((r) => (
          <option key={r.slug} value={r.slug}>
            {r.github}
          </option>
        ))}
      </select>
    </label>
  );
}
