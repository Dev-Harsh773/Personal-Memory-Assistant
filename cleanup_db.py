"""Deduplicate ChromaDB image_memory collection — keeps 1 entry per unique file_path."""
import os, sys
sys.path.insert(0, r'd:\Anti_Gravity\Projects')
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
import warnings; warnings.filterwarnings('ignore')
import chromadb

client = chromadb.PersistentClient(path="./chroma_data")
col = client.get_or_create_collection(name="image_memory", metadata={"hnsw:space": "cosine"})

print(f"Before cleanup: {col.count()} entries", flush=True)

# Get ALL entries
all_data = col.get(include=['metadatas'])
ids = all_data['ids']
metas = all_data['metadatas']

# Group by file_path
path_to_ids = {}
for id_, meta in zip(ids, metas):
    fp = meta.get('file_path', '')
    if fp not in path_to_ids:
        path_to_ids[fp] = []
    path_to_ids[fp].append(id_)

# Find duplicate IDs to delete (keep the first one per path)
ids_to_delete = []
duplicate_paths = 0
for fp, id_list in path_to_ids.items():
    if len(id_list) > 1:
        duplicate_paths += 1
        ids_to_delete.extend(id_list[1:])  # Keep first, delete rest

print(f"Unique file paths: {len(path_to_ids)}", flush=True)
print(f"Paths with duplicates: {duplicate_paths}", flush=True)
print(f"Entries to delete: {len(ids_to_delete)}", flush=True)

# Delete in batches (ChromaDB has batch limits)
batch_size = 500
for i in range(0, len(ids_to_delete), batch_size):
    batch = ids_to_delete[i:i+batch_size]
    col.delete(ids=batch)
    print(f"  Deleted batch {i//batch_size + 1} ({len(batch)} entries)", flush=True)

print(f"\nAfter cleanup: {col.count()} entries", flush=True)
print("Done! Duplicates removed.", flush=True)
