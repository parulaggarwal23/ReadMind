import { useState, useEffect } from "react";
import { api } from "../api";

export default function KubernetesDashboard() {
  const [status, setStatus] = useState(null);
  const [manifests, setManifests] = useState({});
  const [selectedManifest, setSelectedManifest] = useState("hpa.yaml");
  const [isLoading, setIsLoading] = useState(true);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState(false);
  const [error, setError] = useState(null);

  // Fetch cluster status and manifests on mount
  const fetchStatus = async () => {
    try {
      const data = await api.k8sStatus();
      setStatus(data);
      setError(null);
    } catch (err) {
      console.error("Failed to load K8s status:", err);
      setError(err.message);
    }
  };

  const fetchManifests = async () => {
    try {
      const data = await api.k8sManifests();
      setManifests(data);
    } catch (err) {
      console.error("Failed to load K8s manifests:", err);
    }
  };

  useEffect(() => {
    setIsLoading(true);
    Promise.all([fetchStatus(), fetchManifests()]).finally(() => setIsLoading(false));

    // Polling every 5 seconds for live status
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleSimulateLoad = async () => {
    setIsSimulating(true);
    try {
      const updated = await api.k8sSimulateLoad();
      setStatus(updated);
    } catch (err) {
      alert("Error triggering traffic spike: " + err.message);
    } finally {
      setIsSimulating(false);
    }
  };

  const handleResetLoad = async () => {
    setIsResetting(true);
    try {
      const updated = await api.k8sResetLoad();
      setStatus(updated);
    } catch (err) {
      alert("Error resetting traffic: " + err.message);
    } finally {
      setIsResetting(false);
    }
  };

  const handleCopyManifest = () => {
    const content = manifests[selectedManifest] || "";
    navigator.clipboard.writeText(content).then(() => {
      setCopyFeedback(true);
      setTimeout(() => setCopyFeedback(false), 2500);
    });
  };

  if (isLoading && !status) {
    return (
      <div className="k8s-loading">
        <div className="k8s-spinner" />
        <p>Connecting to Kubernetes Cluster control plane...</p>
      </div>
    );
  }

  const hpa = status?.hpa;
  const cluster = status?.cluster;
  const deployments = status?.deployments || [];
  const events = status?.events || [];
  const isSpiking = status?.is_traffic_spiking;

  return (
    <div className="k8s-dashboard">
      {/* ☸️ Top Cluster Overview Header */}
      <div className="k8s-header-card">
        <div className="k8s-header-left">
          <div className="k8s-logo-icon">☸️</div>
          <div>
            <div className="k8s-title-row">
              <h2>Kubernetes Cluster & Horizontal Pod Autoscaling (HPA)</h2>
              <span className="k8s-badge-health">● {cluster?.health || "Healthy"}</span>
              <span className="k8s-badge-ns">Namespace: {cluster?.namespace || "readmind-prod"}</span>
            </div>
            <p className="k8s-subtitle">
              Microservices orchestration for Frontend, Backend RAG engine, and ChromaDB Vector Store.
              Scales replicas from <strong>{hpa?.min_replicas || 2}</strong> to <strong>{hpa?.max_replicas || 6}</strong> automatically upon query traffic spikes.
            </p>
          </div>
        </div>

        <div className="k8s-header-stats">
          <div className="k8s-stat-box">
            <span className="k8s-stat-label">CLUSTER VERSION</span>
            <span className="k8s-stat-val">{cluster?.version || "v1.29.2"}</span>
          </div>
          <div className="k8s-stat-box">
            <span className="k8s-stat-label">WORKER NODES</span>
            <span className="k8s-stat-val">{cluster?.total_nodes || 3}</span>
          </div>
          <div className="k8s-stat-box">
            <span className="k8s-stat-label">TOTAL PODS</span>
            <span className="k8s-stat-val k8s-highlight-pod">{cluster?.total_pods || 5}</span>
          </div>
        </div>
      </div>

      {error && <div className="alert error">Error syncing cluster: {error}</div>}

      {/* 🚀 HPA Control & Metrics Gauge Card */}
      <div className={`k8s-hpa-card ${isSpiking ? "hpa-active-surge" : ""}`}>
        <div className="k8s-hpa-header">
          <div className="k8s-hpa-title-area">
            <span className="k8s-hpa-tag">HPA CONTROLLER</span>
            <h3>{hpa?.name || "readmind-api-hpa"}</h3>
            <span className={`k8s-hpa-status-pill ${isSpiking ? "surge" : "normal"}`}>
              {isSpiking ? "⚡ SCALING SURGE ACTIVE" : "● NORMAL BASELINE"}
            </span>
          </div>

          <div className="k8s-hpa-actions">
            <button
              className={`btn-k8s-spike ${isSpiking ? "active-spike" : ""}`}
              onClick={handleSimulateLoad}
              disabled={isSimulating || isSpiking}
              title="DevOps Live Demo: Flood backend with concurrent RAG requests to exceed 60% CPU threshold"
            >
              {isSimulating ? "Spiking..." : "⚡ Simulate Traffic Surge (Trigger HPA)"}
            </button>
            <button
              className="btn-k8s-reset"
              onClick={handleResetLoad}
              disabled={isResetting || !isSpiking}
              title="Cool down traffic to return to baseline 2 replicas"
            >
              {isResetting ? "Cooling down..." : "🔄 Reset Traffic to Baseline"}
            </button>
          </div>
        </div>

        <div className="k8s-condition-banner">
          <span>{hpa?.condition}</span>
        </div>

        <div className="k8s-metrics-grid">
          {/* CPU Gauge */}
          <div className="k8s-metric-box">
            <div className="k8s-metric-meta">
              <span className="metric-name">Backend Pods CPU Utilization</span>
              <span className={`metric-value ${isSpiking ? "text-danger" : "text-success"}`}>
                {hpa?.current_cpu_percentage}% <small>/ {hpa?.target_cpu_percentage}% Target</small>
              </span>
            </div>
            <div className="k8s-progress-track">
              <div
                className={`k8s-progress-fill ${isSpiking ? "fill-danger" : "fill-primary"}`}
                style={{ width: `${Math.min(hpa?.current_cpu_percentage || 0, 100)}%` }}
              />
              {/* Target Threshold Marker Line */}
              <div
                className="k8s-target-marker"
                style={{ left: `${hpa?.target_cpu_percentage || 60}%` }}
                title="HPA Trigger Threshold: 60% CPU"
              >
                <span className="marker-label">Target 60%</span>
              </div>
            </div>
          </div>

          {/* Memory Gauge */}
          <div className="k8s-metric-box">
            <div className="k8s-metric-meta">
              <span className="metric-name">Backend Pods Memory Utilization</span>
              <span className="metric-value">
                {hpa?.current_memory_percentage}% <small>/ {hpa?.target_memory_percentage}% Target</small>
              </span>
            </div>
            <div className="k8s-progress-track">
              <div
                className="k8s-progress-fill fill-accent"
                style={{ width: `${Math.min(hpa?.current_memory_percentage || 0, 100)}%` }}
              />
              <div
                className="k8s-target-marker"
                style={{ left: `${hpa?.target_memory_percentage || 75}%` }}
                title="HPA Trigger Threshold: 75% Memory"
              >
                <span className="marker-label">Target 75%</span>
              </div>
            </div>
          </div>

          {/* Pod Replicas Gauge */}
          <div className="k8s-metric-box replicas-box">
            <div className="k8s-metric-meta">
              <span className="metric-name">Active Backend Pod Replicas</span>
              <span className="metric-value replicas-num">
                {hpa?.current_replicas} <small className="text-muted">/ {hpa?.max_replicas} max</small>
              </span>
            </div>
            <div className="replicas-visual-bar">
              {Array.from({ length: hpa?.max_replicas || 6 }).map((_, idx) => (
                <div
                  key={idx}
                  className={`replica-pip ${idx < (hpa?.current_replicas || 2) ? "active" : "inactive"} ${
                    isSpiking && idx >= 2 ? "scaled-up" : ""
                  }`}
                  title={`Replica ${idx + 1}`}
                >
                  <span className="pip-label">Pod {idx + 1}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 📦 Microservices & Pod Architecture Grid */}
      <div className="k8s-section">
        <div className="k8s-section-header">
          <h3>📦 Container Workloads & Pod Topology</h3>
          <span className="k8s-section-desc">Each tier is isolated in distinct Pods with dedicated resource limits and health probes</span>
        </div>

        <div className="k8s-deployments-list">
          {deployments.map((dep) => (
            <div key={dep.name} className="k8s-deployment-card">
              <div className="dep-card-header">
                <div className="dep-info">
                  <span className="dep-type-pill">{dep.type}</span>
                  <h4>{dep.name}</h4>
                  <span className="dep-tier-label">{dep.tier}</span>
                </div>
                <div className="dep-meta-right">
                  <span className="dep-service-badge">{dep.service}</span>
                  <span className={`dep-replica-badge ${dep.hpa_enabled && isSpiking ? "rescaled" : ""}`}>
                    Replicas: <strong>{dep.replicas}</strong>
                    {dep.hpa_enabled && <span className="hpa-tag-mini">HPA Managed</span>}
                  </span>
                </div>
              </div>

              {/* Pod Cards Grid */}
              <div className="k8s-pods-grid">
                {dep.pods.map((pod) => (
                  <div
                    key={pod.name}
                    className={`k8s-pod-card ${pod.age.includes("s") || pod.age.includes("m") && isSpiking ? "pod-scaled-highlight" : ""}`}
                  >
                    <div className="pod-card-top">
                      <div className="pod-status-indicator">
                        <span className="pod-dot" />
                        <span className="pod-name" title={pod.name}>{pod.name}</span>
                      </div>
                      <span className="pod-ready-badge">{pod.ready}</span>
                    </div>

                    <div className="pod-card-body">
                      <div className="pod-field">
                        <span className="pf-label">Node:</span>
                        <span className="pf-val">{pod.node}</span>
                      </div>
                      <div className="pod-field">
                        <span className="pf-label">Age:</span>
                        <span className="pf-val">{pod.age}</span>
                      </div>
                      <div className="pod-field">
                        <span className="pf-label">CPU / RAM:</span>
                        <span className="pf-val">{pod.cpu_usage} · {pod.memory_usage}</span>
                      </div>
                      {pod.volume_claim && (
                        <div className="pod-field pvc-field">
                          <span className="pf-label">Storage:</span>
                          <span className="pf-val pvc-badge">💾 {pod.volume_claim}</span>
                        </div>
                      )}
                    </div>

                    <div className="pod-card-footer">
                      <span className="probe-badge ok" title="Liveness Probe: /api/health">
                        ✓ Liveness
                      </span>
                      <span className="probe-badge ok" title="Readiness Probe: /api/health">
                        ✓ Readiness
                      </span>
                      {pod.restarts === 0 && <span className="restart-badge">0 restarts</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 📜 Real-time Kubernetes Events Feed */}
      <div className="k8s-section">
        <div className="k8s-section-header">
          <h3>⚡ Real-time Kubernetes Events Log</h3>
          <span className="k8s-section-desc">Live control plane event stream (Deployment scale-outs, pod scheduling, PVC bindings)</span>
        </div>

        <div className="k8s-events-table-wrapper">
          <table className="k8s-events-table">
            <thead>
              <tr>
                <th>TYPE</th>
                <th>REASON</th>
                <th>AGE</th>
                <th>MESSAGE</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev, idx) => (
                <tr key={idx} className={ev.type === "Warning" ? "event-warning" : "event-normal"}>
                  <td>
                    <span className={`event-type-badge ${ev.type.toLowerCase()}`}>{ev.type}</span>
                  </td>
                  <td><strong>{ev.reason}</strong></td>
                  <td className="event-time">{ev.timestamp}</td>
                  <td className="event-msg">{ev.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 📄 Declarative Manifests & Kustomize Explorer */}
      <div className="k8s-section">
        <div className="k8s-section-header">
          <h3>📄 Declarative Kubernetes Manifests (Production Ready)</h3>
          <span className="k8s-section-desc">Inspect and copy the exact YAML manifests driving the cluster orchestration and HPA</span>
        </div>

        <div className="k8s-manifests-container">
          <div className="manifest-tabs-bar">
            {Object.keys(manifests).map((fileName) => (
              <button
                key={fileName}
                className={`manifest-tab-btn ${selectedManifest === fileName ? "active" : ""}`}
                onClick={() => setSelectedManifest(fileName)}
              >
                {fileName.includes("hpa") ? "⭐ " : ""}{fileName}
              </button>
            ))}
          </div>

          <div className="manifest-code-wrapper">
            <div className="manifest-code-header">
              <span className="manifest-filepath">k8s/{selectedManifest}</span>
              <button className="btn-copy-manifest" onClick={handleCopyManifest}>
                {copyFeedback ? "✓ Copied to Clipboard!" : "📋 Copy YAML"}
              </button>
            </div>
            <pre className="manifest-pre">
              <code>{manifests[selectedManifest] || "# Manifest loading..."}</code>
            </pre>
          </div>

          <div className="k8s-quickstart-banner">
            <div className="quickstart-title">
              <strong>🚀 One-Command Cluster Deployment:</strong>
            </div>
            <div className="quickstart-cmd">
              <code>kubectl apply -k k8s/</code>
              <span className="quickstart-sub">Apply all 11 declarative manifests (Deployments, StatefulSet, Services, Ingress, & HPA) via Kustomize</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
