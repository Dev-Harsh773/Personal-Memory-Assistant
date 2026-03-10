"""
document_indexer.py — Document Embedding & ChromaDB Storage (Phase 2)

Uses BAAI/bge-large-en-v1.5 via sentence-transformers to generate high-accuracy
embeddings for document chunks and stores them in a separate ChromaDB collection.
"""

import os
import uuid
import warnings
import chromadb
from sentence_transformers import SentenceTransformer

from document_processor import extract_text, chunk_text

# Force offline mode — always use cached model
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

warnings.filterwarnings("ignore")

# High-accuracy embedding model for document retrieval
DOC_MODEL_NAME = "BAAI/bge-large-en-v1.5"

# Global model instance
doc_model = None


def load_doc_model():
    """Load the sentence-transformer model for document embeddings."""
    global doc_model
    if doc_model is None:
        print(f"Loading document model '{DOC_MODEL_NAME}'... (this might take a few moments)")
        doc_model = SentenceTransformer(DOC_MODEL_NAME)
    return doc_model


def setup_doc_db(db_path="./chroma_data", collection_name="document_memory"):
    """
    Initialize a ChromaDB collection specifically for document embeddings.
    Separate from the image_memory collection because embedding dimensions differ.
    """
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )
    return collection


def get_doc_text_embedding(text):
    """
    Generate a vector embedding for a text string using BGE-large.
    BGE models recommend prepending 'Represent this sentence:' for queries.
    """
    model = load_doc_model()
    try:
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        print(f"  Error generating doc embedding: {e}")
        return None


def get_doc_query_embedding(query):
    """
    Generate a query embedding with the BGE instruction prefix.
    BGE-large recommends prefixing queries with a specific instruction for retrieval.
    """
    model = load_doc_model()
    try:
        # BGE instruction prefix for retrieval queries
        instruction = "Represent this sentence for searching relevant passages: "
        embedding = model.encode(instruction + query, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        print(f"  Error generating doc query embedding: {e}")
        return None


def index_documents(file_dict, collection):
    """
    Index all categorized document files into ChromaDB.
    
    Args:
        file_dict: Output from scan_system_files(). We process pdf, word, ppt, txt categories.
        collection: ChromaDB collection to upsert into.
    """
    doc_categories = ["pdf", "word", "ppt", "txt"]
    
    total_chunks = 0
    total_files = 0
    
    for category in doc_categories:
        files = file_dict.get(category, [])
        if not files:
            continue
            
        print(f"\n--- Indexing {len(files)} {category.upper()} files ---")
        
        for file_path in files:
            try:
                # Extract text
                text = extract_text(file_path)
                if not text or len(text.strip()) < 20:
                    continue
                
                # Chunk the text
                chunks = chunk_text(text, chunk_size=500, overlap=50)
                if not chunks:
                    continue
                
                file_name = os.path.basename(file_path)
                print(f"  {file_name}: {len(chunks)} chunk(s)")
                
                # Embed and upsert each chunk
                for chunk_idx, chunk in enumerate(chunks):
                    embedding = get_doc_text_embedding(chunk)
                    if embedding is None:
                        continue
                    
                    doc_id = str(uuid.uuid4())
                    
                    # Store rich metadata for the UI to display
                    metadata = {
                        "file_path": file_path,
                        "file_type": category,
                        "chunk_text": chunk[:1000],  # ChromaDB metadata has size limits
                        "chunk_index": chunk_idx,
                        "total_chunks": len(chunks),
                        "type": "document"
                    }
                    
                    collection.upsert(
                        ids=[doc_id],
                        embeddings=[embedding],
                        metadatas=[metadata]
                    )
                    total_chunks += 1
                
                total_files += 1
                
            except Exception as e:
                print(f"  Error indexing '{file_path}': {e}")
                continue
    
    print(f"\n=== Document Indexing Complete ===")
    print(f"Files processed: {total_files}")
    print(f"Chunks indexed: {total_chunks}")


if __name__ == "__main__":
    from file_scanner import scan_system_files
    
    print("=== Personal Memory Assistant — Document Indexer ===\n")
    
    # 1. Scan for files
    print("[1] Scanning file system...")
    file_dict = scan_system_files()
    
    # 2. Setup document database
    print("\n[2] Setting up document database...")
    doc_collection = setup_doc_db()
    
    current_count = doc_collection.count()
    if current_count > 0:
        print(f"Document database already contains {current_count} chunks.")
        print("To re-index, delete the './chroma_data' folder and re-run.")
    else:
        # 3. Index documents
        print("\n[3] Indexing documents...")
        index_documents(file_dict, doc_collection)
    
    print("\nDone!")
