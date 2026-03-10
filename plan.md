# Project Plan: Local Image Semantic Search Pipeline (Phase 1)

## 1. Context and Objective
We are building the first phase of a local Personal Memory Assistant. The goal of this phase is to implement an image processing and semantic search pipeline using Python. 

The system will process a local folder of test images, generate vector embeddings for them, store those embeddings persistently, and allow the user to search for images using natural language text prompts.

## 2. Technical Stack & Constraints
* **Language:** Python
* **Vision-Language Model:** `google/siglip-base-patch16-224` (or a similar lightweight SigLIP variant) via the Hugging Face `transformers` library.
* **Vector Database:** `chromadb` for local, persistent vector storage.
* **Categorization Rule:** **Strictly NO metadata tagging for categories** (e.g., do not implement `{"category": "car"}`). Categorization, grouping, and search must rely 100% on the vector embeddings and cosine/vector distance in the multi-modal space. The only metadata stored alongside the vector should be the absolute file path.
* **Execution Environment:** Everything must run entirely locally. Do not use any external APIs (like OpenAI) or cloud services.

## 3. Required Implementation Steps
Please generate a modular, well-documented Python script that implements the following core functions:

### `setup_db()`
* Initializes a persistent ChromaDB client saving to a local `./chroma_data` directory.
* Creates or retrieves a collection named `image_memory`.

### `get_image_embedding(image_path)`
* Loads an image from the local file system.
* Uses the SigLIP processor and vision model to generate a normalized vector embedding.
* Returns the embedding.

### `get_text_embedding(text_query)`
* Uses the SigLIP processor and text model to generate a normalized vector embedding for the user's natural language search prompt.
* Returns the embedding.

### `index_images(folder_path)`
* Iterates through all supported image files (e.g., .jpg, .png) in the given local directory.
* Extracts the embedding for each image using `get_image_embedding()`.
* Upserts the embedding, generating a unique ID, and stores the absolute file path as the only metadata into the ChromaDB collection.
* Includes basic `try/except` error handling to gracefully skip corrupted or unreadable files.

### `search_images(text_query, top_k=3)`
* Takes a user's text prompt (e.g., "a snowy mountain").
* Generates the text embedding using `get_text_embedding()`.
* Queries the ChromaDB collection for the closest vector matches.
* Returns the file paths of the top `k` most relevant results.

## 4. Deliverables
1.  Complete, executable Python code fulfilling the requirements above.
2.  A standard `if __name__ == "__main__":` execution block that demonstrates:
    * Setting an image folder path.
    * Running the indexing process.
    * Running a sample text search query and printing the resulting file paths.
3.  A commented section at the top of the script listing the required `pip install` dependencies (e.g., `torch`, `transformers`, `chromadb`, `Pillow`).