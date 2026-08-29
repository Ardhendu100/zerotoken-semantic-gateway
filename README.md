# ⚡ ZeroToken Gateway: Enterprise Multi-Tenant Semantic Cache Proxy

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Qdrant](https://img.shields.io/badge/VectorDB-Qdrant-red.svg)](https://qdrant.tech/)
[![uv](https://img.shields.io/badge/Package%20Manager-uv-purple.svg)](https://github.com/astral-sh/uv)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

ZeroToken Gateway is a high-performance, multi-tenant reverse proxy designed to optimize Large Language Model (LLM) infrastructure costs. By intercepting semantically redundant user prompts and serving answers locally using high-speed vector embeddings, ZeroToken reduces upstream API token costs and cuts response latency from **~1,200ms down to <15ms** at $0 API cost per cache hit.

---

## 🎯 Key Capabilities

* **⚡ Sub-15ms Latency on Hits:** Returns semantically matching responses instantly from local vector memory.
* **🛡️ Smart TTL & Volatile Query Bypass:** Automatically bypasses cache evaluation for real-time keywords (`today`, `stock price`, `weather`, `latest news`).
* **🏢 Multi-Tenant Isolation:** Tenant context separation enforced via `X-Tenant-ID` request headers.
* **🔒 Privacy & Guardrails:** Normalizes input whitespace/casing and strips basic PII before vector lookup.
* **📊 Adaptive Token Budgeting:** Per-tenant daily token limits returning `HTTP 429` on budget cap exhaustion.
* **📈 Streamlit Observability Dashboard:** Real-time KPI tracking for Cache Hit Rate, Cost Saved ($), and Latency Boxplots.

---

## 🏗️ System Architecture

```text
                                ┌─────────────────────────────────────────┐
                                │             CLIENT APP                  │
                                └────────────────────┬────────────────────┘
                                                     │
                                                     ▼
                                ┌─────────────────────────────────────────┐
                                │       ZEROTOKEN FASTAPI PROXY           │
                                └────────────────────┬────────────────────┘
                                                     │
                                                     ▼
                                ┌─────────────────────────────────────────┐
                                │   TEXT NORMALIZATION & ENTITY PARSER    │
                                │   (Scrubs PII e.g., [ORDER_ID], [EMAIL])│
                                └────────────────────┬────────────────────┘
                                                     │
                                                     ▼
                                ┌─────────────────────────────────────────┐
                                │     LOCAL CPU EMBEDDING ENGINE ($0)     │
                                │    (all-MiniLM-L6-v2 - 384 dimensions)  │
                                └────────────────────┬────────────────────┘
                                                     │
                                                     ▼
                                ┌─────────────────────────────────────────┐
                                │     ENTERPRISE QDRANT VECTOR STORE      │
                                │  (Metadata Filter: tenant_id == Company)│
                                └─────────┬─────────────────────┬─────────┘
                                          │                     │
                             CACHE HIT    │                     │   CACHE MISS
                       (Cosine Sim ≥ 0.88)│                     │ (Sim < 0.88)
                                          ▼                     ▼
                               ┌────────────────────┐ ┌────────────────────┐
                               │  RETURN IN ~12ms   │ │ FORWARD TO UPSTREAM│
                               │  ($0.00 API Cost)  │ │ LLM (OpenAI/Groq)  │
                               └────────────────────┘ └────────────────────┘

---

## 📊 Benchmark Metrics

============================================================
🚀 Latency Reduction: 98.9%
⚡ Speedup Factor: 92.0x Faster (From 1120.5ms down to 12.2ms)
💰 Upstream API Cost Saved: 100% on Cache HITs
============================================================