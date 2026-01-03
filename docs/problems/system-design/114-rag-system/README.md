# RAG System Design

## Problem Overview

Design a Retrieval Augmented Generation system for 10K organizations with 1B document chunks, supporting <3s query latency.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Document Ingestion Pipeline                            │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ Document │─▶│   Chunking   │─▶│  Embedding   │─▶│   Vector     │            │
│  │ Upload   │  │   Service    │  │   Service    │  │   Store      │            │
│  └──────────┘  └──────────────┘  └──────────────┘  └──────────────┘            │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Query Pipeline                                      │
│                                                                                  │
│  User Query                                                                      │
│      │                                                                           │
│      ▼                                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Query      │───▶│   Vector     │───▶│   Reranker   │───▶│   Context    │  │
│  │   Embedding  │    │   Search     │    │              │    │   Assembly   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘  │
│                                                                      │          │
│                                                                      ▼          │
│                                                              ┌──────────────┐   │
│                                                              │     LLM      │   │
│                                                              │  Generation  │   │
│                                                              └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Document Processing

```python
from dataclasses import dataclass
from typing import List
import tiktoken

@dataclass
class Chunk:
    id: str
    document_id: str
    content: str
    embedding: List[float]
    metadata: dict
    start_char: int
    end_char: int

class ChunkingService:
    """Intelligent document chunking."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def chunk_document(self, document: str, metadata: dict) -> List[Chunk]:
        """Chunk document using semantic boundaries."""
        chunks = []
        doc_id = metadata.get("document_id", str(uuid.uuid4()))

        # Split by paragraphs first
        paragraphs = document.split("\n\n")

        current_chunk = ""
        current_start = 0

        for para in paragraphs:
            para_tokens = len(self.tokenizer.encode(para))

            if para_tokens > self.chunk_size:
                # Paragraph too long, split by sentences
                sentences = self.split_sentences(para)
                for sentence in sentences:
                    if len(self.tokenizer.encode(current_chunk + sentence)) > self.chunk_size:
                        if current_chunk:
                            chunks.append(self.create_chunk(
                                doc_id, current_chunk, current_start, metadata
                            ))
                        current_chunk = sentence
                        current_start = document.find(sentence)
                    else:
                        current_chunk += " " + sentence
            else:
                if len(self.tokenizer.encode(current_chunk + para)) > self.chunk_size:
                    if current_chunk:
                        chunks.append(self.create_chunk(
                            doc_id, current_chunk, current_start, metadata
                        ))
                    current_chunk = para
                    current_start = document.find(para)
                else:
                    current_chunk += "\n\n" + para

        if current_chunk:
            chunks.append(self.create_chunk(
                doc_id, current_chunk, current_start, metadata
            ))

        return chunks


class EmbeddingService:
    """Generate embeddings for text."""

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.dimension = 1536

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={"input": texts, "model": self.model}
            ) as response:
                result = await response.json()
                return [d["embedding"] for d in result["data"]]

    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed([text])
        return embeddings[0]
```

#### 2. Vector Search

```python
class VectorStore:
    """Vector database with hybrid search."""

    def __init__(self, pinecone_client):
        self.pinecone = pinecone_client

    async def upsert(self, chunks: List[Chunk], namespace: str):
        """Insert chunks into vector store."""
        vectors = [
            {
                "id": chunk.id,
                "values": chunk.embedding,
                "metadata": {
                    "document_id": chunk.document_id,
                    "content": chunk.content[:1000],  # Truncate for metadata limit
                    **chunk.metadata
                }
            }
            for chunk in chunks
        ]

        await self.pinecone.upsert(
            vectors=vectors,
            namespace=namespace
        )

    async def search(
        self,
        query_embedding: List[float],
        namespace: str,
        top_k: int = 10,
        filter: dict = None
    ) -> List[dict]:
        """Semantic search."""
        results = await self.pinecone.query(
            vector=query_embedding,
            namespace=namespace,
            top_k=top_k,
            filter=filter,
            include_metadata=True
        )

        return [
            {
                "id": match["id"],
                "score": match["score"],
                "content": match["metadata"]["content"],
                "document_id": match["metadata"]["document_id"],
                "metadata": match["metadata"]
            }
            for match in results["matches"]
        ]


class HybridSearch:
    """Combines vector search with keyword search."""

    async def search(
        self,
        query: str,
        query_embedding: List[float],
        namespace: str,
        top_k: int = 10
    ) -> List[dict]:
        """Perform hybrid search."""
        # Vector search
        vector_results = await self.vector_store.search(
            query_embedding, namespace, top_k=top_k * 2
        )

        # Keyword search (BM25)
        keyword_results = await self.elasticsearch.search(
            index=namespace,
            query={"match": {"content": query}},
            size=top_k * 2
        )

        # Reciprocal Rank Fusion
        combined = self.rrf_fusion(vector_results, keyword_results)

        return combined[:top_k]

    def rrf_fusion(
        self,
        vector_results: List[dict],
        keyword_results: List[dict],
        k: int = 60
    ) -> List[dict]:
        """Combine results using Reciprocal Rank Fusion."""
        scores = {}

        for rank, result in enumerate(vector_results):
            doc_id = result["id"]
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)

        for rank, result in enumerate(keyword_results):
            doc_id = result["_id"]
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)

        # Sort by combined score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        return [
            {"id": doc_id, "score": scores[doc_id]}
            for doc_id in sorted_ids
        ]
```

#### 3. RAG Query

```python
class RAGService:
    """Complete RAG query pipeline."""

    def __init__(
        self,
        embedding_service,
        vector_store,
        reranker,
        llm_client
    ):
        self.embeddings = embedding_service
        self.vectors = vector_store
        self.reranker = reranker
        self.llm = llm_client

    async def query(
        self,
        query: str,
        namespace: str,
        top_k: int = 5,
        stream: bool = True
    ) -> AsyncIterator[str]:
        """Execute RAG query."""
        # 1. Embed query
        query_embedding = await self.embeddings.embed_single(query)

        # 2. Retrieve candidates
        candidates = await self.vectors.search(
            query_embedding,
            namespace,
            top_k=top_k * 3  # Get more for reranking
        )

        # 3. Rerank
        reranked = await self.reranker.rerank(query, candidates)
        top_chunks = reranked[:top_k]

        # 4. Assemble context
        context = self.assemble_context(top_chunks)

        # 5. Generate answer
        prompt = self.build_prompt(query, context, top_chunks)

        async for token in self.llm.generate(prompt, stream=stream):
            yield token

    def assemble_context(self, chunks: List[dict]) -> str:
        """Assemble retrieved chunks into context."""
        context_parts = []
        for i, chunk in enumerate(chunks):
            context_parts.append(f"[Source {i+1}]\n{chunk['content']}")
        return "\n\n".join(context_parts)

    def build_prompt(
        self,
        query: str,
        context: str,
        chunks: List[dict]
    ) -> str:
        """Build prompt with context and citations."""
        return f"""Answer the following question based on the provided context.
Include citations in [Source N] format when using information from the sources.

Context:
{context}

Question: {query}

Answer:"""


class Reranker:
    """Cross-encoder reranking for improved relevance."""

    async def rerank(
        self,
        query: str,
        documents: List[dict],
        top_k: int = None
    ) -> List[dict]:
        """Rerank documents using cross-encoder."""
        if not documents:
            return []

        # Score each document
        pairs = [(query, doc["content"]) for doc in documents]

        scores = await self.cross_encoder.score(pairs)

        # Combine with document data
        for doc, score in zip(documents, scores):
            doc["rerank_score"] = score

        # Sort by rerank score
        reranked = sorted(
            documents,
            key=lambda x: x["rerank_score"],
            reverse=True
        )

        return reranked[:top_k] if top_k else reranked
```

### Testing

```python
class TestRAG:
    async def test_document_ingestion(self, rag_service):
        """Test document upload and chunking."""
        document = "This is a long document..." * 100

        result = await rag_service.ingest_document(
            content=document,
            metadata={"source": "test.pdf"}
        )

        assert result["chunks_created"] > 0
        assert result["status"] == "success"

    async def test_query(self, rag_service):
        """Test RAG query."""
        # First ingest some documents
        await rag_service.ingest_document(
            content="The capital of France is Paris.",
            metadata={"source": "geography.txt"}
        )

        # Query
        response = ""
        async for token in rag_service.query("What is the capital of France?"):
            response += token

        assert "Paris" in response

    async def test_citations(self, rag_service):
        """Test citation generation."""
        response = await rag_service.query_with_citations(
            "What is the population of Tokyo?"
        )

        assert len(response["citations"]) > 0
        assert "[Source" in response["answer"]

    async def test_retrieval_accuracy(self, rag_service):
        """Test retrieval quality."""
        # Ingest test documents
        await rag_service.ingest_document(
            content="Python is a programming language.",
            metadata={"topic": "programming"}
        )
        await rag_service.ingest_document(
            content="France is a country in Europe.",
            metadata={"topic": "geography"}
        )

        # Query should retrieve relevant document
        results = await rag_service.retrieve("programming languages")
        assert any("Python" in r["content"] for r in results)
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Query Latency | < 3 seconds |
| Retrieval Accuracy | > 90% |
| Ingestion Throughput | > 1000 docs/min |
| Answer Relevance | > 85% |
