from __future__ import annotations

import os
from backend.app.schemas.state import RetrievalChunk, RetrievalMetadata

DB_PATH = r"backend\app\rag\data\rag_chroma_db"

RAG_CONFIG = {
    'db_path': os.getenv('RAG_DB_PATH', DB_PATH),
    'collection_name': os.getenv('RAG_COLLECTION_NAME', "patent_law_kb"),
    'device': 'cpu',
}

_embedding_model = None
_chroma_collection = None
_chromadb = None
_transformers = None
_torch = None

def _lazy_import():
    global _chromadb, _transformers, _torch
    if _chromadb is None:
        import chromadb
        from chromadb.config import Settings
        _chromadb = (chromadb, Settings)
    
    if _transformers is None:
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        from transformers import AutoModel, AutoTokenizer
        _transformers = (AutoModel, AutoTokenizer)
    
    if _torch is None:
        import torch
        _torch = torch

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _lazy_import()
        AutoModel, AutoTokenizer = _transformers
        torch = _torch
        
        tokenizer = AutoTokenizer.from_pretrained('BAAI/bge-m3')
        model = AutoModel.from_pretrained('BAAI/bge-m3').to(RAG_CONFIG['device'])
        model.eval()
        _embedding_model = (tokenizer, model)
    
    return _embedding_model

def get_chroma_collection():
    global _chroma_collection
    if _chroma_collection is None:
        _lazy_import()
        chromadb, Settings = _chromadb
        
        db_path = os.path.abspath(RAG_CONFIG['db_path'])
        
        client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        collections = client.list_collections()
        _chroma_collection = client.get_collection(name=RAG_CONFIG['collection_name'])
    return _chroma_collection

def encode_query(query: str) -> list[float]:
    tokenizer, model = get_embedding_model()
    torch = _torch
    
    with torch.no_grad():
        inputs = tokenizer([query], padding=True, truncation=True, max_length=512, return_tensors='pt')
        inputs = {k: v.to(RAG_CONFIG['device']) for k, v in inputs.items()}
        outputs = model(**inputs)
        embeddings = outputs.last_hidden_state[:, 0]
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
    return embeddings.cpu().numpy().tolist()[0]

def rag_retrieve(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
    if not query:
        return []
    
    try:
        collection = get_chroma_collection()
        query_vector = encode_query(query)
        
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, collection.count()),
            include=['documents', 'metadatas', 'distances'],
        )
        
        chunks = []
        for i in range(len(results['documents'][0])):
            similarity = 1 - results['distances'][0][i]
            meta = results['metadatas'][0][i]
            
            chunks.append(RetrievalChunk(
                chunk_id=results['ids'][0][i],
                source="专利代理条例",
                citation=meta['chapter_title'],
                text=results['documents'][0][i],
                score=similarity,
                metadata=RetrievalMetadata(
                    doc_type="law",
                    law_article=meta['chapter_title'],
                    retrieval_method="vector",
                ),
            ))
        
        return chunks
    
    except Exception as e:
        print(f"[RAG] 检索失败: {e}")
        return []