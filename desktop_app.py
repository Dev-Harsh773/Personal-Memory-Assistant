"""
desktop_app.py — Personal Memory Assistant (PyQt5)

Glassmorphism UI with:
  - Background image (background.jpg)
  - Neon-glow search bar with pop-up on hover
  - Centered search → animates up on search
  - Home button + Info button
  - Hover effects on all tiles
  - System tray + background file monitoring
"""

import os
import sys
import uuid
import threading

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

# IMPORTANT: torch must be imported BEFORE PyQt5 to avoid DLL conflicts
import torch  # noqa: F401

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QGridLayout,
    QFrame, QMenu, QAction, QSystemTrayIcon, QStyle,
    QGraphicsDropShadowEffect, QToolButton, QActionGroup,
    QGraphicsOpacityEffect, QMessageBox
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QTimer,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QSequentialAnimationGroup, QPoint, QRect, pyqtProperty, QAbstractAnimation
)
from PyQt5.QtGui import (
    QPixmap, QFont, QColor, QPainter, QLinearGradient, QBrush
)

import chromadb
from main import get_text_embedding, get_image_embedding
from document_indexer import get_doc_query_embedding, setup_doc_db, index_documents
from file_scanner import scan_system_files
from file_monitor import FileMonitor


# ─── Colors ───────────────────────────────────────────────────────
TEXT        = "#dcd5e2"
TEXT2       = "#8a8095"
TEXT3       = "#5a5568"
ACCENT      = "#a090c0"
PANEL_SOLID = "#2e2838"
PANEL_HOVER = "#3d3548"
GREEN       = "#6fcf97"
AMBER       = "#f2c94c"
RED         = "#eb5757"
ORANGE      = "#f2994a"

GLOW_PURPLE = "#8a5cf5"
GLOW_WHITE  = "#d4c8ff"
GLOW_BORDER = "#b8a8ff"

# Background image
BG_IMAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background.jpg")


def _normalize_score(similarity, min_sim, max_sim):
    n = (similarity - min_sim) / (max_sim - min_sim)
    return max(0.0, min(100.0, n * 100.0))


# ─── Info dialog text ─────────────────────────────────────────────
INFO_TEXT = """
<h2 style="color:#d4c8ff;">Memory Assistant — How to Use</h2>

<p style="color:#dcd5e2;">
<b>🔍 Search Bar</b><br>
Type any natural language query and press Enter or click Search.<br>
Examples: "sunset on beach", "invoice from March", "cat photo"
</p>

<p style="color:#dcd5e2;">
<b>≡ Sidebar Menu (top-left)</b><br>
• <b>Images / Documents</b> — switch search mode<br>
• <b>Scan Files</b> — discover all files on your system (first-time setup)<br>
• <b>Index Documents</b> — embed documents for search (after scanning)<br>
• <b>Index Images</b> — embed images for search (after scanning)<br>
• <b>Sync New Files</b> — scan and index only NEW files not yet in database<br>
</p>

<p style="color:#dcd5e2;">
<b>⌂ Home Button</b><br>
Return to the home screen after searching.
</p>

<p style="color:#dcd5e2;">
<b>🟢 Green Dot (top-right)</b><br>
Indicates the background file monitor is active. New files you download
or create are automatically indexed in real-time — no action needed!
</p>

<p style="color:#dcd5e2;">
<b>System Tray</b><br>
Closing the window minimizes to the system tray. The monitor keeps running.
Double-click the tray icon to reopen. Right-click for a quick menu.
</p>
"""


# ─── Search Worker Thread ─────────────────────────────────────────
class SearchWorker(QThread):
    results_ready = pyqtSignal(list, str)

    def __init__(self, query, mode, image_col, doc_col):
        super().__init__()
        self.query = query
        self.mode = mode
        self.image_col = image_col
        self.doc_col = doc_col

    def run(self):
        matches = []
        if self.mode == "Images":
            try:
                emb = get_text_embedding(self.query)
                if emb:
                    res = self.image_col.query(
                        query_embeddings=[emb], n_results=20,
                        include=["metadatas", "distances"]
                    )
                    if res and res.get("metadatas") and res.get("distances"):
                        for i in range(len(res["metadatas"][0])):
                            sim = 1.0 - res["distances"][0][i]
                            pct = _normalize_score(sim, 0.15, 0.35)
                            if pct > 0:
                                matches.append({
                                    "type": "image",
                                    "path": res["metadatas"][0][i]["file_path"],
                                    "percentage": round(pct, 1)
                                })
            except Exception as e:
                print(f"Image search error: {e}", flush=True)

        elif self.mode == "Documents":
            try:
                emb = get_doc_query_embedding(self.query)
                if emb:
                    res = self.doc_col.query(
                        query_embeddings=[emb], n_results=20,
                        include=["metadatas", "distances"]
                    )
                    if res and res.get("metadatas") and res.get("distances"):
                        for i in range(len(res["metadatas"][0])):
                            sim = 1.0 - res["distances"][0][i]
                            pct = _normalize_score(sim, 0.30, 0.85)
                            if pct > 0:
                                matches.append({
                                    "type": "document",
                                    "path": res["metadatas"][0][i].get("file_path", ""),
                                    "file_type": res["metadatas"][0][i].get("file_type", "txt"),
                                    "chunk_text": res["metadatas"][0][i].get("chunk_text", ""),
                                    "percentage": round(pct, 1)
                                })
            except Exception as e:
                print(f"Doc search error: {e}", flush=True)

        matches.sort(key=lambda x: x["percentage"], reverse=True)
        self.results_ready.emit(matches, self.mode)


# ─── Neon Search Bar Widget ───────────────────────────────────────
class NeonSearchBar(QFrame):
    """Pill-shaped search bar with neon glow + pop-up on hover."""

    searchTriggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(580)
        self.setFixedHeight(54)
        self._hovered = False
        self._glow_strength = 0

        # Glow effect
        self._glow_effect = QGraphicsDropShadowEffect(self)
        self._glow_effect.setBlurRadius(0)
        self._glow_effect.setColor(QColor(GLOW_PURPLE))
        self._glow_effect.setOffset(0, 0)
        self.setGraphicsEffect(self._glow_effect)

        # Glow animation — slow glide
        self._glow_anim = QPropertyAnimation(self, b"glowStrength")
        self._glow_anim.setDuration(700)
        self._glow_anim.setEasingCurve(QEasingCurve.InOutCubic)

        self._update_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 0, 8, 0)
        layout.setSpacing(0)

        icon = QLabel("🔍")
        icon.setFont(QFont("Segoe UI", 13))
        icon.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(icon)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Search your memory...")
        self.input.setFont(QFont("Segoe UI", 13))
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {TEXT};
                padding: 0 10px;
            }}
        """)
        self.input.returnPressed.connect(self._on_search)
        layout.addWidget(self.input, 1)

        btn = QPushButton("Search")
        btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(90, 38)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(200, 190, 210, 190),
                    stop:1 rgba(170, 160, 180, 190));
                color: #1a1520;
                border-radius: 19px;
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(225, 215, 235, 220),
                    stop:1 rgba(195, 185, 205, 220));
            }}
            QPushButton:pressed {{ background: rgba(150, 140, 160, 200); }}
        """)
        btn.clicked.connect(self._on_search)
        layout.addWidget(btn)

    def _on_search(self):
        text = self.input.text().strip()
        if text:
            self.searchTriggered.emit(text)

    # ── Glow property ─────────────────────────────────────────────
    def _get_glow_strength(self):
        return self._glow_strength

    def _set_glow_strength(self, val):
        self._glow_strength = val
        self._glow_effect.setBlurRadius(val)
        # Subtle purple-white transition
        ratio = min(1.0, val / 35.0)
        r = int(138 + (200 - 138) * ratio)
        g = int(92 + (170 - 92) * ratio)
        b = int(245 + (255 - 245) * ratio)
        color = QColor(r, g, b, min(140, int(val * 2.0)))
        self._glow_effect.setColor(color)
        self._update_style()

    glowStrength = pyqtProperty(int, _get_glow_strength, _set_glow_strength)

    def _update_style(self):
        if self._hovered:
            border_color = "rgba(220, 210, 240, 180)"
            bg = "rgba(60, 48, 78, 130)"
        else:
            border_color = "rgba(130, 120, 145, 50)"
            bg = "rgba(45, 38, 58, 100)"

        self.setStyleSheet(f"""
            NeonSearchBar {{
                background: {bg};
                border-radius: 27px;
                border: 1.5px solid {border_color};
            }}
        """)

    def enterEvent(self, event):
        self._hovered = True
        self._glow_anim.stop()
        self._glow_anim.setStartValue(self._glow_strength)
        self._glow_anim.setEndValue(35)
        self._glow_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._glow_anim.stop()
        self._glow_anim.setStartValue(self._glow_strength)
        self._glow_anim.setEndValue(0)
        self._glow_anim.start()
        super().leaveEvent(event)


# ─── Hoverable Image Tile ────────────────────────────────────────
class ImageTile(QFrame):
    """Image thumbnail tile with pop-up + white border on hover.
    No QGraphicsDropShadowEffect — it breaks transparent rendering.
    Uses CSS border/background changes + margin-based pop-up only."""

    def __init__(self, match, parent=None):
        super().__init__(parent)
        self._hovered = False
        self._match = match
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()

        tile_layout = QVBoxLayout(self)
        tile_layout.setContentsMargins(6, 6, 6, 6)
        tile_layout.setSpacing(4)

        thumb_label = QLabel()
        thumb_label.setAlignment(Qt.AlignCenter)
        thumb_label.setFixedHeight(180)
        thumb_label.setStyleSheet("background: transparent; border: none;")

        try:
            pixmap = QPixmap(match["path"])
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    QSize(240, 180), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                thumb_label.setPixmap(scaled)
            else:
                thumb_label.setText("[Preview Error]")
                thumb_label.setStyleSheet(f"color: {TEXT2}; background: transparent; border: none;")
        except Exception:
            thumb_label.setText("[Error]")

        tile_layout.addWidget(thumb_label)

        bottom = QWidget()
        bottom.setStyleSheet("background: transparent;")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(4, 0, 4, 2)

        fname = os.path.basename(match["path"])
        short = fname[:24] + "..." if len(fname) > 27 else fname
        name_lbl = QLabel(short)
        name_lbl.setFont(QFont("Segoe UI", 7))
        name_lbl.setStyleSheet(f"color: {TEXT2}; background: transparent;")
        bl.addWidget(name_lbl)

        pct = match["percentage"]
        color = GREEN if pct >= 60 else (AMBER if pct >= 30 else TEXT2)
        score_lbl = QLabel(f"{pct:.0f}%")
        score_lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
        score_lbl.setStyleSheet(f"color: {color}; background: transparent;")
        score_lbl.setAlignment(Qt.AlignRight)
        bl.addWidget(score_lbl)

        tile_layout.addWidget(bottom)

    def _get_pop_offset(self):
        return self._pop_offset

    def _set_pop_offset(self, val):
        self._pop_offset = val
        self.setContentsMargins(0, 0, 0, val)

    popOffset = pyqtProperty(int, _get_pop_offset, _set_pop_offset)

    def _update_style(self):
        if self._hovered:
            self.setStyleSheet("""
                ImageTile {
                    background: rgba(55, 46, 68, 140);
                    border-radius: 14px;
                    border: 1.5px solid rgba(255, 255, 255, 130);
                }
            """)
        else:
            self.setStyleSheet("""
                ImageTile {
                    background: rgba(40, 34, 52, 100);
                    border-radius: 14px;
                    border: 1.5px solid rgba(100, 85, 130, 35);
                }
            """)

    def enterEvent(self, event):
        self._hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        try:
            os.startfile(self._match["path"])
        except Exception:
            pass


# ─── Hoverable Document Card ─────────────────────────────────────
class DocCard(QFrame):
    """Document result card with pop-up + white border on hover.
    No QGraphicsDropShadowEffect — uses CSS border + margin pop-up."""

    def __init__(self, match, parent=None):
        super().__init__(parent)
        self._hovered = False
        self._match = match
        self._update_style()

        cl = QHBoxLayout(self)
        cl.setContentsMargins(14, 12, 14, 12)

        ft = match.get("file_type", "txt")
        ic = {"pdf": RED, "word": "#6a8aff", "ppt": ORANGE, "txt": TEXT2}
        il = {"pdf": "PDF", "word": "DOC", "ppt": "PPT", "txt": "TXT"}

        icon_lbl = QLabel(il.get(ft, "?"))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFixedSize(42, 42)
        icon_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        icon_lbl.setStyleSheet(f"background: {ic.get(ft, TEXT2)}; color: white; border-radius: 8px;")
        cl.addWidget(icon_lbl)

        info = QVBoxLayout()
        info.setSpacing(3)

        fname = os.path.basename(match["path"])
        name_lbl = QLabel(fname)
        name_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        name_lbl.setStyleSheet(f"color: {TEXT}; background: transparent;")
        info.addWidget(name_lbl)

        snippet = match.get("chunk_text", "")[:220]
        if snippet:
            snip = QLabel(snippet + ("..." if len(match.get("chunk_text", "")) > 220 else ""))
            snip.setFont(QFont("Segoe UI", 8))
            snip.setStyleSheet(f"color: {TEXT2}; background: transparent;")
            snip.setWordWrap(True)
            info.addWidget(snip)

        open_btn = QPushButton("Open")
        open_btn.setFixedSize(60, 24)
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setFont(QFont("Segoe UI", 8))
        open_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PANEL_SOLID}; color: {TEXT};
                border-radius: 12px; border: 1px solid rgba(100,85,130,40);
            }}
            QPushButton:hover {{ background: {PANEL_HOVER}; }}
        """)
        open_btn.clicked.connect(lambda: os.startfile(match["path"]))
        info.addWidget(open_btn)
        cl.addLayout(info, 1)

        pct = match["percentage"]
        color = GREEN if pct >= 60 else (AMBER if pct >= 30 else TEXT2)
        score = QLabel(f"{pct:.1f}%")
        score.setFont(QFont("Segoe UI", 14, QFont.Bold))
        score.setStyleSheet(f"color: {color}; background: transparent;")
        score.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cl.addWidget(score)

    def _update_style(self):
        if self._hovered:
            self.setStyleSheet("""
                DocCard {
                    background: rgba(55, 46, 68, 130);
                    border-radius: 12px;
                    border: 1.5px solid rgba(255, 255, 255, 120);
                }
            """)
        else:
            self.setStyleSheet("""
                DocCard {
                    background: rgba(40, 34, 52, 100);
                    border-radius: 12px;
                    border: 1.5px solid rgba(100, 85, 130, 35);
                }
            """)

    def enterEvent(self, event):
        self._hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)


# ─── Main Application ────────────────────────────────────────────
class MemorySearchApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Memory Assistant")
        self.setMinimumSize(1000, 700)
        self.resize(1150, 780)

        # Load background image
        self._bg_pixmap = QPixmap(BG_IMAGE_PATH) if os.path.exists(BG_IMAGE_PATH) else None

        # DB
        self._db_client = chromadb.PersistentClient(path="./chroma_data")
        self.image_collection = self._db_client.get_or_create_collection(
            name="image_memory", metadata={"hnsw:space": "cosine"}
        )
        self.doc_collection = self._db_client.get_or_create_collection(
            name="document_memory", metadata={"hnsw:space": "cosine"}
        )

        self._search_mode = "Images"
        self._search_worker = None
        self._is_home = True
        self._anims = []  # keep refs to prevent GC

        self._build_ui()
        self._setup_tray()

        # File monitor
        self._monitor = FileMonitor(
            self.image_collection, self.doc_collection,
            on_file_indexed=lambda p: None
        )
        self._start_monitor()

    # ─── Build UI ─────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)

        self._main_layout = QVBoxLayout(central)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────
        top_bar = QWidget()
        top_bar.setFixedHeight(46)
        top_bar.setStyleSheet("background: transparent;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(14, 8, 14, 0)

        btn_style = f"""
            QPushButton, QToolButton {{
                color: {TEXT2};
                background: transparent;
                border: none;
                padding: 2px 8px;
            }}
            QPushButton:hover, QToolButton:hover {{ color: {GLOW_WHITE}; }}
        """

        # Hamburger menu (≡)
        self.menu_btn = QToolButton()
        self.menu_btn.setText("≡")
        self.menu_btn.setFont(QFont("Segoe UI", 18))
        self.menu_btn.setStyleSheet(btn_style)
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)

        mode_menu = QMenu(self)
        mode_menu.setStyleSheet(f"""
            QMenu {{
                background: #2a2435;
                border: 1px solid rgba(120,110,140,50);
                border-radius: 10px;
                padding: 6px;
            }}
            QMenu::item {{
                color: {TEXT};
                padding: 8px 28px;
                border-radius: 6px;
                font-size: 12px;
            }}
            QMenu::item:selected {{ background: rgba(100,85,130,70); }}
            QMenu::separator {{
                height: 1px;
                background: rgba(100,85,130,35);
                margin: 4px 10px;
            }}
        """)

        ag = QActionGroup(self)
        ag.setExclusive(True)
        img_act = QAction("🖼️  Images", self, checkable=True, checked=True)
        img_act.triggered.connect(lambda: self._set_mode("Images"))
        ag.addAction(img_act)
        mode_menu.addAction(img_act)
        doc_act = QAction("📄  Documents", self, checkable=True)
        doc_act.triggered.connect(lambda: self._set_mode("Documents"))
        ag.addAction(doc_act)
        mode_menu.addAction(doc_act)

        mode_menu.addSeparator()
        for label, slot in [
            ("📁  Scan Files", self._on_scan_files),
            ("📄  Index Documents", self._on_index_docs),
            ("🖼️  Index Images", self._on_index_images),
            ("🔄  Sync New Files", self._on_force_sync),
        ]:
            a = QAction(label, self)
            a.triggered.connect(slot)
            mode_menu.addAction(a)

        self.menu_btn.setMenu(mode_menu)
        top_layout.addWidget(self.menu_btn)

        # Home button (⌂) — always visible
        self.home_btn = QPushButton("⌂")
        self.home_btn.setFont(QFont("Segoe UI", 16))
        self.home_btn.setCursor(Qt.PointingHandCursor)
        self.home_btn.setStyleSheet(btn_style)
        self.home_btn.clicked.connect(self._go_home)
        top_layout.addWidget(self.home_btn)

        top_layout.addStretch()

        # Monitor dot + stats
        self.monitor_dot = QLabel("●")
        self.monitor_dot.setFont(QFont("Segoe UI", 7))
        self.monitor_dot.setStyleSheet(f"color: {GREEN}; background: transparent;")
        top_layout.addWidget(self.monitor_dot)

        self.stats_label = QLabel("")
        self.stats_label.setFont(QFont("Segoe UI", 8))
        self.stats_label.setStyleSheet(f"color: {TEXT2}; background: transparent;")
        top_layout.addWidget(self.stats_label)
        self._update_stats()

        self.mode_label = QLabel("Images")
        self.mode_label.setFont(QFont("Segoe UI", 8))
        self.mode_label.setStyleSheet(f"color: {ACCENT}; background: transparent; padding-left: 8px;")
        top_layout.addWidget(self.mode_label)

        # Info button (ℹ) — top-right
        self.info_btn = QPushButton("ℹ")
        self.info_btn.setFont(QFont("Segoe UI", 14))
        self.info_btn.setCursor(Qt.PointingHandCursor)
        self.info_btn.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT2};
                background: transparent;
                border: none;
                padding: 2px 10px;
            }}
            QPushButton:hover {{ color: {GLOW_WHITE}; }}
        """)
        self.info_btn.clicked.connect(self._show_info)
        top_layout.addWidget(self.info_btn)

        self._main_layout.addWidget(top_bar)

        # ── Search bar container (centered on home) ───────────────
        self._search_spacer_top = QWidget()
        self._search_spacer_top.setStyleSheet("background: transparent;")
        self._main_layout.addWidget(self._search_spacer_top, 1)

        # Title (home screen)
        self.title_label = QLabel("Memory Assistant")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Segoe UI", 28, QFont.Bold))
        self.title_label.setStyleSheet(f"color: {GLOW_WHITE}; background: transparent;")
        self._main_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Search your images and documents with natural language")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setFont(QFont("Segoe UI", 10))
        self.subtitle_label.setStyleSheet(f"color: {TEXT3}; background: transparent; margin-bottom: 24px;")
        self._main_layout.addWidget(self.subtitle_label)

        # Search bar
        search_container = QWidget()
        search_container.setStyleSheet("background: transparent;")
        search_h = QHBoxLayout(search_container)
        search_h.setContentsMargins(0, 0, 0, 0)
        search_h.addStretch(1)

        self.search_bar = NeonSearchBar()
        self.search_bar.searchTriggered.connect(self._on_search)
        search_h.addWidget(self.search_bar)

        search_h.addStretch(1)
        self._main_layout.addWidget(search_container)

        # Status
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {TEXT2}; background: transparent; padding: 6px;")
        self._main_layout.addWidget(self.status_label)

        # Bottom spacer
        self._search_spacer_bottom = QWidget()
        self._search_spacer_bottom.setStyleSheet("background: transparent;")
        self._main_layout.addWidget(self._search_spacer_bottom, 1)

        # ── Results area (hidden initially) ───────────────────────
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 6px;
            }
            QScrollBar::handle:vertical {
                background: rgba(120, 100, 150, 70); border-radius: 3px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.results_widget = QWidget()
        self.results_widget.setStyleSheet("background: transparent;")
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(30, 10, 30, 30)
        self.results_layout.setAlignment(Qt.AlignTop)
        self.results_layout.setSpacing(10)

        self.scroll_area.setWidget(self.results_widget)
        self.scroll_area.setVisible(False)

        self._results_opacity = QGraphicsOpacityEffect(self.scroll_area)
        self._results_opacity.setOpacity(0.0)
        self.scroll_area.setGraphicsEffect(self._results_opacity)

        self._main_layout.addWidget(self.scroll_area, 3)

    # ─── State transitions ────────────────────────────────────────
    def _switch_to_results_view(self):
        """Animate: search bar goes up slowly, results slide in."""
        self._is_home = False
        self.title_label.setVisible(False)
        self.subtitle_label.setVisible(False)

        # Slow collapse of top spacer
        self._search_spacer_top.setFixedHeight(10)
        self._search_spacer_bottom.setFixedHeight(0)
        self._search_spacer_bottom.setVisible(False)

        # Show scroll area with slow fade-in
        self.scroll_area.setVisible(True)
        fade_in = QPropertyAnimation(self._results_opacity, b"opacity")
        fade_in.setDuration(800)  # Slower fade
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        fade_in.start()
        self._anims.append(fade_in)

    def _go_home(self):
        """Return to centered search bar home screen."""
        self._is_home = True
        self._clear_results()
        self._anims.clear()
        self.title_label.setVisible(True)
        self.subtitle_label.setVisible(True)
        self.status_label.setText("")

        # Restore spacers
        self._search_spacer_top.setMinimumHeight(0)
        self._search_spacer_top.setMaximumHeight(16777215)
        self._search_spacer_bottom.setVisible(True)
        self._search_spacer_bottom.setMinimumHeight(0)
        self._search_spacer_bottom.setMaximumHeight(16777215)

        self.scroll_area.setVisible(False)
        self._results_opacity.setOpacity(0.0)

        self.search_bar.input.clear()
        self.search_bar.input.setFocus()

    def _set_mode(self, mode):
        self._search_mode = mode
        self.mode_label.setText(mode)

    def _update_stats(self):
        try:
            ic = self.image_collection.count()
            dc = self.doc_collection.count()
            self.stats_label.setText(f"{ic} images · {dc} doc chunks")
        except:
            pass

    def _set_status(self, text, color=TEXT2):
        self.status_label.setStyleSheet(f"color: {color}; background: transparent; padding: 6px;")
        self.status_label.setText(text)

    def _clear_results(self):
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _show_info(self):
        """Show info dialog about how to use the app."""
        msg = QMessageBox(self)
        msg.setWindowTitle("How to Use")
        msg.setTextFormat(Qt.RichText)
        msg.setText(INFO_TEXT)
        msg.setStyleSheet(f"""
            QMessageBox {{
                background: #1e1828;
            }}
            QMessageBox QLabel {{
                color: {TEXT};
                min-width: 450px;
            }}
            QPushButton {{
                background: {PANEL_SOLID};
                color: {TEXT};
                padding: 6px 20px;
                border-radius: 8px;
                border: 1px solid rgba(100,85,130,50);
            }}
            QPushButton:hover {{ background: {PANEL_HOVER}; }}
        """)
        msg.exec_()

    # ─── Monitor ──────────────────────────────────────────────────
    def _start_monitor(self):
        try:
            self._monitor.start()
        except Exception as e:
            print(f"Monitor error: {e}", flush=True)
            self.monitor_dot.setStyleSheet(f"color: {RED}; background: transparent;")

    # ─── System Tray ──────────────────────────────────────────────
    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray_icon.setToolTip("Memory Assistant")

        tray_menu = QMenu()
        tray_menu.setStyleSheet(f"""
            QMenu {{ background: #2a2435; border: 1px solid rgba(100,85,130,40); padding: 4px; }}
            QMenu::item {{ color: {TEXT}; padding: 6px 18px; }}
            QMenu::item:selected {{ background: rgba(100,85,130,60); }}
        """)
        tray_menu.addAction("Open Search").triggered.connect(self._restore_window)
        tray_menu.addAction("Sync New Files").triggered.connect(self._on_force_sync)
        tray_menu.addSeparator()
        tray_menu.addAction("Quit").triggered.connect(self._quit_app)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._restore_window()

    def _restore_window(self):
        self.showNormal()
        self.activateWindow()
        self.search_bar.input.setFocus()

    def _quit_app(self):
        self._monitor.stop()
        self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    # ─── Search ───────────────────────────────────────────────────
    def _on_search(self, query):
        if not query:
            return

        self._set_status("Searching...", ACCENT)
        self._clear_results()

        if self._is_home:
            self._switch_to_results_view()

        # Refresh collections
        self.image_collection = self._db_client.get_or_create_collection(
            name="image_memory", metadata={"hnsw:space": "cosine"}
        )
        self.doc_collection = self._db_client.get_or_create_collection(
            name="document_memory", metadata={"hnsw:space": "cosine"}
        )

        self._search_worker = SearchWorker(
            query, self._search_mode, self.image_collection, self.doc_collection
        )
        self._search_worker.results_ready.connect(self._display_results)
        self._search_worker.start()

    def _display_results(self, matches, mode):
        self._clear_results()

        if not matches:
            self._set_status("No matches found.", AMBER)
            lbl = QLabel("No matching results found.")
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setStyleSheet(f"color: {TEXT2}; background: transparent; padding: 40px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.results_layout.addWidget(lbl)
            return

        label = "images" if mode == "Images" else "documents"
        self._set_status(f"Found {len(matches)} {label}", GREEN)

        if mode == "Images":
            self._render_image_gallery(matches)
        else:
            for m in matches:
                card = DocCard(m)
                self.results_layout.addWidget(card)

    def _render_image_gallery(self, matches):
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_widget)
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        cols = 4
        for idx, match in enumerate(matches):
            row = idx // cols
            col = idx % cols
            tile = ImageTile(match)
            grid.addWidget(tile, row, col)

        self.results_layout.addWidget(grid_widget)

    # ─── Actions ──────────────────────────────────────────────────
    def _on_scan_files(self):
        self._set_status("Scanning file system...", ACCENT)
        if self._is_home:
            self._switch_to_results_view()
        self._clear_results()
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        try:
            result = scan_system_files()
            self._last_scan = result
            total = sum(len(v) for v in result.values())
            QTimer.singleShot(0, lambda: self._set_status(f"Scan complete! {total} files found.", GREEN))
            QTimer.singleShot(0, lambda: self._show_scan_results(result))
        except Exception as e:
            QTimer.singleShot(0, lambda: self._set_status(f"Scan error: {e}", RED))

    def _show_scan_results(self, result):
        self._clear_results()
        for cat, files in result.items():
            lbl = QLabel(f"  {cat.upper()}: {len(files)} files")
            lbl.setFont(QFont("Segoe UI", 10))
            lbl.setStyleSheet(f"color: {TEXT}; background: transparent; padding: 4px;")
            self.results_layout.addWidget(lbl)

    def _on_index_docs(self):
        if not hasattr(self, "_last_scan"):
            self._set_status("Run 'Scan Files' first!", AMBER)
            return
        self._set_status("Indexing documents...", ACCENT)
        threading.Thread(target=self._index_docs_thread, daemon=True).start()

    def _index_docs_thread(self):
        try:
            index_documents(self._last_scan, self.doc_collection)
            QTimer.singleShot(0, self._update_stats)
            QTimer.singleShot(0, lambda: self._set_status("Document indexing complete!", GREEN))
        except Exception as e:
            QTimer.singleShot(0, lambda: self._set_status(f"Error: {e}", RED))

    def _on_index_images(self):
        if not hasattr(self, "_last_scan"):
            self._set_status("Run 'Scan Files' first!", AMBER)
            return
        paths = self._last_scan.get("images", [])
        if not paths:
            self._set_status("No images found.", AMBER)
            return
        self._set_status(f"Indexing {len(paths)} images...", ACCENT)
        threading.Thread(target=self._index_images_thread, args=(paths,), daemon=True).start()

    def _index_images_thread(self, paths):
        count = 0
        for p in paths:
            try:
                emb = get_image_embedding(p)
                if emb:
                    self.image_collection.upsert(
                        ids=[str(uuid.uuid4())], embeddings=[emb],
                        metadatas=[{"file_path": p}]
                    )
                    count += 1
            except:
                pass
        QTimer.singleShot(0, self._update_stats)
        QTimer.singleShot(0, lambda: self._set_status(f"Done! {count} images indexed.", GREEN))

    def _on_force_sync(self):
        self._set_status("Syncing new files...", ACCENT)
        threading.Thread(target=self._force_sync_thread, daemon=True).start()

    def _force_sync_thread(self):
        try:
            result = scan_system_files()
            self._last_scan = result
            index_documents(result, self.doc_collection)
            QTimer.singleShot(0, self._update_stats)
            QTimer.singleShot(0, lambda: self._set_status("Sync complete!", GREEN))
        except Exception as e:
            QTimer.singleShot(0, lambda: self._set_status(f"Sync error: {e}", RED))

    # ─── Background image paint ───────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._bg_pixmap and not self._bg_pixmap.isNull():
            # Scale to fill while keeping aspect ratio
            scaled = self._bg_pixmap.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            # Center crop
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(0, 0, scaled, x, y, self.width(), self.height())

            # Semi-transparent dark blue overlay
            painter.fillRect(self.rect(), QColor(6, 10, 28, 110))
        else:
            # Fallback dark blue gradient
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            gradient.setColorAt(0.0, QColor(8, 14, 32))
            gradient.setColorAt(0.5, QColor(12, 18, 38))
            gradient.setColorAt(1.0, QColor(10, 16, 35))
            painter.fillRect(self.rect(), QBrush(gradient))

        painter.end()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    window = MemorySearchApp()
    window.show()

    sys.exit(app.exec_())
