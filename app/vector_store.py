from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import Optional, Dict, Any, List
import uuid

class VectorCacheManager:
    def __init__(self, collection_name: str = "semantic_cache"):
        self.collection_name = collection_name
        
        # Load local CPU model (384-dimensional vectors)
        print("⚡ Pre-warming sentence-transformer model (all-MiniLM-L6-v2) on CPU...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
        
        # Initialize local Qdrant in-memory client for fast prototyping
        self.client = QdrantClient(":memory:")
        self._init_collection()

    def _init_collection(self):
        # Create collection if it doesn't exist
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            print(f"✅ Qdrant collection '{self.collection_name}' initialized.")

    def get_embedding(self, text: str) -> List[float]:
        """Generate 384-dim normalized vector for input text."""
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def search_similar(
        self, 
        query_text: str, 
        similarity_threshold: float = 0.85,
        tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Search vector cache for semantically matching prompts."""
        query_vector = self.get_embedding(query_text)
        
        search_result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=1
        ).points

        if search_result and search_result[0].score >= similarity_threshold:
            hit = search_result[0]
            payload = hit.payload or {}
            
            # Ensure tenant isolation if specified
            if tenant_id and payload.get("tenant_id") != tenant_id:
                return None

            return {
                "score": hit.score,
                "cached_response": payload.get("response"),
                "prompt": payload.get("prompt"),
                "tenant_id": payload.get("tenant_id")
            }
            
        return None

    def store_cache(self, prompt: str, response: Dict[str, Any], tenant_id: str = "default"):
        """Store prompt vector and response payload in Qdrant."""
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
                        "tenant_id": tenant_id
                    }
                )
            ]
        )