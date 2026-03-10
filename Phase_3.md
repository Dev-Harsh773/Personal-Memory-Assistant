# Project Plan: Real-Time Background Sync & Gallery UI Integration (Phase 3)

## 1. Context and Objective
We are building Phase 3 of a local Personal Memory Assistant. 
* Phase 1 (Image semantic search with SigLIP) and Phase 2 (Document chunking and search with BGE/ChromaDB) are complete. 
* The objective of Phase 3 is to implement real-time, silent background monitoring of the file system. When a supported new file is created or downloaded, it must be automatically processed and embedded into ChromaDB without user intervention. 
* Additionally, the existing Tkinter UI must be redesigned into a "Native Photo Gallery" style layout.
* **New Objective:** The application must operate as a persistent background utility, residing in the Windows system tray (taskbar) with a dropdown/context menu, allowing for instant access to the search interface.

## 2. Technical Stack & Constraints
* **Language:** Python
* **File System Monitoring:** Use the `watchdog` library to detect file creation and modification events.
* **Concurrency:** Use `threading` and the `queue` module to ensure background embedding does not freeze the Tkinter main loop.
* **Scope Exclusions:** Strictly ignore audio and video files. Only process images (.jpg, .png, etc.) and documents (.pdf, .docx, .txt, .pptx).
* **UI Framework:** `tkinter` combined with `PIL` (Pillow) for rendering image thumbnails.
* **System Tray Integration:** Use the `pystray` library (or equivalent) to handle taskbar icon placement, background execution, and right-click menus.

## 3. Required Implementation Steps

### Step 3a: The Watchdog File Monitor (`file_monitor.py`)
Create a background service script or class that:
1. Uses `watchdog.observers.Observer` to monitor the `Downloads` and `Documents` folders on the `C:\` drive, and the root of any other connected drives.
2. Implements a `FileSystemEventHandler` that listens specifically for `on_created` and `on_modified` events.
3. Filters out temporary files, `.crdownload` (Chrome unfinished downloads), and unsupported extensions.
4. **Implements Debouncing/Locking:** The script must wait until a file is completely written to the disk before attempting to read it (e.g., waiting for the file size to stop changing, or trying to open it in exclusive mode first).

### Step 3b: Background Processing Queue
1. Create a thread-safe `Queue`. When the Watchdog detects a new, completely saved file, it pushes the absolute file path to this queue.
2. Create a background worker thread that continuously checks this queue. 
3. When a path is popped from the queue, the worker determines if it is an image or a document, runs the existing embedding functions, and upserts the embeddings and metadata to ChromaDB silently.

### Step 3c: The "Photo Gallery" UI Merge (`app.py`)
Redesign the existing Tkinter interface to act as a unified, visually appealing gallery:
1. **The Layout:** Create a sleek, modern layout. Add a persistent semantic search bar at the top. The main area should be a scrollable `Canvas` or `Frame`.
2. **Image Results (Gallery View):** If the search results return images, display them in a dynamic, multi-column grid, generating lightweight thumbnails via `PIL`.
3. **Document Results (List View):** If the results return documents, display them as clean cards showing the file name, type icon, and the exact text chunk that matched the query.

### Step 3d: System Tray and Background Execution
Implement a robust taskbar presence:
1. **Minimize to Tray:** Override the default Tkinter window close/minimize behavior. When the user closes or minimizes the window, it should hide the window but keep the Python process and Watchdog monitor running.
2. **System Tray Icon (`pystray`):** Create a persistent icon in the Windows system tray.
3. **Left-Click Action:** When the user left-clicks (or double-clicks) the tray icon, the hidden Tkinter window must instantly reappear, bringing the search bar into focus.
4. **Right-Click Menu:** Implement a dropdown/context menu on the tray icon with options like "Open Search," "Force Sync," and "Quit" (which safely closes the database connections and kills the process).

## 4. Deliverables
1. The new `file_monitor.py` script containing the Watchdog logic and threading queue.
2. The overhauled `app.py` featuring the Gallery-style UI and the `pystray` system tray integration.
3. Updated `requirements.txt` to include `watchdog` and `pystray`.