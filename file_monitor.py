"""
file_monitor.py — Real-Time File System Monitor (Phase 3)

Uses watchdog to monitor directories for new files, debounces them,
and auto-embeds them into ChromaDB via a background worker thread.
"""

import os
import sys
import time
import uuid
import queue
import string
import threading
import warnings
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

warnings.filterwarnings("ignore")

# Supported extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}
DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md", ".csv"}

# Extensions to always skip
SKIP_EXTENSIONS = {
    ".crdownload", ".tmp", ".part", ".partial", ".download",
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma",
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
    ".exe", ".dll", ".sys", ".msi", ".bat", ".cmd",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".iso", ".img", ".vmdk", ".log",
}

# Directories to skip
SKIP_DIRS = {
    "$Recycle.Bin", "System Volume Information", "Windows",
    "ProgramData", "Program Files", "Program Files (x86)",
    "node_modules", "__pycache__", ".git", "venv", ".venv",
    "AppData", "Recovery", "PerfLogs",
}

DEBOUNCE_SECONDS = 3.0


def _log(msg):
    """Print with flush to ensure output is visible immediately."""
    print(f"[Monitor] {msg}", flush=True)


class MemoryEventHandler(FileSystemEventHandler):
    """Handles file creation/modification events, filters and debounces."""

    def __init__(self, file_queue):
        super().__init__()
        self._file_queue = file_queue
        self._seen = {}  # path -> last_seen_time for debouncing
        self._lock = threading.Lock()

    def _should_process(self, path):
        """Check if a file path should be processed."""
        if not os.path.isfile(path):
            return False

        # Check if in a skip directory
        parts = path.replace("/", "\\").split("\\")
        for part in parts:
            if part in SKIP_DIRS:
                return False

        ext = os.path.splitext(path)[1].lower()
        if ext in SKIP_EXTENSIONS:
            return False
        if ext not in IMAGE_EXTENSIONS and ext not in DOC_EXTENSIONS:
            return False

        return True

    def _debounce_and_queue(self, path):
        """Wait for file to finish writing, then queue it."""
        now = time.time()

        with self._lock:
            # Skip if we saw this file very recently
            if path in self._seen and (now - self._seen[path]) < DEBOUNCE_SECONDS:
                return
            self._seen[path] = now

        _log(f"Detected: {os.path.basename(path)}")

        # Schedule debounced check in a thread
        threading.Thread(
            target=self._wait_and_queue, args=(path,), daemon=True
        ).start()

    def _wait_and_queue(self, path):
        """Wait until file size stabilizes, then add to queue."""
        try:
            _log(f"Waiting for file to finish writing: {os.path.basename(path)}")
            time.sleep(DEBOUNCE_SECONDS)

            # Check size stability
            for attempt in range(3):
                try:
                    if not os.path.exists(path):
                        _log(f"File disappeared: {os.path.basename(path)}")
                        return
                    size1 = os.path.getsize(path)
                    time.sleep(1.0)
                    size2 = os.path.getsize(path)
                    if size1 == size2 and size2 > 0:
                        break  # File is stable
                    _log(f"File still writing (attempt {attempt+1}): {os.path.basename(path)}")
                except OSError:
                    return
            else:
                _log(f"File never stabilized, skipping: {os.path.basename(path)}")
                return

            # Try to open exclusively to confirm it's not locked
            try:
                with open(path, "rb") as f:
                    f.read(1)  # Read 1 byte to verify access
            except (PermissionError, IOError):
                _log(f"File still locked, waiting more: {os.path.basename(path)}")
                time.sleep(3.0)

            self._file_queue.put(path)
            _log(f"Queued for embedding: {os.path.basename(path)}")

        except Exception as e:
            _log(f"Debounce error for {os.path.basename(path)}: {e}")

    def on_created(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            self._debounce_and_queue(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            self._debounce_and_queue(event.src_path)


class FileMonitor:
    """
    Manages Watchdog observer and a background worker that auto-embeds
    new files into ChromaDB.
    """

    def __init__(self, image_collection, doc_collection, on_file_indexed=None):
        self._image_collection = image_collection
        self._doc_collection = doc_collection
        self._on_file_indexed = on_file_indexed
        self._queue = queue.Queue()
        self._observer = Observer()
        self._handler = MemoryEventHandler(self._queue)
        self._worker_thread = None
        self._running = False
        self._files_indexed = 0

    @property
    def files_indexed(self):
        return self._files_indexed

    @property
    def is_running(self):
        return self._running

    def _get_watch_paths(self):
        """Get list of directories to monitor."""
        paths = []
        user_profile = os.environ.get("USERPROFILE", "C:\\Users\\Default")

        # C: drive — only Downloads and Documents
        for folder in ["Downloads", "Documents", "Desktop"]:
            p = os.path.join(user_profile, folder)
            if os.path.exists(p):
                paths.append(p)

        # Other drives — watch root but NOT recursive (too heavy)
        # Instead, watch common top-level folders
        for letter in string.ascii_uppercase:
            if letter == "C":
                continue
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                # Watch the drive root non-recursively first
                paths.append(drive)

        return paths

    def start(self):
        """Start the file monitor and background worker."""
        if self._running:
            return

        self._running = True
        watch_paths = self._get_watch_paths()

        _log(f"Starting watchdog on {len(watch_paths)} paths:")
        for p in watch_paths:
            try:
                # Use recursive=True only for user folders, not entire drives
                is_user_folder = "Users" in p
                self._observer.schedule(
                    self._handler, p, recursive=is_user_folder
                )
                _log(f"  ✓ {p} (recursive={is_user_folder})")
            except Exception as e:
                _log(f"  ✗ {p} — Error: {e}")

        try:
            self._observer.start()
            _log("Observer started successfully.")
        except Exception as e:
            _log(f"Observer failed to start: {e}")
            self._running = False
            return

        # Start background worker
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True
        )
        self._worker_thread.start()
        _log("Background worker started. Monitoring active.")

    def stop(self):
        """Stop the monitor cleanly."""
        _log("Stopping...")
        self._running = False
        try:
            self._observer.stop()
            self._observer.join(timeout=3)
        except Exception:
            pass
        _log("Stopped.")

    def _worker_loop(self):
        """Background worker that processes queued files."""
        _log("Worker loop running.")
        while self._running:
            try:
                path = self._queue.get(timeout=2.0)
            except queue.Empty:
                continue

            try:
                ext = os.path.splitext(path)[1].lower()
                abs_path = os.path.abspath(path)

                # Check if already indexed (prevent duplicates)
                if ext in IMAGE_EXTENSIONS:
                    existing = self._image_collection.get(
                        where={"file_path": abs_path}, include=[]
                    )
                    if existing and existing['ids']:
                        _log(f"⏭ Already indexed, skipping: {os.path.basename(path)}")
                        continue
                    self._embed_image(path)
                elif ext in DOC_EXTENSIONS:
                    existing = self._doc_collection.get(
                        where={"file_path": abs_path}, include=[]
                    )
                    if existing and existing['ids']:
                        _log(f"⏭ Already indexed, skipping: {os.path.basename(path)}")
                        continue
                    self._embed_document(path)

                self._files_indexed += 1
                _log(f"✓ Indexed! Total auto-indexed: {self._files_indexed}")

                if self._on_file_indexed:
                    self._on_file_indexed(path)

            except Exception as e:
                _log(f"✗ Error processing {os.path.basename(path)}: {e}")

    def _embed_image(self, path):
        """Embed a single image into ChromaDB."""
        from main import get_image_embedding

        _log(f"Embedding image: {os.path.basename(path)}")
        embedding = get_image_embedding(path)
        if embedding:
            self._image_collection.upsert(
                ids=[str(uuid.uuid4())],
                embeddings=[embedding],
                metadatas=[{"file_path": os.path.abspath(path)}]
            )
            _log(f"✓ Image embedded: {os.path.basename(path)}")
        else:
            _log(f"✗ Failed to generate embedding for: {os.path.basename(path)}")

    def _embed_document(self, path):
        """Embed a document (with chunking) into ChromaDB."""
        from document_processor import extract_text, chunk_text
        from document_indexer import get_doc_text_embedding

        _log(f"Embedding document: {os.path.basename(path)}")
        text = extract_text(path)
        if not text or len(text.strip()) < 20:
            _log(f"✗ No text extracted from: {os.path.basename(path)}")
            return

        chunks = chunk_text(text, chunk_size=500, overlap=50)
        ext = os.path.splitext(path)[1].lower()
        file_type = "pdf" if ext == ".pdf" else \
                    "word" if ext in (".doc", ".docx") else \
                    "ppt" if ext in (".ppt", ".pptx") else "txt"

        for idx, chunk in enumerate(chunks):
            embedding = get_doc_text_embedding(chunk)
            if embedding:
                self._doc_collection.upsert(
                    ids=[str(uuid.uuid4())],
                    embeddings=[embedding],
                    metadatas=[{
                        "file_path": os.path.abspath(path),
                        "file_type": file_type,
                        "chunk_text": chunk[:1000],
                        "chunk_index": idx,
                        "total_chunks": len(chunks),
                        "type": "document"
                    }]
                )
        _log(f"✓ Document embedded: {os.path.basename(path)} ({len(chunks)} chunks)")


if __name__ == "__main__":
    from main import setup_db
    from document_indexer import setup_doc_db

    _log("=== File Monitor — Standalone Test ===")
    img_col = setup_db()
    doc_col = setup_doc_db()

    monitor = FileMonitor(img_col, doc_col)
    monitor.start()

    try:
        _log("Monitoring... Press Ctrl+C to stop.")
        _log("Try saving a file to Downloads to test!")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        _log("Done.")
