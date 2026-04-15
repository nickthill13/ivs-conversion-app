"""
main.py — IVS Conversion App
Built by Nicholas Thill
"""

import sys
import threading
import webbrowser
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QPalette, QFont, QIcon, QPixmap, QPainter
import os
import subprocess

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QTreeWidget,
    QTreeWidgetItem, QTextEdit, QStatusBar, QFrame, QButtonGroup,
    QSizePolicy, QProgressBar, QCheckBox, QMessageBox,
)

from converter import convert_file

GITHUB_URL = "https://github.com/nickthill13/ivs-conversion-app"
ACCENT     = "#2563EB"
SUCCESS    = "#16A34A"
ERROR      = "#DC2626"
WARN       = "#D97706"


# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------
def dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor("#0F172A"))
    p.setColor(QPalette.ColorRole.WindowText,      QColor("#F1F5F9"))
    p.setColor(QPalette.ColorRole.Base,            QColor("#1E293B"))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor("#263347"))
    p.setColor(QPalette.ColorRole.Text,            QColor("#F1F5F9"))
    p.setColor(QPalette.ColorRole.Button,          QColor("#1E293B"))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor("#F1F5F9"))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#475569"))
    p.setColor(QPalette.ColorRole.Mid,             QColor("#334155"))
    p.setColor(QPalette.ColorRole.Dark,            QColor("#0F172A"))
    return p


def light_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor("#F1F5F9"))
    p.setColor(QPalette.ColorRole.WindowText,      QColor("#0F172A"))
    p.setColor(QPalette.ColorRole.Base,            QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor("#F0F4F8"))
    p.setColor(QPalette.ColorRole.Text,            QColor("#0F172A"))
    p.setColor(QPalette.ColorRole.Button,          QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor("#0F172A"))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#94A3B8"))
    p.setColor(QPalette.ColorRole.Mid,             QColor("#CBD5E1"))
    p.setColor(QPalette.ColorRole.Dark,            QColor("#E2E8F0"))
    return p


# ---------------------------------------------------------------------------
# Conversion worker (runs on a background thread, signals back to UI)
# ---------------------------------------------------------------------------
class Worker(QObject):
    log     = pyqtSignal(str)
    status  = pyqtSignal(int, str)   # (row_index, status_text)
    done    = pyqtSignal(int, int)   # (ok_count, err_count)

    def __init__(self, files: list[Path], output_dir: str, fmt: str, markups: bool):
        super().__init__()
        self.files      = files
        self.output_dir = output_dir
        self.fmt        = fmt
        self.markups    = markups
        self._abort     = False

    def run(self):
        ok = err = 0
        self.log.emit(f"▶  {len(self.files)} file(s)  ·  {self.fmt}  ·  markups {'on' if self.markups else 'off'}\n")

        for i, path in enumerate(self.files):
            if self._abort:
                break
            self.status.emit(i, "⏳")
            try:
                convert_file(str(path), self.output_dir, self.fmt,
                             self.markups, lambda m: self.log.emit(m))
                self.status.emit(i, "✓")
                ok += 1
            except Exception as e:
                self.log.emit(f"  ✕  {path.name}: {e}")
                self.status.emit(i, "✕")
                err += 1

        self.log.emit(f"\n■  Done — {ok} exported, {err} failed")
        self.done.emit(ok, err)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._files: list[Path] = []
        self._dark = True
        self._busy = False
        self._worker: Worker | None = None
        self._thread: QThread | None = None

        self.setWindowTitle("IVS Conversion App")
        self.resize(1060, 700)
        self.setMinimumSize(860, 560)

        self._apply_theme()
        self._build()

    # -----------------------------------------------------------------------
    # Theme
    # -----------------------------------------------------------------------
    def _apply_theme(self):
        QApplication.instance().setPalette(
            dark_palette() if self._dark else light_palette()
        )
        border = "#334155" if self._dark else "#CBD5E1"
        surface = "#1E293B" if self._dark else "#FFFFFF"
        muted_text = "#94A3B8" if self._dark else "#64748B"
        tree_alt = "#263347" if self._dark else "#F0F4F8"
        log_bg = "#1E293B" if self._dark else "#FFFFFF"

        self.setStyleSheet(f"""
            QMainWindow {{
                background: {"#0F172A" if self._dark else "#F1F5F9"};
            }}
            QTreeWidget {{
                border: 1px solid {border};
                border-radius: 8px;
                outline: 0;
                font-size: 12px;
            }}
            QTreeWidget::item {{
                height: 36px;
                padding-left: 6px;
                border-bottom: 1px solid {border};
            }}
            QTreeWidget::item:selected {{
                background: {ACCENT}22;
                color: {"#F1F5F9" if self._dark else "#0F172A"};
            }}
            QTreeWidget::item:hover {{
                background: {ACCENT}11;
            }}
            QHeaderView::section {{
                background: {surface};
                color: {muted_text};
                font-size: 10px;
                font-weight: bold;
                padding: 6px;
                border: none;
                border-bottom: 1px solid {border};
                border-right: 1px solid {border};
            }}
            QTextEdit {{
                background: {log_bg};
                border: 1px solid {border};
                border-radius: 8px;
                font-family: monospace;
                font-size: 11px;
                color: {"#94A3B8" if self._dark else "#475569"};
                padding: 6px;
            }}
            QLineEdit {{
                background: {"#263347" if self._dark else "#F0F4F8"};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                color: {"#F1F5F9" if self._dark else "#0F172A"};
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT};
            }}
            QPushButton {{
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }}
            QCheckBox {{
                font-size: 12px;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {border};
                border-radius: 4px;
                background: {"#263347" if self._dark else "#F0F4F8"};
            }}
            QCheckBox::indicator:checked {{
                background: {ACCENT};
                border: 1px solid {ACCENT};
            }}
            QProgressBar {{
                border: none;
                background: {border};
                border-radius: 2px;
                height: 4px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {ACCENT};
                border-radius: 2px;
            }}
            QStatusBar {{
                background: {surface};
                border-top: 1px solid {border};
                font-size: 10px;
                color: {muted_text};
                padding: 0 24px;
            }}
            QStatusBar QLabel {{
                padding-right: 24px;
            }}
            QFrame#navbar {{
                background: {surface};
                border-bottom: 1px solid {border};
            }}
            QFrame#controlstrip {{
                background: {surface};
                border-bottom: 1px solid {border};
            }}
        """)

    def _toggle_theme(self):
        self._dark = not self._dark
        self._apply_theme()
        self._mode_btn.setText("☀  Light" if self._dark else "🌙  Dark")

    # -----------------------------------------------------------------------
    # Build UI
    # -----------------------------------------------------------------------
    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._make_navbar())
        layout.addWidget(self._make_controls())
        layout.addWidget(self._make_filelist(), stretch=1)
        layout.addWidget(self._make_log())

        bar = QStatusBar()
        bar.setSizeGripEnabled(False)
        self.setStatusBar(bar)
        bar.addPermanentWidget(QLabel("Nicholas Thill  ·  2025  ·  Open Source"))

    # ── Navbar ──────────────────────────────────────────────────────────────
    def _make_navbar(self) -> QFrame:
        nav = QFrame()
        nav.setObjectName("navbar")
        nav.setFixedHeight(52)
        row = QHBoxLayout(nav)
        row.setContentsMargins(20, 0, 20, 0)

        # Logo
        icon_path = Path(__file__).parent / "icon.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(
                28, 28, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            ico_lbl = QLabel()
            ico_lbl.setPixmap(pix)
            row.addWidget(ico_lbl)
            row.addSpacing(10)

        title = QLabel("IVS Conversion App")
        title.setFont(QFont(title.font().family(), 14, QFont.Weight.Bold))
        row.addWidget(title)

        dot = QLabel("·")
        dot.setStyleSheet("color: #64748B; font-size: 14px;")
        row.addWidget(dot)
        row.addSpacing(2)

        by = QLabel("by Nicholas Thill")
        by.setStyleSheet("color: #64748B; font-size: 12px;")
        row.addWidget(by)

        row.addStretch()

        self._mode_btn = self._ghost_btn("☀  Light")
        self._mode_btn.clicked.connect(self._toggle_theme)
        row.addWidget(self._mode_btn)
        row.addSpacing(8)

        gh = self._ghost_btn("⎇  GitHub")
        gh.clicked.connect(lambda: webbrowser.open(GITHUB_URL))
        row.addWidget(gh)

        return nav

    # ── Control strip ────────────────────────────────────────────────────────
    def _make_controls(self) -> QFrame:
        strip = QFrame()
        strip.setObjectName("controlstrip")

        outer = QVBoxLayout(strip)
        outer.setContentsMargins(20, 10, 20, 10)
        outer.setSpacing(8)

        # Row 1: folders
        folders = QHBoxLayout()
        folders.setSpacing(10)

        self._in_edit = QLineEdit()
        self._in_edit.setPlaceholderText("Input folder — containing .IVS files")
        in_browse = self._browse_btn()
        in_browse.clicked.connect(self._browse_input)

        arrow = QLabel("→")
        arrow.setStyleSheet("color: #64748B; font-size: 15px;")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(28)

        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("Output folder — where exports will be saved")
        out_browse = self._browse_btn()
        out_browse.clicked.connect(self._browse_output)

        folders.addWidget(self._in_edit, stretch=1)
        folders.addWidget(in_browse)
        folders.addWidget(arrow)
        folders.addWidget(self._out_edit, stretch=1)
        folders.addWidget(out_browse)
        outer.addLayout(folders)

        # Row 2: format + markup + progress + convert
        row2 = QHBoxLayout()
        row2.setSpacing(0)

        self._fmt_group = QButtonGroup()
        self._fmt_btns: dict[str, QPushButton] = {}
        for i, fmt in enumerate(["PDF", "TIFF", "PNG", "JPEG"]):
            b = QPushButton(fmt)
            b.setCheckable(True)
            b.setFixedHeight(32)
            b.setFixedWidth(60)
            b.setStyleSheet(self._pill_style(i == 0, i, 3))
            b.clicked.connect(lambda _, f=fmt: self._select_fmt(f))
            self._fmt_group.addButton(b)
            self._fmt_btns[fmt] = b
            row2.addWidget(b)

        self._fmt_btns["PDF"].setChecked(True)
        self._selected_fmt = "PDF"

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #334155; margin: 4px 16px;")
        row2.addWidget(sep)

        self._markup_cb = QCheckBox("Apply IVA Markups")
        self._markup_cb.setChecked(True)
        row2.addWidget(self._markup_cb)

        row2.addStretch()

        self._progress = QProgressBar()
        self._progress.setFixedWidth(120)
        self._progress.setFixedHeight(4)
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        row2.addWidget(self._progress)
        row2.addSpacing(12)

        self._open_btn = QPushButton("Open Output  ↗")
        self._open_btn.setFixedHeight(36)
        self._open_btn.setFixedWidth(136)
        self._open_btn.setVisible(False)
        self._open_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #334155;
                border-radius: 8px;
                color: #94A3B8;
                font-size: 12px;
            }
            QPushButton:hover { background: #263347; color: #F1F5F9; }
        """)
        self._open_btn.clicked.connect(self._open_output_folder)
        row2.addWidget(self._open_btn)
        row2.addSpacing(8)

        self._convert_btn = QPushButton("Convert All  →")
        self._convert_btn.setFixedHeight(36)
        self._convert_btn.setFixedWidth(148)
        self._convert_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{ background: #1D4ED8; }}
            QPushButton:disabled {{ background: #475569; color: #94A3B8; }}
        """)
        self._convert_btn.clicked.connect(self._start_conversion)
        row2.addWidget(self._convert_btn)

        outer.addLayout(row2)
        return strip

    # ── File list ────────────────────────────────────────────────────────────
    def _make_filelist(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 0)
        layout.setSpacing(0)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["#", "Filename", "Markup", "Status"])
        self._tree.setColumnWidth(0, 44)
        self._tree.setColumnWidth(1, 999)   # will stretch
        self._tree.setColumnWidth(2, 80)
        self._tree.setColumnWidth(3, 72)
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(1, self._tree.header().ResizeMode.Stretch)
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSortingEnabled(False)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self._tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout.addWidget(self._tree)
        return container

    # ── Log ─────────────────────────────────────────────────────────────────
    def _make_log(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 8, 16, 10)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(96)
        layout.addWidget(self._log)
        return container

    # -----------------------------------------------------------------------
    # Widget helpers
    # -----------------------------------------------------------------------
    def _ghost_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setFixedHeight(30)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #94A3B8;
                font-size: 11px;
                padding: 0 12px;
            }
            QPushButton:hover { background: #1E293B; color: #F1F5F9; }
        """)
        return b

    def _browse_btn(self) -> QPushButton:
        b = QPushButton("Browse")
        b.setFixedHeight(34)
        b.setFixedWidth(72)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #94A3B8;
                font-size: 11px;
            }
            QPushButton:hover { background: #263347; color: #F1F5F9; }
        """)
        return b

    def _pill_style(self, active: bool, idx: int, last: int) -> str:
        tl = "8px" if idx == 0 else "0"
        bl = "8px" if idx == 0 else "0"
        tr = "8px" if idx == last else "0"
        br = "8px" if idx == last else "0"
        if active:
            return f"""
                QPushButton {{
                    background: {ACCENT}; color: white; font-size: 12px;
                    border: 1px solid {ACCENT};
                    border-radius: 0;
                    border-top-left-radius: {tl};
                    border-bottom-left-radius: {bl};
                    border-top-right-radius: {tr};
                    border-bottom-right-radius: {br};
                }}"""
        return f"""
            QPushButton {{
                background: transparent; color: #64748B; font-size: 12px;
                border: 1px solid #334155;
                border-radius: 0;
                border-top-left-radius: {tl};
                border-bottom-left-radius: {bl};
                border-top-right-radius: {tr};
                border-bottom-right-radius: {br};
            }}
            QPushButton:hover {{ background: #263347; color: #F1F5F9; }}"""

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------
    def _browse_input(self):
        d = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if d:
            self._in_edit.setText(d)
            self._load_files(d)

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if d:
            self._out_edit.setText(d)

    def _select_fmt(self, fmt: str):
        self._selected_fmt = fmt
        for i, (f, b) in enumerate(self._fmt_btns.items()):
            b.setStyleSheet(self._pill_style(f == fmt, i, 3))

    def _load_files(self, folder: str):
        ivs = sorted(Path(folder).glob("*.ivs")) + sorted(Path(folder).glob("*.IVS"))
        seen, unique = set(), []
        for f in ivs:
            if f.name.lower() not in seen:
                seen.add(f.name.lower()); unique.append(f)

        self._tree.clear()
        self._files = unique

        if not unique:
            return

        iva_n = sum(1 for f in unique if f.with_suffix(".iva").exists())

        for i, f in enumerate(unique):
            has_iva = f.with_suffix(".iva").exists()
            item = QTreeWidgetItem([
                f"{i+1:02d}",
                f.stem,
                "IVA ✓" if has_iva else "—",
                "—",
            ])
            item.setTextAlignment(0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
            item.setTextAlignment(3, Qt.AlignmentFlag.AlignCenter)
            item.setForeground(0, QColor("#475569"))
            item.setForeground(2, QColor(SUCCESS) if has_iva else QColor("#475569"))
            self._tree.addTopLevelItem(item)

    def _write_log(self, msg: str):
        self._log.append(msg)

    def _on_status(self, row: int, text: str):
        item = self._tree.topLevelItem(row)
        if item:
            color = SUCCESS if text == "✓" else ERROR if text == "✕" else WARN
            item.setText(3, text)
            item.setForeground(3, QColor(color))

    def _on_done(self, ok: int, err: int):
        self._convert_btn.setEnabled(True)
        self._convert_btn.setText("Convert All  →")
        self._progress.setVisible(False)
        self._open_btn.setVisible(True)
        self._busy = False

    def _open_output_folder(self):
        out = self._out_edit.text().strip()
        if not out:
            return
        if sys.platform == "darwin":
            subprocess.run(["open", out])
        elif sys.platform == "win32":
            os.startfile(out)
        else:
            subprocess.run(["xdg-open", out])

    def _start_conversion(self):
        if self._busy:
            msg = QMessageBox(self)
            msg.setWindowTitle("Already Converting")
            msg.setText("A conversion is already in progress.\nPlease wait for it to finish.")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return

        inp = self._in_edit.text().strip()
        out = self._out_edit.text().strip()

        if not inp:
            self._write_log("⚠  Select an input folder.")
            return
        if not out:
            self._write_log("⚠  Select an output folder.")
            return
        if not self._files:
            self._write_log("⚠  No files loaded.")
            return

        self._open_btn.setVisible(False)

        # Reset status column
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            item.setText(3, "—")
            item.setForeground(3, QColor("#475569"))

        self._busy = True
        self._convert_btn.setEnabled(False)
        self._convert_btn.setText("Converting…")
        self._progress.setVisible(True)

        self._worker = Worker(
            self._files, out,
            self._selected_fmt,
            self._markup_cb.isChecked(),
        )
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self._write_log)
        self._worker.status.connect(self._on_status)
        self._worker.done.connect(self._on_done)
        self._worker.done.connect(self._thread.quit)
        self._thread.start()


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    icon_path = Path(__file__).parent / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
