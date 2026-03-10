"""Verify unicorn search after cleanup."""
import os, sys
sys.path.insert(0, r'd:\Anti_Gravity\Projects')
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
import warnings; warnings.filterwarnings('ignore')
import chromadb
from main import get_text_embedding

client = chromadb.PersistentClient(path="./chroma_data")
col = client.get_or_create_collection(name="image_memory", metadata={"hnsw:space": "cosine"})
print(f"Collection: {col.count()} entries", flush=True)

emb = get_text_embedding("unicorn")
if emb:
    r = col.query(query_embeddings=[emb], n_results=10, include=['metadatas','distances'])
    print(f"\nTop 10 for 'unicorn':", flush=True)
    for i in range(len(r['metadatas'][0])):
        d = r['distances'][0][i]
        p = os.path.basename(r['metadatas'][0][i]['file_path'])
        print(f"  {i+1}. dist={d:.4f}  sim={1-d:.4f}  {p}", flush=True)
