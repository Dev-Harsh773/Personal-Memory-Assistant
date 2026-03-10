# Project Plan: Document Scanning, Extraction, and Semantic Search (Phase 2)

## 1. Context and Objective
We are building Phase 2 of a local Personal Memory Assistant. Phase 1 (Image semantic search using SigLIP and ChromaDB) is complete. 
The objective of Phase 2 is to expand the system to index and search document files (PDF, DOCX, TXT, PPTX). The system must scan specific Windows directories, categorize files into a data structure, extract text, generate high-accuracy vector embeddings, store them in the existing ChromaDB, and update the `app.py` UI to support universal multimodal search.

## 2. Technical Stack & Constraints
* **Language:** Python
* **Embedding Model (Accuracy Priority):** Use `BAAI/bge-large-en-v1.5` or `sentence-transformers/all-mpnet-base-v2` via Hugging Face `sentence-transformers`. Do not use fast/lightweight models like MiniLM; prioritize retrieval accuracy.
* **Vector Database:** `chromadb` (integrating with the existing setup).
* **Text Extraction Libraries:** `PyMuPDF` (for PDF), `python-docx` (for Word), `python-pptx` (for PPT), and standard I/O for TXT.
* **Scope Exclusions:** Explicitly skip audio (.mp3, .wav) and video (.mp4, .mkv, etc.) files for now.

## 3. Required Implementation Steps

### Step 3a: Intelligent Directory Scanning (WinDirStat Style)
Write a function `scan_system_files()` that:
1. Dynamically identifies all available drive letters on the Windows system (e.g., C:\, D:\, E:\).
2. For the `C:\` drive, it MUST ONLY scan the user's `Downloads` and `Documents` folders (construct paths dynamically using `os.environ['USERPROFILE']`).
3. For all other available drives (e.g., `D:\`), it must do a complete recursive scan of the entire drive.
4. Returns a categorized data structure (dictionary) grouping discovered absolute file paths by type. Example: 
   `{ "images": [...], "pdf": [...], "word": [...], "ppt": [...], "txt": [...] }`

### Step 3b: Text Extraction and Chunking
Write a module `document_processor.py` containing:
1. Extraction functions for each supported format using the specified libraries.
2. A robust **Text Chunking Algorithm**. High-accuracy embedding models have strict token limits (usually 512). The script must split long extracted document text into overlapping chunks (e.g., 500 words per chunk with a 50-word overlap) so no context is lost.

### Step 3c: High-Accuracy Embedding & Storage
Update the indexing logic to:
1. Iterate through the categorized document lists (from Step 3a).
2. Extract and chunk the text.
3. Pass each chunk through the chosen high-accuracy sentence transformer model to get the vector embedding.
4. Upsert the embeddings into ChromaDB. For documents, store the absolute file path and the specific "chunk text" as metadata so the UI can display the relevant paragraph that matched the search.

### Step 3d: Unified Search & UI Update (`app.py`)
Update the main application file:
1. Modify the search logic so that when a user enters a text query, the system embeds the query using *both* the text model (for documents) and the SigLIP text processor (for images).
2. Query ChromaDB to retrieve the most mathematically relevant results across both vector spaces.
3. Update the UI layout to display the results clearly, showing the image preview for image matches, and the file path + extracted text snippet (chunk) for document matches.

## 4. Deliverables
1. Complete Python code for the new scanning and extraction modules.
2. Updated indexing script that handles the document chunking and database upserting.
3. The updated `app.py` script featuring the unified multimodal search interface.
4. An updated `requirements.txt` block including `PyMuPDF`, `python-docx`, `python-pptx`, and any other required libraries.