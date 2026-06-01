import os
import shutil
import threading
import json
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# ─────────────────────────────────────────────
#  DEFAULT CONFIGURATION
# ─────────────────────────────────────────────
DEFAULT_FILE_TYPES = {
    "Videos":      [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".mpg", ".m4v", ".3gp", ".ts", ".vob"],
    "Music":       [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".alac", ".aiff", ".opus"],
    "Pictures":    [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".svg", ".webp", ".heic", ".raw", ".cr2", ".nef", ".arw"],
    "Documents":   [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xlsx", ".xls", ".csv", ".ppt", ".pptx", ".epub", ".md", ".json", ".xml", ".yaml", ".yml"],
    "Compressed":  [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".cab"],
    "Code":        [".py", ".js", ".html", ".css", ".php", ".c", ".cpp", ".cs", ".java", ".kt", ".swift", ".rb", ".go", ".ts", ".sql", ".sh", ".bat", ".ps1"],
    "3D_Models":   [".fbx", ".obj", ".blend", ".dae", ".stl", ".gltf", ".glb"],
    "Executables": [".exe", ".msi", ".apk", ".dmg", ".bin", ".dll", ".sys"],
}

DEFAULT_IGNORE = [".ini", ".sys", ".db", ".tmp", ".log", ".DS_Store"]
CONFIG_FILE = str(Path.home() / ".folder_organizer_config.json")


# ─────────────────────────────────────────────
#  CONFIG PERSISTENCE
# ─────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "folder_path": str(Path.home() / "Downloads"),
        "file_types": DEFAULT_FILE_TYPES.copy(),
        "ignore_extensions": DEFAULT_IGNORE.copy(),
        "auto_detect_new": True,
        "skip_scripts": True,
        "watch_on_start": False,
        "move_to_others": True,
    }


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ─────────────────────────────────────────────
#  ORGANIZER LOGIC
# ─────────────────────────────────────────────
class Organizer:
    def __init__(self, cfg, log_callback):
        self.cfg = cfg
        self.log = log_callback
        self.stats = {"moved": 0, "ignored": 0, "auto": 0, "others": 0, "errors": 0}

    def move_file(self, file_path):
        if not os.path.isfile(file_path):
            return
        folder_path = self.cfg["folder_path"]
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1].lower()

        if file_ext in self.cfg["ignore_extensions"]:
            self.log(f"⏭  Ignored: {file_name}", "muted")
            self.stats["ignored"] += 1
            return

        for folder, extensions in self.cfg["file_types"].items():
            if file_ext in extensions:
                dest_dir = os.path.join(folder_path, folder)
                os.makedirs(dest_dir, exist_ok=True)
                dest = os.path.join(dest_dir, file_name)
                try:
                    shutil.move(file_path, dest)
                    self.log(f"✔  {file_name}  →  {folder}", "success")
                    self.stats["moved"] += 1
                except Exception as e:
                    self.log(f"✖  Error moving {file_name}: {e}", "error")
                    self.stats["errors"] += 1
                return

        if file_ext and self.cfg.get("auto_detect_new", True):
            new_folder = file_ext.replace(".", "").upper()
            new_folder_path = os.path.join(folder_path, new_folder)
            os.makedirs(new_folder_path, exist_ok=True)
            try:
                shutil.move(file_path, os.path.join(new_folder_path, file_name))
                self.log(f"★  Auto-detected: {file_name}  →  {new_folder}", "auto")
                self.stats["auto"] += 1
            except Exception as e:
                self.log(f"✖  Error: {e}", "error")
                self.stats["errors"] += 1
        elif self.cfg.get("move_to_others", True):
            others_dir = os.path.join(folder_path, "Others")
            os.makedirs(others_dir, exist_ok=True)
            try:
                shutil.move(file_path, os.path.join(others_dir, file_name))
                self.log(f"?  {file_name}  →  Others", "warn")
                self.stats["others"] += 1
            except Exception as e:
                self.log(f"✖  Error: {e}", "error")
                self.stats["errors"] += 1
        else:
            self.log(f"–  Skipped (no category): {file_name}", "muted")

    def organize_existing(self):
        folder_path = self.cfg["folder_path"]
        self.log(f"📂  Scanning: {folder_path}", "info")
        count = 0
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isdir(item_path):
                continue
            if self.cfg.get("skip_scripts", True) and item.endswith(".py"):
                self.log(f"⏭  Skipped script: {item}", "muted")
                continue
            self.move_file(item_path)
            count += 1
        self.log(f"✅  Done — {count} file(s) processed.", "info")


class WatchHandler(FileSystemEventHandler):
    def __init__(self, organizer):
        self.organizer = organizer

    def on_created(self, event):
        if not event.is_directory:
            time.sleep(0.5)
            self.organizer.move_file(event.src_path)


# ─────────────────────────────────────────────
#  MAIN GUI
# ─────────────────────────────────────────────
class FolderOrganizerApp(tk.Tk):
    DARK_BG   = "#1a1a2e"
    PANEL     = "#16213e"
    CARD      = "#0f3460"
    ACCENT    = "#e94560"
    ACCENT2   = "#53d8fb"
    TEXT      = "#e0e0e0"
    MUTED     = "#8888aa"
    SUCCESS   = "#4ade80"
    WARN      = "#fbbf24"
    ERROR     = "#f87171"
    AUTO      = "#a78bfa"

    FONT_TITLE  = ("Segoe UI", 20, "bold")
    FONT_H2     = ("Segoe UI", 13, "bold")
    FONT_BODY   = ("Segoe UI", 10)
    FONT_MONO   = ("Consolas", 9)
    FONT_BADGE  = ("Segoe UI", 8, "bold")

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.observer = None
        self.watching = False
        self.organizer = None

        self.title("Folder Organizer Pro")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(bg=self.DARK_BG)
        self._setup_styles()
        self._build_ui()

        if self.cfg.get("watch_on_start") and WATCHDOG_AVAILABLE:
            self.after(800, self._toggle_watch)

    # ── styles ──────────────────────────────
    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook", background=self.DARK_BG, borderwidth=0)
        s.configure("TNotebook.Tab",
                    background=self.PANEL, foreground=self.MUTED,
                    padding=[14, 8], font=self.FONT_BODY, borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", self.CARD)],
              foreground=[("selected", self.ACCENT2)])
        s.configure("TFrame", background=self.DARK_BG)
        s.configure("Card.TFrame", background=self.CARD)
        s.configure("Panel.TFrame", background=self.PANEL)
        s.configure("TLabel", background=self.DARK_BG, foreground=self.TEXT, font=self.FONT_BODY)
        s.configure("Title.TLabel", font=self.FONT_TITLE, foreground=self.ACCENT2)
        s.configure("H2.TLabel", font=self.FONT_H2, foreground=self.TEXT)
        s.configure("Muted.TLabel", foreground=self.MUTED, font=self.FONT_BODY)
        s.configure("TCheckbutton", background=self.DARK_BG, foreground=self.TEXT, font=self.FONT_BODY)
        s.map("TCheckbutton", background=[("active", self.DARK_BG)])
        s.configure("TEntry", fieldbackground=self.PANEL, foreground=self.TEXT,
                    insertcolor=self.TEXT, borderwidth=1, relief="flat")
        s.configure("TScrollbar", background=self.PANEL, troughcolor=self.DARK_BG,
                    arrowcolor=self.MUTED, borderwidth=0)
        s.configure("Horizontal.TProgressbar",
                    troughcolor=self.PANEL, background=self.ACCENT2,
                    borderwidth=0, thickness=4)

    # ── top layout ──────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=self.PANEL, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⚙  Folder Organizer Pro", font=self.FONT_TITLE,
                 bg=self.PANEL, fg=self.ACCENT2).pack(side="left", padx=20, pady=12)
        self._status_dot = tk.Label(hdr, text="●  Idle", font=("Segoe UI", 10, "bold"),
                                    bg=self.PANEL, fg=self.MUTED)
        self._status_dot.pack(side="right", padx=20)

        # Body
        body = tk.Frame(self, bg=self.DARK_BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # Left sidebar
        sidebar = tk.Frame(body, bg=self.PANEL, width=260)
        sidebar.pack(side="left", fill="y", padx=(0, 12))
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        # Right content
        content = tk.Frame(body, bg=self.DARK_BG)
        content.pack(side="left", fill="both", expand=True)
        self._build_notebook(content)

    # ── sidebar ─────────────────────────────
    def _build_sidebar(self, parent):
        tk.Label(parent, text="TARGET FOLDER", font=self.FONT_BADGE,
                 bg=self.PANEL, fg=self.MUTED).pack(anchor="w", padx=14, pady=(16, 4))

        path_frame = tk.Frame(parent, bg=self.PANEL)
        path_frame.pack(fill="x", padx=14)
        self._folder_var = tk.StringVar(value=self.cfg["folder_path"])
        folder_entry = tk.Entry(path_frame, textvariable=self._folder_var,
                                font=("Consolas", 8), bg="#0f0f23", fg=self.TEXT,
                                insertbackground=self.TEXT, relief="flat", bd=4)
        folder_entry.pack(side="left", fill="x", expand=True)
        tk.Button(path_frame, text="…", font=self.FONT_BADGE,
                  bg=self.CARD, fg=self.TEXT, relief="flat", bd=0,
                  activebackground=self.ACCENT, activeforeground="white",
                  command=self._browse_folder, padx=6).pack(side="left", padx=(4, 0))

        # ── stat cards ──
        tk.Label(parent, text="SESSION STATS", font=self.FONT_BADGE,
                 bg=self.PANEL, fg=self.MUTED).pack(anchor="w", padx=14, pady=(20, 6))

        self._stat_vars = {}
        stats_data = [
            ("moved",   "Moved",        self.SUCCESS),
            ("auto",    "Auto-detected", self.AUTO),
            ("ignored", "Ignored",      self.MUTED),
            ("others",  "Others",       self.WARN),
            ("errors",  "Errors",       self.ERROR),
        ]
        for key, label, color in stats_data:
            row = tk.Frame(parent, bg="#0f0f23", pady=6)
            row.pack(fill="x", padx=14, pady=2)
            tk.Label(row, text=label, font=("Segoe UI", 9), bg="#0f0f23",
                     fg=self.MUTED).pack(side="left", padx=8)
            var = tk.StringVar(value="0")
            self._stat_vars[key] = var
            tk.Label(row, textvariable=var, font=("Segoe UI", 12, "bold"),
                     bg="#0f0f23", fg=color).pack(side="right", padx=8)

        # ── action buttons ──
        tk.Label(parent, text="ACTIONS", font=self.FONT_BADGE,
                 bg=self.PANEL, fg=self.MUTED).pack(anchor="w", padx=14, pady=(20, 6))

        btn_cfg = [
            ("▶  Organize Now",   self.ACCENT,  self._run_organize),
            ("👁  Toggle Watch",   self.ACCENT2, self._toggle_watch),
            ("🗑  Clear Log",      "#334",       self._clear_log),
            ("💾  Save Config",    "#334",       self._save_config_ui),
            ("↺  Reset Defaults", "#334",       self._reset_defaults),
        ]
        for label, color, cmd in btn_cfg:
            b = tk.Button(parent, text=label, font=("Segoe UI", 10, "bold"),
                          bg=color, fg="white", relief="flat", bd=0,
                          activebackground=self.DARK_BG, activeforeground=self.TEXT,
                          cursor="hand2", command=cmd, pady=8)
            b.pack(fill="x", padx=14, pady=3)

        if not WATCHDOG_AVAILABLE:
            tk.Label(parent, text="⚠ watchdog not installed\n(watch disabled)",
                     font=("Segoe UI", 8), bg=self.PANEL, fg=self.WARN,
                     justify="center").pack(padx=14, pady=(8, 0))

    # ── notebook ────────────────────────────
    def _build_notebook(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)

        self._build_tab_log(nb)
        self._build_tab_categories(nb)
        self._build_tab_ignore(nb)
        self._build_tab_options(nb)
        self._build_tab_help(nb)

    # ── TAB: Log ────────────────────────────
    def _build_tab_log(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Activity Log  ")

        toolbar = tk.Frame(frame, bg=self.DARK_BG)
        toolbar.pack(fill="x", pady=(8, 4), padx=8)
        tk.Label(toolbar, text="Live activity feed", bg=self.DARK_BG,
                 fg=self.MUTED, font=("Segoe UI", 9)).pack(side="left")
        self._filter_var = tk.StringVar(value="All")
        for opt in ("All", "Moved", "Errors", "Ignored"):
            tk.Radiobutton(toolbar, text=opt, variable=self._filter_var, value=opt,
                           bg=self.DARK_BG, fg=self.TEXT, selectcolor=self.CARD,
                           activebackground=self.DARK_BG, font=("Segoe UI", 9),
                           command=self._filter_log).pack(side="left", padx=6)

        log_frame = tk.Frame(frame, bg="#080818")
        log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._log_text = tk.Text(log_frame, font=self.FONT_MONO, bg="#080818",
                                 fg=self.TEXT, relief="flat", bd=0,
                                 state="disabled", wrap="none",
                                 selectbackground=self.CARD)
        scrolly = tk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        scrollx = tk.Scrollbar(log_frame, orient="horizontal", command=self._log_text.xview)
        self._log_text.configure(yscrollcommand=scrolly.set, xscrollcommand=scrollx.set)
        scrolly.pack(side="right", fill="y")
        scrollx.pack(side="bottom", fill="x")
        self._log_text.pack(fill="both", expand=True)

        # colour tags
        self._log_text.tag_config("success", foreground=self.SUCCESS)
        self._log_text.tag_config("error",   foreground=self.ERROR)
        self._log_text.tag_config("warn",    foreground=self.WARN)
        self._log_text.tag_config("auto",    foreground=self.AUTO)
        self._log_text.tag_config("info",    foreground=self.ACCENT2)
        self._log_text.tag_config("muted",   foreground=self.MUTED)

        self._log_entries = []   # (tag, text)
        self._log("Welcome to Folder Organizer Pro. Configure settings and click Organize Now.", "info")

    # ── TAB: Categories ─────────────────────
    def _build_tab_categories(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Categories  ")

        top = tk.Frame(frame, bg=self.DARK_BG)
        top.pack(fill="x", padx=10, pady=(10, 6))
        tk.Label(top, text="File type → category mappings", bg=self.DARK_BG,
                 fg=self.MUTED, font=("Segoe UI", 9)).pack(side="left")
        tk.Button(top, text="+ Add Category", font=("Segoe UI", 9, "bold"),
                  bg=self.ACCENT, fg="white", relief="flat", bd=0,
                  activebackground="#c0364d", cursor="hand2",
                  command=self._add_category, pady=4, padx=8).pack(side="right")

        cols_frame = tk.Frame(frame, bg=self.DARK_BG)
        cols_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        canvas = tk.Canvas(cols_frame, bg=self.DARK_BG, highlightthickness=0)
        vsb = tk.Scrollbar(cols_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._cat_inner = tk.Frame(canvas, bg=self.DARK_BG)
        win = canvas.create_window((0, 0), window=self._cat_inner, anchor="nw")
        self._cat_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        self._cat_canvas = canvas

        self._cat_widgets = {}
        self._refresh_categories()

    def _refresh_categories(self):
        for w in self._cat_inner.winfo_children():
            w.destroy()
        self._cat_widgets = {}

        for cat, exts in self.cfg["file_types"].items():
            self._add_category_row(cat, exts)

    def _add_category_row(self, cat, exts):
        row = tk.Frame(self._cat_inner, bg=self.CARD, pady=6)
        row.pack(fill="x", pady=3, padx=2)

        # category name
        name_var = tk.StringVar(value=cat)
        name_entry = tk.Entry(row, textvariable=name_var, font=("Segoe UI", 10, "bold"),
                               bg=self.PANEL, fg=self.ACCENT2, relief="flat", bd=4, width=14)
        name_entry.pack(side="left", padx=(8, 4))

        # extensions text
        ext_var = tk.StringVar(value="  ".join(exts))
        ext_entry = tk.Entry(row, textvariable=ext_var, font=("Consolas", 9),
                              bg="#0f0f23", fg=self.TEXT, relief="flat", bd=4)
        ext_entry.pack(side="left", fill="x", expand=True, padx=4)

        def save_row():
            old_name = [k for k, v in self._cat_widgets.items() if v == (name_var, ext_var)]
            new_name = name_var.get().strip()
            new_exts = [e.strip().lower() for e in ext_var.get().replace(",", " ").split() if e.strip()]
            if old_name:
                del self.cfg["file_types"][old_name[0]]
            self.cfg["file_types"][new_name] = new_exts
            self._log(f"Category '{new_name}' updated.", "info")

        def delete_row():
            name = name_var.get().strip()
            if name in self.cfg["file_types"]:
                del self.cfg["file_types"][name]
            row.destroy()
            if name in self._cat_widgets:
                del self._cat_widgets[name]
            self._log(f"Category '{name}' removed.", "warn")

        tk.Button(row, text="✔", font=("Segoe UI", 10), bg="#1a3a1a", fg=self.SUCCESS,
                  relief="flat", bd=0, cursor="hand2", command=save_row, padx=6).pack(side="right", padx=2)
        tk.Button(row, text="✖", font=("Segoe UI", 10), bg="#3a1a1a", fg=self.ERROR,
                  relief="flat", bd=0, cursor="hand2", command=delete_row, padx=6).pack(side="right", padx=2)

        self._cat_widgets[cat] = (name_var, ext_var)

    def _add_category(self):
        name = f"New_Category_{len(self.cfg['file_types'])+1}"
        self.cfg["file_types"][name] = []
        self._add_category_row(name, [])

    # ── TAB: Ignore list ────────────────────
    def _build_tab_ignore(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Ignore List  ")

        tk.Label(frame, text="Extensions to skip (one per line or space-separated):",
                 bg=self.DARK_BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(10, 4))

        self._ignore_text = tk.Text(frame, font=("Consolas", 10), bg="#080818", fg=self.WARN,
                                     relief="flat", bd=0, height=10, insertbackground=self.TEXT)
        self._ignore_text.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self._ignore_text.insert("1.0", "\n".join(self.cfg["ignore_extensions"]))

        tk.Button(frame, text="Apply Ignore List", font=("Segoe UI", 10, "bold"),
                  bg=self.ACCENT, fg="white", relief="flat", bd=0,
                  command=self._apply_ignore, pady=6).pack(padx=12, pady=(0, 10))

    def _apply_ignore(self):
        raw = self._ignore_text.get("1.0", "end")
        exts = [e.strip().lower() for e in raw.replace(",", " ").split() if e.strip()]
        self.cfg["ignore_extensions"] = exts
        self._log(f"Ignore list updated: {len(exts)} extension(s).", "info")

    # ── TAB: Options ────────────────────────
    def _build_tab_options(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Options  ")

        options = [
            ("auto_detect_new",  "Auto-detect unknown file types (create new folders)"),
            ("skip_scripts",     "Skip Python scripts (.py) in target folder"),
            ("watch_on_start",   "Start file watcher automatically on launch"),
            ("move_to_others",   "Move uncategorized files to 'Others' folder"),
        ]

        self._opt_vars = {}
        for i, (key, label) in enumerate(options):
            var = tk.BooleanVar(value=self.cfg.get(key, True))
            self._opt_vars[key] = var
            row = tk.Frame(frame, bg=self.CARD)
            row.pack(fill="x", padx=12, pady=4)
            tk.Checkbutton(row, text=f"  {label}", variable=var,
                           bg=self.CARD, fg=self.TEXT, selectcolor=self.DARK_BG,
                           activebackground=self.CARD, font=("Segoe UI", 10),
                           pady=10, command=self._apply_options).pack(anchor="w", padx=10)

        tk.Label(frame, text="", bg=self.DARK_BG).pack()
        tk.Label(frame, text="Watchdog Status:", bg=self.DARK_BG,
                 fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=16)
        status = "✔  Installed and available" if WATCHDOG_AVAILABLE else "✖  Not installed — run: pip install watchdog"
        col = self.SUCCESS if WATCHDOG_AVAILABLE else self.ERROR
        tk.Label(frame, text=status, bg=self.DARK_BG, fg=col, font=("Consolas", 10)).pack(anchor="w", padx=16)

    def _apply_options(self):
        for key, var in self._opt_vars.items():
            self.cfg[key] = var.get()

    # ── TAB: Help ───────────────────────────
    def _build_tab_help(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Help  ")

        help_text = tk.Text(frame, font=("Segoe UI", 10), bg=self.PANEL, fg=self.TEXT,
                             relief="flat", bd=0, wrap="word", state="normal", padx=16, pady=14)
        help_text.pack(fill="both", expand=True)

        sections = [
            ("Folder Organizer Pro — Quick Guide\n", "h1"),
            ("\nOrganize Now\n", "h2"),
            ("Scans all loose files in the target folder and moves them into category subfolders.\n", "body"),
            ("\nToggle Watch\n", "h2"),
            ("Starts/stops a real-time watcher. New files that land in the folder are automatically sorted.\nRequires 'watchdog' (pip install watchdog).\n", "body"),
            ("\nCategories Tab\n", "h2"),
            ("Edit category names and their associated extensions. Separate extensions with spaces. Click ✔ to save a row or ✖ to remove it.\n", "body"),
            ("\nIgnore List Tab\n", "h2"),
            ("Extensions listed here are never moved. Useful for system files, temp files, etc.\n", "body"),
            ("\nOptions Tab\n", "h2"),
            ("• Auto-detect: unknown extensions get their own folder (e.g. .xd → XD/).\n• Skip scripts: avoids moving the organizer script itself.\n• Watch on start: auto-activates the watcher when the app opens.\n• Move to Others: files with no extension go to Others/.\n", "body"),
            ("\nConfig is saved to ~/.folder_organizer_config.json\n", "muted"),
        ]
        help_text.tag_config("h1", font=("Segoe UI", 14, "bold"), foreground=self.ACCENT2, spacing1=6)
        help_text.tag_config("h2", font=("Segoe UI", 11, "bold"), foreground=self.ACCENT, spacing1=4)
        help_text.tag_config("body", font=("Segoe UI", 10), foreground=self.TEXT, spacing1=2)
        help_text.tag_config("muted", font=("Segoe UI", 9, "italic"), foreground=self.MUTED)

        for content, tag in sections:
            help_text.insert("end", content, tag)
        help_text.configure(state="disabled")

    # ── ACTIONS ─────────────────────────────
    def _browse_folder(self):
        path = filedialog.askdirectory(title="Select Folder to Organize",
                                        initialdir=self.cfg["folder_path"])
        if path:
            self._folder_var.set(path)
            self.cfg["folder_path"] = path
            self._log(f"Target folder set: {path}", "info")

    def _sync_folder_from_entry(self):
        self.cfg["folder_path"] = self._folder_var.get().strip()

    def _run_organize(self):
        self._sync_folder_from_entry()
        if not os.path.isdir(self.cfg["folder_path"]):
            messagebox.showerror("Error", f"Folder not found:\n{self.cfg['folder_path']}")
            return
        self._apply_options()
        self._apply_ignore()

        org = Organizer(self.cfg, self._log)
        self._log("─" * 60, "muted")
        self._log(f"Started: {datetime.now().strftime('%H:%M:%S')}", "info")

        def task():
            org.organize_existing()
            for key, val in org.stats.items():
                self._stat_vars[key].set(str(val))

        threading.Thread(target=task, daemon=True).start()

    def _toggle_watch(self):
        if not WATCHDOG_AVAILABLE:
            messagebox.showwarning("watchdog missing", "Install watchdog:\n  pip install watchdog")
            return
        self._sync_folder_from_entry()
        if not os.path.isdir(self.cfg["folder_path"]):
            messagebox.showerror("Error", f"Folder not found:\n{self.cfg['folder_path']}")
            return

        if self.watching:
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None
            self.watching = False
            self._status_dot.config(text="●  Idle", fg=self.MUTED)
            self._log("Watcher stopped.", "warn")
        else:
            self._apply_options()
            org = Organizer(self.cfg, self._log)
            handler = WatchHandler(org)
            self.observer = Observer()
            self.observer.schedule(handler, self.cfg["folder_path"], recursive=False)
            self.observer.start()
            self.watching = True
            self._status_dot.config(text="●  Watching", fg=self.SUCCESS)
            self._log(f"Watching: {self.cfg['folder_path']}", "info")

    def _clear_log(self):
        self._log_entries.clear()
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def _save_config_ui(self):
        self._sync_folder_from_entry()
        self._apply_options()
        self._apply_ignore()
        # pull category changes from widgets
        for cat, (name_var, ext_var) in self._cat_widgets.items():
            name = name_var.get().strip()
            exts = [e.strip().lower() for e in ext_var.get().replace(",", " ").split() if e.strip()]
            if name:
                self.cfg["file_types"][name] = exts
        save_config(self.cfg)
        self._log("Configuration saved to disk.", "success")
        messagebox.showinfo("Saved", "Configuration saved successfully.")

    def _reset_defaults(self):
        if not messagebox.askyesno("Reset", "Reset all settings to defaults?"):
            return
        self.cfg["file_types"] = DEFAULT_FILE_TYPES.copy()
        self.cfg["ignore_extensions"] = DEFAULT_IGNORE.copy()
        self.cfg["auto_detect_new"] = True
        self.cfg["skip_scripts"] = True
        self.cfg["watch_on_start"] = False
        self.cfg["move_to_others"] = True
        self._refresh_categories()
        self._ignore_text.delete("1.0", "end")
        self._ignore_text.insert("1.0", "\n".join(self.cfg["ignore_extensions"]))
        for key, var in self._opt_vars.items():
            var.set(self.cfg.get(key, True))
        self._log("Settings reset to defaults.", "info")

    def _filter_log(self):
        filt = self._filter_var.get()
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        for tag, line in self._log_entries:
            if filt == "All":
                self._log_text.insert("end", line + "\n", tag)
            elif filt == "Moved" and tag in ("success", "auto"):
                self._log_text.insert("end", line + "\n", tag)
            elif filt == "Errors" and tag == "error":
                self._log_text.insert("end", line + "\n", tag)
            elif filt == "Ignored" and tag == "muted":
                self._log_text.insert("end", line + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    # ── logging ─────────────────────────────
    def _log(self, msg, tag="body"):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}]  {msg}"
        self._log_entries.append((tag, line))

        self._log_text.configure(state="normal")
        filt = self._filter_var.get()
        show = (filt == "All" or
                (filt == "Moved"   and tag in ("success", "auto")) or
                (filt == "Errors"  and tag == "error") or
                (filt == "Ignored" and tag == "muted"))
        if show:
            self._log_text.insert("end", line + "\n", tag)
            self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def destroy(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        super().destroy()


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = FolderOrganizerApp()
    app.mainloop()
