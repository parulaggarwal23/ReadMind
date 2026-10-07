import React from 'react';

export default function HeroExplanation() {
  return (
    <div className="hero-container">
      <div className="hero-content">
        <h2 className="hero-title">Beyond Simple Code Search</h2>
        <p className="hero-subtitle">
          Traditional AI only looks at your code. Our <strong>RepoHistory RAG</strong> connects the dots across your entire development history to answer complex architectural questions with real evidence.
        </p>

        <div className="pipeline">
          <div className="pipeline-step glass-card">
            <div className="step-icon">💬</div>
            <div className="step-title">1. You Ask</div>
            <p>"Why did we implement authentication this way?"</p>
          </div>
          
          <div className="pipeline-arrow">➔</div>
          
          <div className="pipeline-step glass-card">
            <div className="step-icon">🔍</div>
            <div className="step-title">2. Deep Retrieval</div>
            <div className="retrieval-tags">
              <span className="rtag t-code">Code</span>
              <span className="rtag t-commit">Commits</span>
              <span className="rtag t-pr">Pull Requests</span>
              <span className="rtag t-issue">Issues</span>
              <span className="rtag t-review">Reviews</span>
            </div>
            <p>Hybrid search across the entire repository history graph.</p>
          </div>

          <div className="pipeline-arrow">➔</div>

          <div className="pipeline-step glass-card">
            <div className="step-icon">✨</div>
            <div className="step-title">3. Grounded Answer</div>
            <p>Accurate response with verifiable inline citations to the actual GitHub history.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
