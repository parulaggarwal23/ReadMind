import re

with open("frontend/src/App.jsx", "r") as f:
    content = f.read()

# Add activeModel state
content = content.replace('const [health, setHealth] = useState(null);', 'const [health, setHealth] = useState(null);\n  const [activeModel, setActiveModel] = useState("gemini-2.5-flash");')

# Replace the status span with a select box
old_span = '<span className={`status ${health ? "ok" : "down"}`}>\n            <span className="dot" />\n            {health ? `${health.provider} · ${health.model}` : "API offline"}\n          </span>'

new_span = '''<span className={`status ${health ? "ok" : "down"}`}>
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
          </span>'''

content = content.replace(old_span, new_span)

with open("frontend/src/App.jsx", "w") as f:
    f.write(content)
