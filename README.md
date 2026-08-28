# ⚡ ZeroToken Gateway: Enterprise Multi-Tenant Semantic Cache

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Qdrant](https://img.shields.io/badge/VectorDB-Qdrant-red.svg)](https://qdrant.tech/)
[![uv](https://img.shields.io/badge/Package%20Manager-uv-purple.svg)](https://github.com/astral-sh/uv)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**ZeroToken Gateway** is a high-performance, multi-tenant reverse proxy designed to optimize Large Language Model (LLM) infrastructure costs. By intercepting semantically redundant user prompts and serving answers locally using high-speed vector embeddings, ZeroToken reduces upstream API token bills by up to **70%** and cuts response latency from **~1,800ms down to <15ms** at $0 API cost per cache hit.

---

## 💡 System Architecture

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
                                │   (Scubs PII e.g., [ORDER_ID], [EMAIL]) │
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
                               └────────────────────┘ └────────────────────
