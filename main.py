"""
Required dependencies:
pip install torch torchvision transformers chromadb Pillow
"""

import os
import uuid
import warnings
import torch
from PIL import Image
import chromadb
from transformers import CLIPProcessor, CLIPModel

# Force offline mode — always use cached model, never phone home
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")

# Define the model to use
MODEL_NAME = "openai/clip-vit-large-patch14"

# Global variables to prevent reloading the model on every function call
processor = None
model = None

def load_model():
    """Loads the CLIP processor and model."""
    global processor, model
    if processor is None or model is None:
        print(f"Loading model '{MODEL_NAME}'... (this might take a few moments)")
        # Explicitly use CLIPProcessor and CLIPModel
        processor = CLIPProcessor.from_pretrained(MODEL_NAME)
        model = CLIPModel.from_pretrained(MODEL_NAME)
        model.eval()

def setup_db(db_path="./chroma_data", collection_name="image_memory"):
    """
    Initializes a persistent ChromaDB client and creates or retrieves a collection.
    """
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(
        name=collection_name, 
        metadata={"hnsw:space": "cosine"} # SigLIP embeddings work optimally with cosine similarity
    )
    return collection

def get_image_embedding(image_path):
    """
    Loads an image from the local file system and generates a normalized vector embedding.
    """
    load_model()
    try:
        image = Image.open(image_path).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            outputs = model.get_image_features(**inputs)
            
        # CLIPModel returns BaseModelOutputWithPooling
        if hasattr(outputs, "image_embeds") and outputs.image_embeds is not None:
             features = outputs.image_embeds
        elif hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
             features = outputs.pooler_output
        elif isinstance(outputs, (tuple, list)):
             features = outputs[0]
        else:
             features = outputs
             
        image_features = features / features.norm(p=2, dim=-1, keepdim=True)
        return image_features.squeeze(0).tolist()
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return None

def get_text_embedding(text_query):
    """
    Generates a normalized vector embedding for a natural language search prompt.
    """
    load_model()
    try:
        inputs = processor(text=[text_query], padding="max_length", return_tensors="pt")
        with torch.no_grad():
            outputs = model.get_text_features(**inputs)
            
        if hasattr(outputs, "text_embeds") and outputs.text_embeds is not None:
             features = outputs.text_embeds
        elif hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
             features = outputs.pooler_output
        elif isinstance(outputs, (tuple, list)):
             features = outputs[0]
        else:
             features = outputs
             
        text_features = features / features.norm(p=2, dim=-1, keepdim=True)
        return text_features.squeeze(0).tolist()
    except Exception as e:
        print(f"Error processing text query '{text_query}': {e}")
        return None

def index_images(folder_path, collection):
    """
    Iterates through image files, extracts embeddings, and upserts them into ChromaDB.
    """
    supported_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}
    
    if not os.path.exists(folder_path):
        print(f"Error: Directory '{folder_path}' does not exist.")
        return

    print(f"Starting to index images in '{folder_path}'...")
    
    count = 0
    for root, _, files in os.walk(folder_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in supported_extensions:
                abs_path = os.path.abspath(os.path.join(root, file))
                
                print(f"Processing: {abs_path}")
                embedding = get_image_embedding(abs_path)
                
                if embedding is not None:
                    # Generate a unique ID
                    doc_id = str(uuid.uuid4())
                    
                    collection.upsert(
                        ids=[doc_id],
                        embeddings=[embedding],
                        metadatas=[{"file_path": abs_path}]
                    )
                    count += 1

    print(f"Successfully indexed {count} images.")

def search_images(text_query, collection, top_k=3):
    """
    Queries ChromaDB for the closest image vectors matching the text query.
    """
    query_embedding = get_text_embedding(text_query)
    
    if not query_embedding:
        print("Failed to generate embedding for the search query.")
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    
    filepaths = []
    if results and "metadatas" in results and results["metadatas"]:
        for metadata_list in results["metadatas"]:
            if metadata_list:
                for metadata in metadata_list:
                    filepaths.append(metadata["file_path"])
                
    return filepaths

if __name__ == "__main__":
    print("--- Personal Memory Assistant (Phase 1) Search Pipeline ---")
    
    # 1. Setup Phase
    print("\n[1] Setting up Database...")
    db_collection = setup_db()
    
    # 2. Indexing Phase
    # Path defaults to the dataset user mentioned. Fallback to general archive if nested doesn't exist.
    IMAGE_FOLDER = r"D:\Anti_Gravity\Projects\archive\unsplash-images-collection"
    if not os.path.exists(IMAGE_FOLDER):
        IMAGE_FOLDER = r"D:\Anti_Gravity\Projects\archive"
        
    print(f"\n[2] Checking Database for existing images...")
    current_count = db_collection.count()
    if current_count == 0:
        index_images(IMAGE_FOLDER, db_collection)
    else:
        print(f"Database already contains {current_count} indexed images.")
        print("Skipping full re-index. (To re-index, delete the './chroma_data' folder)")

    # 3. Search Phase
    print("\n[3] Running Sample Queries...")
    sample_queries = [
        "a snowy mountain",
        "a dark forest",
        "people walking in a city"
    ]
    
    for query in sample_queries:
        print(f"\nSearching for: '{query}'")
        top_results = search_images(query, db_collection, top_k=3)
        
        if top_results:
            print("Top Matches:")
            for i, path in enumerate(top_results, 1):
                print(f"  {i}. {path}")
        else:
            print("No matching images found. Have you indexed images yet?")
