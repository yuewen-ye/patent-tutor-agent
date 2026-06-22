import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
import json
import chromadb
from chromadb.config import Settings
from transformers import AutoModel, AutoTokenizer
import torch
from tqdm import tqdm

CONFIG = {
    'chunked_json': r"backend\app\rag\data\chunked_txt.json",
    'chroma_db_path': r"backend\app\rag\data\rag_chroma_db",
    'collection_name': "patent_law_kb",
    'batch_size': 8,
    'device': 'cpu',
}

def load_model():
    tokenizer = AutoTokenizer.from_pretrained('BAAI/bge-m3')
    model = AutoModel.from_pretrained('BAAI/bge-m3').to(CONFIG['device'])
    model.eval()
    return tokenizer, model

def encode_batch(tokenizer, model, texts):
    with torch.no_grad():
        inputs = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors='pt')
        inputs = {k: v.to(CONFIG['device']) for k, v in inputs.items()}
        outputs = model(**inputs)
        embeddings = outputs.last_hidden_state[:, 0]
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
    return embeddings.cpu().numpy().tolist()

def main():
    with open(CONFIG['chunked_json'], 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    docs = data['level1_chapters'] + data['level2_parents'] + data['level3_children']
    
    client = chromadb.PersistentClient(
        path=CONFIG['chroma_db_path'],
        settings=Settings(anonymized_telemetry=False)
    )
    
    try:
        client.delete_collection(CONFIG['collection_name'])
    except:
        pass
    
    collection = client.create_collection(
        name=CONFIG['collection_name'],
        metadata={"hnsw:space": "cosine"}
    )
    
    tokenizer, model = load_model()
    
    for i in tqdm(range(0, len(docs), CONFIG['batch_size'])):
        batch = docs[i:i+CONFIG['batch_size']]
        
        ids = [d['id'] for d in batch]
        texts = [d['content'] for d in batch]
        vectors = encode_batch(tokenizer, model, texts)
        
        collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=[{
                'chapter_title': d.get('title', d.get('chapter_title', '')),
                'level': d['level'],
                'parent_id': d.get('parent_id', ''),
            } for d in batch]
        )

if __name__ == "__main__":
    main()