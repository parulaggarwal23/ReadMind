"""Kubernetes (K8s) Orchestration & Horizontal Pod Autoscaler (HPA) Controller.

Manages:
- Cluster topology state (Deployments, StatefulSets, Pods, Services, PVCs)
- HPA status and real-time CPU/Memory utilization tracking
- Interactive load simulation to trigger live HPA autoscaling events
- Reading and delivering declarative K8s YAML manifests to the UI
"""
from __future__ import annotations
import datetime
import os
import time
from pathlib import Path
from typing import Any, Dict, List

# Workspace root path
K8S_DIR = Path(__file__).resolve().parent.parent.parent / "k8s"

# State tracking for Kubernetes simulation
_CLUSTER_STATE = {
    "is_traffic_spiking": False,
    "last_scaled_at": None,
    "scaling_events": [
        {
            "timestamp": "2026-10-27T04:30:12Z",
            "type": "Normal",
            "reason": "SuccessfulCreate",
            "message": "Created pod: readmind-api-68f7d98b9-x4r2z",
        },
        {
            "timestamp": "2026-10-27T04:30:15Z",
            "type": "Normal",
            "reason": "SuccessfulCreate",
            "message": "Created pod: readmind-api-68f7d98b9-m9k2a",
        },
        {
            "timestamp": "2026-10-27T04:30:18Z",
            "type": "Normal",
            "reason": "ProvisioningSucceeded",
            "message": "Bound persistent volume claim 'chroma-data' to volume pvc-e418-10gi",
        },
    ],
}


def get_cluster_status() -> Dict[str, Any]:
    """Return the complete live topology and metrics of the Kubernetes cluster."""
    is_spike = _CLUSTER_STATE["is_traffic_spiking"]

    # Dynamic metrics based on traffic spike state
    cpu_util = 86 if is_spike else 34
    mem_util = 72 if is_spike else 48
    api_replicas = 5 if is_spike else 2

    # Backend pods
    backend_pods = [
        {
            "name": "readmind-api-68f7d98b9-x4r2z",
            "node": "k8s-worker-pool-01",
            "status": "Running",
            "ready": "1/1",
            "restarts": 0,
            "age": "2h45m",
            "cpu_usage": f"{cpu_util - 4}%",
            "memory_usage": "242Mi",
            "probes": {"liveness": "OK", "readiness": "OK"},
        },
        {
            "name": "readmind-api-68f7d98b9-m9k2a",
            "node": "k8s-worker-pool-02",
            "status": "Running",
            "ready": "1/1",
            "restarts": 0,
            "age": "2h45m",
            "cpu_usage": f"{cpu_util + 2}%",
            "memory_usage": "258Mi",
            "probes": {"liveness": "OK", "readiness": "OK"},
        },
    ]

    if is_spike:
        backend_pods.extend([
            {
                "name": "readmind-api-68f7d98b9-t7p9q",
                "node": "k8s-worker-pool-01",
                "status": "Running",
                "ready": "1/1",
                "restarts": 0,
                "age": "1m12s",
                "cpu_usage": f"{cpu_util - 2}%",
                "memory_usage": "218Mi",
                "probes": {"liveness": "OK", "readiness": "OK"},
            },
            {
                "name": "readmind-api-68f7d98b9-c2w8v",
                "node": "k8s-worker-pool-02",
                "status": "Running",
                "ready": "1/1",
                "restarts": 0,
                "age": "45s",
                "cpu_usage": f"{cpu_util - 6}%",
                "memory_usage": "204Mi",
                "probes": {"liveness": "OK", "readiness": "OK"},
            },
            {
                "name": "readmind-api-68f7d98b9-k5z1e",
                "node": "k8s-worker-pool-03",
                "status": "Running",
                "ready": "1/1",
                "restarts": 0,
                "age": "25s",
                "cpu_usage": f"{cpu_util}%",
                "memory_usage": "195Mi",
                "probes": {"liveness": "OK", "readiness": "OK"},
            },
        ])

    frontend_pods = [
        {
            "name": "readmind-frontend-5b4d8-j8z2k",
            "node": "k8s-worker-pool-01",
            "status": "Running",
            "ready": "1/1",
            "restarts": 0,
            "age": "2h45m",
            "cpu_usage": "11%",
            "memory_usage": "88Mi",
            "probes": {"liveness": "OK", "readiness": "OK"},
        },
        {
            "name": "readmind-frontend-5b4d8-m1w9p",
            "node": "k8s-worker-pool-02",
            "status": "Running",
            "ready": "1/1",
            "restarts": 0,
            "age": "2h45m",
            "cpu_usage": "14%",
            "memory_usage": "92Mi",
            "probes": {"liveness": "OK", "readiness": "OK"},
        },
    ]

    vector_db_pods = [
        {
            "name": "chromadb-vector-store-0",
            "node": "k8s-worker-pool-storage-01",
            "status": "Running",
            "ready": "1/1",
            "restarts": 0,
            "age": "2h45m",
            "cpu_usage": "22%",
            "memory_usage": "1.2Gi",
            "volume_claim": "chroma-data (10Gi Bound)",
            "probes": {"liveness": "OK", "readiness": "OK"},
        }
    ]

    hpa_status = {
        "name": "readmind-api-hpa",
        "target_deployment": "readmind-api",
        "min_replicas": 2,
        "max_replicas": 6,
        "current_replicas": api_replicas,
        "target_cpu_percentage": 60,
        "current_cpu_percentage": cpu_util,
        "target_memory_percentage": 75,
        "current_memory_percentage": mem_util,
        "status": "SCALING_ACTIVE" if is_spike else "NORMAL",
        "condition": (
            "⚠️ HIGH LOAD: HPA triggered scale-up (2 ➔ 5 pods)"
            if is_spike
            else "✅ Optimal Load: Operating within target threshold (34% < 60%)"
        ),
    }

    return {
        "cluster": {
            "name": "readmind-k8s-cluster",
            "version": "v1.29.2",
            "namespace": "readmind-prod",
            "health": "Healthy",
            "total_nodes": 3,
            "total_pods": len(backend_pods) + len(frontend_pods) + len(vector_db_pods),
        },
        "is_traffic_spiking": is_spike,
        "hpa": hpa_status,
        "deployments": [
            {
                "name": "readmind-api",
                "type": "Deployment",
                "tier": "Backend (RAG Engine)",
                "replicas": f"{api_replicas}/{api_replicas}",
                "hpa_enabled": True,
                "service": "readmind-api-svc (ClusterIP:8000)",
                "pods": backend_pods,
            },
            {
                "name": "readmind-frontend",
                "type": "Deployment",
                "tier": "Frontend (Vite/Nginx)",
                "replicas": "2/2",
                "hpa_enabled": False,
                "service": "readmind-frontend-svc (LoadBalancer:80)",
                "pods": frontend_pods,
            },
            {
                "name": "chromadb-vector-store",
                "type": "StatefulSet",
                "tier": "Vector Database (ChromaDB)",
                "replicas": "1/1",
                "hpa_enabled": False,
                "service": "chromadb-svc (Headless:8000)",
                "pods": vector_db_pods,
            },
        ],
        "events": _CLUSTER_STATE["scaling_events"][-6:],
    }


def simulate_traffic_spike() -> Dict[str, Any]:
    """Simulate a sudden surge of 50 concurrent RAG queries to trigger HPA scaling."""
    _CLUSTER_STATE["is_traffic_spiking"] = True
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%SZ")

    _CLUSTER_STATE["scaling_events"].append({
        "timestamp": now_iso,
        "type": "Warning",
        "reason": "ThresholdExceeded",
        "message": "HorizontalPodAutoscaler: CPU utilization 86% exceeded target threshold (60%)",
    })
    _CLUSTER_STATE["scaling_events"].append({
        "timestamp": now_iso,
        "type": "Normal",
        "reason": "SuccessfulRescale",
        "message": "Scaled readmind-api deployment from 2 to 5 replicas based on HPA policy",
    })

    return get_cluster_status()


def reset_traffic() -> Dict[str, Any]:
    """Cooldown cluster traffic back to nominal baseline."""
    _CLUSTER_STATE["is_traffic_spiking"] = False
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%SZ")

    _CLUSTER_STATE["scaling_events"].append({
        "timestamp": now_iso,
        "type": "Normal",
        "reason": "SuccessfulRescale",
        "message": "Traffic cooled down. HorizontalPodAutoscaler scaled readmind-api back to 2 replicas",
    })

    return get_cluster_status()


def get_k8s_manifests() -> Dict[str, str]:
    """Read all K8s YAML manifests to display in the UI."""
    manifests = {}
    if K8S_DIR.exists():
        for yml in sorted(K8S_DIR.glob("*.yaml")):
            manifests[yml.name] = yml.read_text(encoding="utf-8")
    return manifests
