import uuid
from typing import Any, Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer


class VectorCacheManager:
    def __init__(self, collection_name: str = "semantic_cache"):
        self.collection_name = collection_name

        print("⚡ Pre-warming sentence-transformer model (all-MiniLM-L6-v2) on CPU...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

        self.client = QdrantClient(path="./qdrant_data")
        self._init_collection()

    def _init_collection(self):
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            print(f"✅ Qdrant collection '{self.collection_name}' initialized.")

    def get_embedding(self, text: str) -> List[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def search_similar(
        self,
        query_text: str,
        similarity_threshold: float = 0.85,
        tenant_id: str = "default",
    ) -> Optional[Dict[str, Any]]:
        query_vector = self.get_embedding(query_text)

        # Enforce tenant isolation directly at the Qdrant filter level
        tenant_filter = Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=tenant_id)
                )
            ]
        )

        search_result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=tenant_filter,
            limit=1,
        ).points

        if search_result and search_result[0].score >= similarity_threshold:
            hit = search_result[0]
            payload = hit.payload or {}
            return {
                "score": hit.score,
                "cached_response": payload.get("response"),
                "prompt": payload.get("prompt"),
                "tenant_id": payload.get("tenant_id"),
            }

        return None

    def store_cache(
        self, prompt: str, response: Dict[str, Any], tenant_id: str = "default"
    ):
        vector = self.get_embedding(prompt)
        point_id = str(uuid.uuid4())

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "prompt": prompt,
                        "response": response,
                        "tenant_id": tenant_id,
                    },
                )
            ],
        )

    def delete_cache(self, tenant_id: Optional[str] = None, purge_all: bool = False) -> int:
        """Invalidate cache entries for a specific tenant or purge all."""
        if purge_all:
            self.client.delete_collection(self.collection_name)
            self._init_collection()
            return -1  # Indicates full wipe

        if tenant_id:
            tenant_filter = Filter(
                must=[
                    FieldCondition(
                        key="tenant_id",
                        match=MatchValue(value=tenant_id)
                    )
                ]
            )
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=tenant_filter
            )
            return 1
        return 0