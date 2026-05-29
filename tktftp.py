import json
import logging
import os
import queue
import socket
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import mytftpy as tftpy
from PIL import Image, ImageDraw, ImageFont, ImageTk


if getattr(sys, "frozen", False):
    APPLICATION_PATH = sys._MEIPASS
else:
    APPLICATION_PATH = os.path.dirname(os.path.abspath(__file__))


COLORS = {
    "bg": "#f8f8f8",
    "panel": "#ffffff",
    "border": "#d9dde2",
    "muted_border": "#e6e9ed",
    "text": "#111111",
    "muted": "#5f6670",
    "blue": "#0066c9",
    "blue_dark": "#0053a5",
    "blue_light": "#3f95dd",
    "blue_bar": "#1f63e9",
    "green": "#37ad25",
    "green_dark": "#249313",
    "green_light": "#71d35d",
    "red": "#d40000",
    "field": "#ffffff",
    "field_border": "#c6cbd2",
}

FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_TITLE = ("Segoe UI", 12, "bold")
FONT_BUTTON = ("Segoe UI", 10, "bold")


def resource_path(name):
    return os.path.join(APPLICATION_PATH, name)


def local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def format_bytes(value):
    if value is None:
        return ""
    value = float(value)
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} GB"


def format_speed(bytes_per_second):
    if bytes_per_second is None:
        return "0 B/s"
    if bytes_per_second < 1024:
        return f"{bytes_per_second:.0f} B/s"
    if bytes_per_second < 1024 * 1024:
        return f"{bytes_per_second / 1024:.0f} KB/s"
    return f"{bytes_per_second / (1024 * 1024):.1f} MB/s"


def format_duration(seconds):
    seconds = max(0, int(seconds or 0))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"00:{minutes:02d}:{seconds:02d}"


def percent_for(done, total, status):
    if status in ("Completed", "Cancelled"):
        return 100 if status == "Completed" else 0
    if total:
        return max(0, min(100, int(done * 100 / total)))
    return 0


def draw_rounded_rect(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def gradient_image(width, height, top, bottom, radius=4, outline=None):
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(gradient)
    top_rgb = tuple(int(top[i : i + 2], 16) for i in (1, 3, 5))
    bottom_rgb = tuple(int(bottom[i : i + 2], 16) for i in (1, 3, 5))
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(top_rgb[i] + (bottom_rgb[i] - top_rgb[i]) * ratio) for i in range(3))
        draw.line((0, y, width, y), fill=color + (255,))
    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)
    image.paste(gradient, (0, 0), mask)
    if outline:
        outline_draw = ImageDraw.Draw(image)
        outline_draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, outline=outline)
    return image


def tk_font(size=18, bold=False):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def make_icon(kind, color, size=24):
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    c = color
    lw = max(2, size // 12)
    if kind == "server":
        for y in (4, 10, 16):
            draw.rounded_rectangle((4, y, size - 4, y + 5), radius=1, outline=c, width=lw)
            draw.ellipse((7, y + 2, 9, y + 4), fill=c)
            draw.line((size - 10, y + 3, size - 6, y + 3), fill=c, width=lw)
    elif kind == "monitor":
        draw.rectangle((4, 4, size - 4, size - 9), outline=c, width=lw)
        draw.line((size // 2, size - 9, size // 2, size - 4), fill=c, width=lw)
        draw.line((7, size - 4, size - 7, size - 4), fill=c, width=lw)
    elif kind == "download":
        draw.line((size // 2, 4, size // 2, size - 8), fill=c, width=lw)
        draw.line((size // 2, size - 8, size // 2 - 6, size - 14), fill=c, width=lw)
        draw.line((size // 2, size - 8, size // 2 + 6, size - 14), fill=c, width=lw)
        draw.line((6, size - 4, size - 6, size - 4), fill=c, width=lw)
    elif kind == "upload":
        draw.line((size // 2, size - 5, size // 2, 7), fill=c, width=lw)
        draw.line((size // 2, 7, size // 2 - 6, 13), fill=c, width=lw)
        draw.line((size // 2, 7, size // 2 + 6, 13), fill=c, width=lw)
        draw.line((6, size - 4, size - 6, size - 4), fill=c, width=lw)
    elif kind == "trash":
        draw.rectangle((8, 9, size - 8, size - 4), outline=c, width=lw)
        draw.line((6, 7, size - 6, 7), fill=c, width=lw)
        draw.line((10, 5, size - 10, 5), fill=c, width=lw)
        draw.line((11, 12, 11, size - 7), fill=c, width=lw)
        draw.line((size - 11, 12, size - 11, size - 7), fill=c, width=lw)
    elif kind == "cancel":
        draw.ellipse((4, 4, size - 4, size - 4), outline=c, width=lw)
        draw.line((8, 8, size - 8, size - 8), fill=c, width=lw)
    photo = ImageTk.PhotoImage(image)
    return photo


@dataclass
class TransferRecord:
    id: str
    file_name: str
    direction: str
    status: str
    peer: str
    bytes_done: int = 0
    bytes_total: int | None = None
    started_at: float = 0
    ended_at: float | None = None
    error: str | None = None

    @property
    def progress(self):
        return percent_for(self.bytes_done, self.bytes_total, self.status)

    @property
    def speed(self):
        end = self.ended_at or time.time()
        elapsed = max(0.001, end - (self.started_at or end))
        return self.bytes_done / elapsed


class ProgressBar(tk.Canvas):
    def __init__(self, master, height=24, compact=False, **kwargs):
        super().__init__(
            master,
            height=height,
            highlightthickness=0,
            bg=COLORS["panel"],
            bd=0,
            **kwargs,
        )
        self.percent = 0
        self.compact = compact
        self.bind("<Configure>", lambda _event: self.draw())
        self.draw()

    def set(self, percent):
        self.percent = max(0, min(100, int(percent or 0)))
        self.draw()

    def draw(self):
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        self.delete("all")
        pad = 1 if self.compact else 0
        radius = 3
        self.create_rectangle(
            pad,
            pad,
            width - pad,
            height - pad,
            fill="#f8f8f8",
            outline=COLORS["field_border"],
        )
        fill_width = int((width - 2 * pad) * self.percent / 100)
        if fill_width > 2:
            bar = ImageTk.PhotoImage(
                gradient_image(
                    max(2, fill_width),
                    max(2, height - 2 * pad),
                    "#4e8cff",
                    COLORS["blue_bar"],
                    radius=radius,
                )
            )
            self._bar_image = bar
            self.create_image(pad, pad, anchor="nw", image=bar)
        self.create_text(
            width // 2,
            height // 2,
            text=f"{self.percent}%",
            fill=COLORS["text"],
            font=FONT_SMALL,
        )


class GradientButton(tk.Canvas):
    def __init__(self, master, text, icon, command, top, bottom, width=180, height=44):
        super().__init__(
            master,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            bg=COLORS["panel"],
            cursor="hand2",
        )
        self.text = text
        self.command = command
        self.top = top
        self.bottom = bottom
        self.width = width
        self.height = height
        self.icon = icon
        self.enabled = True
        self.hover = False
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonRelease-1>", self.on_click)
        self.draw()

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self.draw()

    def on_enter(self, _event):
        self.hover = True
        self.draw()

    def on_leave(self, _event):
        self.hover = False
        self.draw()

    def on_click(self, _event):
        if self.enabled and self.command:
            self.command()

    def draw(self):
        self.delete("all")
        top = self.top if self.enabled else "#d6d6d6"
        bottom = self.bottom if self.enabled else "#bcbcbc"
        if self.hover and self.enabled:
            top, bottom = bottom, top
        image = ImageTk.PhotoImage(gradient_image(self.width, self.height, top, bottom, radius=5, outline=bottom))
        self._image = image
        self.create_image(0, 0, anchor="nw", image=image)
        self.create_image(self.width // 2 - 42, self.height // 2, image=self.icon)
        self.create_text(
            self.width // 2 + 10,
            self.height // 2,
            text=self.text,
            fill="#ffffff",
            font=FONT_BUTTON,
        )


class ModernButton(tk.Canvas):
    def __init__(self, master, text, command, icon=None, width=120, height=40):
        super().__init__(
            master,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            bg=COLORS["panel"],
            cursor="hand2",
        )
        self.text = text
        self.command = command
        self.icon = icon
        self.width = width
        self.height = height
        self.hover = False
        self.enabled = True
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonRelease-1>", self.on_click)
        self.draw()

    def on_enter(self, _event):
        self.hover = True
        self.draw()

    def on_leave(self, _event):
        self.hover = False
        self.draw()

    def on_click(self, _event):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self.draw()

    def draw(self):
        self.delete("all")
        top = "#ffffff" if (not self.hover or not self.enabled) else "#f7fbff"
        bottom = "#ffffff" if (not self.hover or not self.enabled) else "#eef6ff"
        outline = "#8bb7ff"
        text_fill = COLORS["blue"] if self.enabled else "#6f9fe5"
        image = ImageTk.PhotoImage(gradient_image(self.width, self.height, top, bottom, radius=4, outline=outline))
        self._image = image
        self.create_image(0, 0, anchor="nw", image=image)
        text_x = self.width // 2
        if self.icon:
            self.create_image(self.width // 2 - 46, self.height // 2 - 2, image=self.icon)
            text_x += 12
        self.create_text(text_x, self.height // 2 - 2, text=self.text, fill=text_fill, font=FONT)


class TransferTable(tk.Frame):
    COLUMNS = [
        ("File Name", 0.20),
        ("Status", 0.12),
        ("Progress", 0.22),
        ("Peer IP:Port", 0.19),
        ("Size", 0.12),
        ("Speed", 0.15),
    ]
    HEADER_HEIGHT = 36
    ROW_HEIGHT = 42

    def __init__(self, master):
        super().__init__(master, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
        self.record_ids = []
        self.records = {}
        self.canvas = tk.Canvas(self, bg=COLORS["panel"], bd=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", lambda _event: self.draw())

    def upsert(self, record):
        if record.id not in self.records:
            self.record_ids.insert(0, record.id)
        self.records[record.id] = record
        self.draw()

    def clear_completed(self):
        for record_id in list(self.record_ids):
            record = self.records.get(record_id)
            if record and record.status in ("Completed", "Failed", "Cancelled"):
                self.record_ids.remove(record_id)
                del self.records[record_id]
        self.draw()

    def draw(self):
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        table_width = max(1, width - 2)
        self.canvas.delete("all")
        x_positions = [1]
        for _title, ratio in self.COLUMNS:
            x_positions.append(x_positions[-1] + int(table_width * ratio))
        x_positions[-1] = table_width + 1

        self.canvas.create_rectangle(1, 1, table_width, self.HEADER_HEIGHT, fill="#fbfbfb", outline=COLORS["border"])
        for index, (title, _ratio) in enumerate(self.COLUMNS):
            x0, x1 = x_positions[index], x_positions[index + 1]
            self.canvas.create_line(x1, 1, x1, self.HEADER_HEIGHT, fill=COLORS["muted_border"])
            self.canvas.create_text((x0 + x1) // 2, self.HEADER_HEIGHT // 2 + 1, text=title, fill=COLORS["text"], font=("Segoe UI", 10, "bold"))

        for row_index, record_id in enumerate(self.record_ids):
            record = self.records[record_id]
            y0 = self.HEADER_HEIGHT + row_index * self.ROW_HEIGHT
            y1 = y0 + self.ROW_HEIGHT
            self.canvas.create_rectangle(1, y0, table_width, y1, fill=COLORS["panel"], outline=COLORS["muted_border"])
            for x in x_positions[1:-1]:
                self.canvas.create_line(x, y0, x, y1, fill=COLORS["muted_border"])
            values = [
                Path(record.file_name or "").name or record.file_name or "",
                record.status,
                None,
                record.peer,
                format_bytes(record.bytes_total or record.bytes_done),
                format_speed(record.speed if record.status != "Failed" else 0),
            ]
            for col_index, value in enumerate(values):
                x0, x1 = x_positions[col_index], x_positions[col_index + 1]
                if col_index == 2:
                    if record.status == "Failed" and record.error:
                        self.draw_failure_reason(x0, x1, y0, y1, record.error)
                    else:
                        self.draw_progress_cell(x0, x1, y0, y1, record.progress)
                else:
                    fill = status_color(record.status) if col_index == 1 else COLORS["text"]
                    anchor = "center"
                    self.canvas.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=value, fill=fill, font=FONT_SMALL, anchor=anchor)

        content_height = self.HEADER_HEIGHT + max(len(self.record_ids), 1) * self.ROW_HEIGHT
        self.canvas.configure(scrollregion=(0, 0, table_width, content_height))

    def draw_progress_cell(self, x0, x1, y0, y1, percent):
        bar_width = min(92, max(64, int((x1 - x0) * 0.42)))
        bar_height = 16
        bar_x = x0 + 14
        bar_y = y0 + (self.ROW_HEIGHT - bar_height) // 2
        self.canvas.create_rectangle(bar_x, bar_y, bar_x + bar_width, bar_y + bar_height, fill="#f8f8f8", outline=COLORS["field_border"])
        fill_width = int(bar_width * max(0, min(100, percent)) / 100)
        if fill_width > 0:
            self.canvas.create_rectangle(bar_x + 1, bar_y + 1, bar_x + fill_width - 1, bar_y + bar_height - 1, fill=COLORS["blue_bar"], outline=COLORS["blue_bar"])
        self.canvas.create_text(x1 - 26, y0 + self.ROW_HEIGHT // 2, text=f"{percent}%", fill=COLORS["text"], font=FONT_SMALL)

    def draw_failure_reason(self, x0, x1, y0, y1, error):
        reason = str(error).replace("\n", " ")
        max_chars = max(12, int((x1 - x0) / 7))
        if len(reason) > max_chars:
            reason = reason[: max_chars - 3] + "..."
        self.canvas.create_text(x0 + 10, y0 + self.ROW_HEIGHT // 2, text=reason, fill=COLORS["red"], font=FONT_SMALL, anchor="w")


def status_color(status):
    if status in ("Running", "Completed"):
        return COLORS["green"]
    if status in ("Receiving", "Sending", "Transferring..."):
        return COLORS["blue"]
    if status in ("Failed", "Cancelled", "Stopped"):
        return COLORS["red"]
    return COLORS["text"]


class TFTPToolApp:
    HISTORY_FILE = "history.json"
    MAX_HISTORY = 30
    LISTEN_PORT = 69
    CLEAR_HISTORY = "Clear History"

    def __init__(self, root):
        self.root = root
        self.root.title("TFTP Tool")
        self.root.configure(bg=COLORS["bg"])
        self.server = None
        self.server_thread = None
        self.server_running = False
        self.client_thread = None
        self.client_cancel = threading.Event()
        self.client = None
        self.ui_queue = queue.Queue()
        self.history = self.load_history()
        self.current_directory = next(iter(self.history), os.getcwd())
        self.records = {}
        self.client_record = None
        self.icons = {}

        self.setup_window()
        self.setup_styles()
        self.setup_icons()
        self.setup_ui()
        self.update_path_combo()
        self.start_server(self.current_directory)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.after(100, self.process_ui_queue)

    def setup_window(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = max(860, screen_width // 2)
        height = max(520, screen_height // 2)
        x = max(0, int((self.root.winfo_screenwidth() - width) / 2))
        y = max(0, int((self.root.winfo_screenheight() - height) / 2))
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(860, 520)
        icon_path = resource_path("icon.png")
        if os.path.exists(icon_path):
            self._app_icon = ImageTk.PhotoImage(Image.open(icon_path))
            self.root.iconphoto(True, self._app_icon)

    def setup_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=FONT)
        style.configure("TButton", font=FONT, padding=(12, 6), background="#ffffff", relief="raised")
        style.configure("TEntry", fieldbackground=COLORS["field"], bordercolor=COLORS["field_border"], padding=4)
        style.configure("TCombobox", fieldbackground=COLORS["field"], bordercolor=COLORS["blue"], padding=4)
        style.configure("Vertical.TScrollbar", background="#f0f0f0", troughcolor="#fafafa")
        style.configure("Panel.TLabelframe", background=COLORS["panel"], bordercolor=COLORS["border"], relief="solid")
        style.configure("Panel.TLabelframe.Label", background=COLORS["panel"], foreground=COLORS["blue"], font=FONT_TITLE)

    def setup_icons(self):
        self.icons = {
            "server": make_icon("server", COLORS["blue"], 24),
            "monitor": make_icon("monitor", COLORS["blue"], 24),
            "download": make_icon("download", "#ffffff", 24),
            "upload": make_icon("upload", "#ffffff", 24),
            "download_blue": make_icon("download", COLORS["blue"], 22),
            "upload_blue": make_icon("upload", COLORS["blue"], 22),
            "trash": make_icon("trash", COLORS["blue"], 18),
            "cancel": make_icon("cancel", COLORS["blue"], 20),
            "globe": make_icon("monitor", COLORS["blue"], 18),
            "port": make_icon("server", COLORS["blue"], 18),
            "swap": make_icon("download", COLORS["blue"], 18),
            "ok": make_icon("cancel", COLORS["green"], 18),
            "fail": make_icon("cancel", COLORS["red"], 18),
        }

    def setup_ui(self):
        container = tk.Frame(self.root, bg=COLORS["bg"])
        container.pack(fill="both", expand=True, padx=10, pady=10)
        container.grid_columnconfigure(0, weight=3, uniform="main")
        container.grid_columnconfigure(1, weight=2, uniform="main")
        container.grid_rowconfigure(0, weight=1)

        self.server_panel = self.create_panel(container)
        self.server_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.client_panel = self.create_panel(container)
        self.client_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.footer = self.create_panel(container, height=48)
        self.footer.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self.setup_server_panel()
        self.setup_client_panel()
        self.setup_footer()

    def create_panel(self, master, height=None):
        frame = tk.Frame(master, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
        if height:
            frame.configure(height=height)
            frame.grid_propagate(False)
        return frame

    def section_title(self, master, icon, text):
        frame = tk.Frame(master, bg=COLORS["panel"])
        tk.Label(frame, image=icon, bg=COLORS["panel"]).pack(side="left", padx=(0, 8))
        tk.Label(frame, text=text, bg=COLORS["panel"], fg=COLORS["blue"], font=FONT_TITLE).pack(side="left")
        return frame

    def label_frame(self, master, title):
        frame = ttk.LabelFrame(master, text=f"  {title}  ", style="Panel.TLabelframe")
        return frame

    def setup_server_panel(self):
        self.server_panel.grid_columnconfigure(0, weight=1)
        self.section_title(self.server_panel, self.icons["server"], "TFTP Server").grid(row=0, column=0, sticky="w", padx=16, pady=(10, 6))

        config = ttk.LabelFrame(self.server_panel, text="  Server Configuration  ", style="Panel.TLabelframe")
        config.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 8))
        config.grid_columnconfigure(1, weight=1)
        config.grid_columnconfigure(3, weight=1)

        tk.Label(config, text="Root Directory:", bg=COLORS["panel"], fg=COLORS["text"], font=FONT).grid(row=0, column=0, sticky="w", padx=10, pady=(14, 8))
        self.path_var = tk.StringVar(value=self.current_directory)
        self.path_combo = ttk.Combobox(config, textvariable=self.path_var, font=FONT)
        self.path_combo.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(0, 10), pady=(14, 8), ipady=3)
        self.path_combo.bind("<<ComboboxSelected>>", self.on_path_change)
        self.path_combo.bind("<Button-1>", lambda event: self.path_combo.event_generate("<Down>"))
        ModernButton(config, "Browse...", self.browse_root, width=112, height=36).grid(row=0, column=4, sticky="ew", padx=(0, 10), pady=(14, 8))

        tk.Label(config, text="Status:", bg=COLORS["panel"], fg=COLORS["text"], font=FONT).grid(row=1, column=0, sticky="w", padx=10, pady=(8, 14))
        self.server_status_var = tk.StringVar(value="Starting")
        self.server_status_label = tk.Label(config, textvariable=self.server_status_var, bg=COLORS["panel"], fg=COLORS["blue"], font=FONT_BUTTON)
        self.server_status_label.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(8, 14))

        transfers = ttk.LabelFrame(self.server_panel, text="  Transfer List  ", style="Panel.TLabelframe")
        transfers.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 8))
        transfers.grid_columnconfigure(0, weight=1)
        transfers.grid_rowconfigure(0, weight=1)
        self.server_panel.grid_rowconfigure(2, weight=1)
        self.table = TransferTable(transfers)
        self.table.grid(row=0, column=0, sticky="nsew", padx=6, pady=(8, 6))

        clear_button = ModernButton(transfers, "Clear History", self.clear_completed, icon=self.icons["trash"], width=150, height=38)
        clear_button.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 8))

    def setup_client_panel(self):
        self.client_panel.grid_columnconfigure(0, weight=1)
        self.section_title(self.client_panel, self.icons["monitor"], "TFTP Client").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 10))

        form = tk.Frame(self.client_panel, bg=COLORS["panel"])
        form.grid(row=1, column=0, sticky="ew", padx=14)
        form.grid_columnconfigure(1, weight=1)

        self.server_ip_var = tk.StringVar(value=local_ip())
        self.port_var = tk.StringVar(value=str(self.LISTEN_PORT))
        self.local_file_var = tk.StringVar()
        self.remote_file_var = tk.StringVar()

        self.form_entry(form, "Server IP:", self.server_ip_var, row=0)
        self.form_port_entry(form, "Port:", self.port_var, row=1)
        self.form_entry(form, "Local File:", self.local_file_var, row=2, browse=True)
        self.form_entry(form, "Remote File:", self.remote_file_var, row=3)

        actions = tk.Frame(self.client_panel, bg=COLORS["panel"])
        actions.grid(row=2, column=0, sticky="ew", padx=14, pady=(12, 14))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        self.get_button = ModernButton(actions, "Get", self.start_get, icon=self.icons["download_blue"], width=132, height=40)
        self.get_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.put_button = ModernButton(actions, "Put", self.start_put, icon=self.icons["upload_blue"], width=132, height=40)
        self.put_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        progress_frame = tk.Frame(self.client_panel, bg=COLORS["panel"])
        progress_frame.grid(row=3, column=0, sticky="ew", padx=14)
        tk.Label(progress_frame, text="Progress", bg=COLORS["panel"], fg=COLORS["blue"], font=FONT_TITLE).pack(anchor="w", pady=(0, 8))
        self.client_progress = ProgressBar(progress_frame, height=24)
        self.client_progress.pack(fill="x")

        details = tk.Frame(self.client_panel, bg=COLORS["panel"])
        details.grid(row=4, column=0, sticky="ew", padx=14, pady=(12, 0))
        details.grid_columnconfigure(1, weight=1)
        self.client_status_var = tk.StringVar(value="Idle")
        self.client_mode_var = tk.StringVar(value="octet")
        self.client_transferred_var = tk.StringVar(value="0 B / 0 B")
        self.client_speed_var = tk.StringVar(value="0 B/s")
        self.client_elapsed_var = tk.StringVar(value="00:00:00")
        self.client_estimated_var = tk.StringVar(value="00:00:00")
        self.client_status_label = self.detail_row(details, "Status:", self.client_status_var, 0, COLORS["blue"])
        self.detail_row(details, "Mode:", self.client_mode_var, 1)
        self.detail_row(details, "Transferred:", self.client_transferred_var, 2)
        self.detail_row(details, "Speed:", self.client_speed_var, 3)
        self.detail_row(details, "Elapsed Time:", self.client_elapsed_var, 4)
        self.detail_row(details, "Estimated Time:", self.client_estimated_var, 5)

        self.client_panel.grid_rowconfigure(5, weight=1)
        self.cancel_button = ModernButton(
            self.client_panel,
            "Cancel",
            self.cancel_client_transfer,
            icon=self.icons["cancel"],
            width=132,
            height=40,
        )
        self.cancel_button.grid(row=6, column=0, sticky="e", padx=14, pady=(0, 14))
        self.set_client_busy(False)

    def form_entry(self, master, label, variable, row, browse=False):
        tk.Label(master, text=label, bg=COLORS["panel"], fg=COLORS["text"], font=FONT).grid(row=row, column=0, sticky="w", pady=5)
        entry = ttk.Entry(master, textvariable=variable, font=FONT)
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 8 if browse else 0), pady=5, ipady=3)
        if browse:
            ModernButton(master, "Browse...", self.browse_local_file, width=112, height=36).grid(row=row, column=2, sticky="ew", pady=5)

    def form_port_entry(self, master, label, variable, row):
        tk.Label(master, text=label, bg=COLORS["panel"], fg=COLORS["text"], font=FONT).grid(row=row, column=0, sticky="w", pady=5)
        entry = ttk.Entry(master, textvariable=variable, width=8, font=FONT)
        entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=5, ipady=3)

    def detail_row(self, master, label, variable, row, color=None):
        tk.Label(master, text=label, bg=COLORS["panel"], fg=COLORS["text"], font=FONT_SMALL).grid(row=row, column=0, sticky="w", pady=4)
        value_label = tk.Label(master, textvariable=variable, bg=COLORS["panel"], fg=color or COLORS["text"], font=FONT_SMALL)
        value_label.grid(row=row, column=1, sticky="w", padx=(28, 0), pady=4)
        return value_label

    def setup_footer(self):
        self.footer.grid_columnconfigure(0, weight=1)
        self.footer_values = {}
        items = [
            ("Server IP:", "0.0.0.0", "globe"),
            ("Port:", str(self.LISTEN_PORT), "port"),
            ("Total Transfers:", "0", "swap"),
            ("Completed:", "0", "completed"),
            ("In Progress:", "0", "progress"),
            ("Failed:", "0", "failed"),
        ]
        for index in range(len(items)):
            self.footer.grid_columnconfigure(index, weight=1)
        for index, (label, value, role) in enumerate(items):
            cell = tk.Frame(self.footer, bg=COLORS["panel"])
            cell.grid(row=0, column=index, sticky="nsew", pady=10)
            if index:
                tk.Frame(cell, bg=COLORS["border"], width=1).pack(side="left", fill="y", padx=(0, 8))
            icon_name = {"completed": "ok", "progress": "swap", "failed": "fail"}.get(role, role)
            if icon_name in self.icons:
                tk.Label(cell, image=self.icons[icon_name], bg=COLORS["panel"]).pack(side="left", padx=(0, 5))
            tk.Label(cell, text=label, bg=COLORS["panel"], fg=COLORS["text"], font=FONT_SMALL).pack(side="left")
            var = tk.StringVar(value=value)
            color = COLORS["text"]
            if role == "completed":
                color = COLORS["green"]
            elif role == "progress":
                color = COLORS["blue"]
            elif role == "failed":
                color = COLORS["red"]
            tk.Label(cell, textvariable=var, bg=COLORS["panel"], fg=color, font=FONT_SMALL).pack(side="left", padx=(5, 6))
            self.footer_values[label] = var

    def load_history(self):
        path = Path(self.HISTORY_FILE)
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as file:
                    history = json.load(file)
                    return dict(sorted(history.items(), key=lambda item: item[1], reverse=True))
            except (OSError, json.JSONDecodeError):
                pass
        return {os.getcwd(): time.time()}

    def save_history(self):
        try:
            with open(self.HISTORY_FILE, "w", encoding="utf-8") as file:
                json.dump(self.history, file, indent=2)
        except OSError:
            pass

    def update_history(self, path):
        self.history[path] = time.time()
        self.history = dict(sorted(self.history.items(), key=lambda item: item[1], reverse=True))
        self.history = dict(list(self.history.items())[: self.MAX_HISTORY])
        self.save_history()

    def update_path_combo(self):
        values = list(self.history.keys()) + [self.CLEAR_HISTORY]
        self.path_combo["values"] = values
        self.path_combo.set(self.current_directory)

    def on_path_change(self, _event=None):
        new_path = self.path_var.get()
        if new_path == self.CLEAR_HISTORY:
            self.history = {self.current_directory: time.time()}
            self.save_history()
            self.update_path_combo()
            return
        if new_path and new_path != self.current_directory:
            self.current_directory = new_path
            self.update_history(new_path)
            self.update_path_combo()
            self.restart_server(new_path)

    def browse_root(self):
        directory = filedialog.askdirectory(initialdir=self.current_directory)
        if directory:
            self.current_directory = directory
            self.update_history(directory)
            self.update_path_combo()
            self.restart_server(directory)

    def browse_local_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.local_file_var.set(path)
            if not self.remote_file_var.get():
                self.remote_file_var.set(os.path.basename(path))

    def start_server(self, directory):
        self.stop_server(update_status=False)
        self.server_status_var.set("Starting")
        self.server_status_label.configure(fg=COLORS["blue"])

        def runner():
            try:
                server = tftpy.TftpServer(directory, cb=self.handle_server_callback)
                self.server = server
                self.ui_queue.put(("server_status", ("Running", None)))
                server.listen(listenip="0.0.0.0", listenport=self.LISTEN_PORT, timeout=0.5)
            except Exception as exc:
                self.ui_queue.put(("server_status", ("Failed", str(exc))))

        self.server_thread = threading.Thread(target=runner, daemon=True)
        self.server_thread.start()

    def stop_server(self, update_status=True):
        server = self.server
        if server:
            try:
                server.stop(now=True)
                self.wake_server()
            except Exception:
                pass
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1.2)
        self.server = None
        self.server_thread = None
        if update_status:
            self.server_status_var.set("Stopped")
            self.server_status_label.configure(fg=COLORS["red"])

    def wake_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(b"\x00\x00", ("127.0.0.1", self.LISTEN_PORT))
        except OSError:
            pass
        finally:
            sock.close()

    def restart_server(self, directory):
        self.start_server(directory)

    def handle_server_callback(self, payload):
        if isinstance(payload, dict):
            self.ui_queue.put(("server_event", payload))

    def start_get(self):
        remote = self.remote_file_var.get().strip()
        if not remote:
            messagebox.showwarning("Missing Remote File", "Please enter a remote file name.")
            return
        local = self.local_file_var.get().strip()
        if not local:
            local = filedialog.asksaveasfilename(initialfile=os.path.basename(remote))
            if not local:
                return
            self.local_file_var.set(local)
        self.start_client_transfer("get", local, remote)

    def start_put(self):
        local = self.local_file_var.get().strip()
        if not local:
            local = filedialog.askopenfilename()
            if not local:
                return
            self.local_file_var.set(local)
        if not os.path.exists(local):
            messagebox.showwarning("Missing Local File", "Local file does not exist.")
            return
        remote = self.remote_file_var.get().strip() or os.path.basename(local)
        self.remote_file_var.set(remote)
        self.start_client_transfer("put", local, remote)

    def start_client_transfer(self, action, local, remote):
        if self.client_thread and self.client_thread.is_alive():
            return
        self.client_cancel.clear()
        self.set_client_busy(True)
        self.client_progress.set(0)
        self.client_status_var.set("Transferring...")
        self.client_transferred_var.set("0 B / 0 B")
        self.client_speed_var.set("0 B/s")
        self.client_elapsed_var.set("00:00:00")
        self.client_estimated_var.set("00:00:00")

        total = os.path.getsize(local) if action == "put" and os.path.exists(local) else None
        host = self.server_ip_var.get().strip()
        try:
            port = int(self.port_var.get())
        except (TypeError, ValueError):
            messagebox.showwarning("Invalid Port", "Please enter a valid port number.")
            self.set_client_busy(False)
            return
        if not 1 <= port <= 65535:
            messagebox.showwarning("Invalid Port", "Port must be between 1 and 65535.")
            self.set_client_busy(False)
            return
        record = TransferRecord(
            id=f"client:{time.time()}",
            file_name=remote,
            direction=action,
            status="Transferring...",
            peer=f"{host}:{port}",
            bytes_done=0,
            bytes_total=total,
            started_at=time.time(),
        )
        self.client_record = record

        self.client_thread = threading.Thread(target=self.run_client_transfer, args=(action, local, remote, record, host, port), daemon=True)
        self.client_thread.start()

    def run_client_transfer(self, action, local, remote, record, host, port):
        transferred = {"bytes": 0, "total": record.bytes_total}
        start = record.started_at
        last_emit = {"percent": -1, "time": 0, "bytes": 0}

        def emit(status=None, error=None, speed_override=None, elapsed_override=None):
            elapsed = elapsed_override if elapsed_override is not None else time.time() - start
            speed = speed_override if speed_override is not None else transferred["bytes"] / max(0.001, elapsed)
            total = transferred["total"]
            percent = percent_for(transferred["bytes"], total, status or "Transferring...")
            eta = 0
            if total and speed > 0 and transferred["bytes"] < total:
                eta = (total - transferred["bytes"]) / speed
            if status is None:
                now = time.time()
                if total:
                    if percent == last_emit["percent"] and now - last_emit["time"] < 0.1:
                        return
                    last_emit["percent"] = percent
                elif now - last_emit["time"] < 0.1:
                    return
                if last_emit["time"]:
                    delta_bytes = transferred["bytes"] - last_emit["bytes"]
                    delta_time = max(0.001, now - last_emit["time"])
                    speed = max(0, delta_bytes / delta_time)
                last_emit["time"] = now
                last_emit["bytes"] = transferred["bytes"]
            self.ui_queue.put(
                (
                    "client_event",
                    {
                        "record": record,
                        "status": status or "Transferring...",
                        "bytes_done": transferred["bytes"],
                        "bytes_total": total,
                        "progress": percent,
                        "speed": speed,
                        "elapsed": elapsed,
                        "eta": eta,
                        "error": error,
                    },
                )
            )

        def hook(packet):
            if self.client_cancel.is_set():
                raise tftpy.TftpException("Cancelled")
            name = packet.__class__.__name__
            if name == "TftpPacketOACK":
                tsize = getattr(packet, "options", {}).get("tsize")
                if tsize not in (None, "0"):
                    try:
                        transferred["total"] = int(tsize)
                    except ValueError:
                        pass
            elif name == "TftpPacketDAT":
                data = getattr(packet, "data", b"")
                if action == "put":
                    transferred["bytes"] = min((transferred["total"] or 0), transferred["bytes"] + len(data)) if transferred["total"] else transferred["bytes"] + len(data)
                else:
                    transferred["bytes"] += len(data)
            emit()

        try:
            options = {"blksize": 1468, "tsize": str(record.bytes_total or 0)}
            self.client = tftpy.TftpClient(host, port, options=options)
            if action == "get":
                self.client.download(remote, local, packethook=hook)
                if transferred["total"] is None and os.path.exists(local):
                    transferred["total"] = os.path.getsize(local)
                    transferred["bytes"] = transferred["total"]
            else:
                self.client.upload(remote, local, packethook=hook)
                transferred["bytes"] = record.bytes_total or transferred["bytes"]
            metrics = self.client.context.metrics if self.client and self.client.context else None
            metric_speed = None
            metric_elapsed = None
            if metrics:
                metric_speed = metrics.kbps * 1024 / 8
                metric_elapsed = metrics.duration
            emit(status="Completed", speed_override=metric_speed, elapsed_override=metric_elapsed)
        except Exception as exc:
            status = "Cancelled" if self.client_cancel.is_set() else "Failed"
            emit(status=status, error=str(exc))
        finally:
            self.client = None
            self.ui_queue.put(("client_done", None))

    def cancel_client_transfer(self):
        self.client_cancel.set()
        client = self.client
        try:
            if client and client.context and client.context.sock:
                client.context.sock.close()
        except Exception:
            pass

    def set_client_busy(self, busy):
        self.get_button.set_enabled(not busy)
        self.put_button.set_enabled(not busy)

    def process_ui_queue(self):
        processed = 0
        max_events = 10
        while processed < max_events:
            try:
                kind, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            processed += 1
            if kind == "server_status":
                self.apply_server_status(*payload)
            elif kind == "server_event":
                self.apply_server_event(payload)
            elif kind == "client_event":
                self.apply_client_event(payload)
            elif kind == "client_done":
                self.set_client_busy(False)
        delay = 16 if processed == max_events else 50
        self.root.after(delay, self.process_ui_queue)

    def apply_server_status(self, status, error):
        self.server_status_var.set(status)
        self.server_status_label.configure(fg=status_color(status))
        if error:
            messagebox.showerror("TFTP Server", error)

    def apply_server_event(self, event):
        if event.get("direction") is None:
            return
        record_id = event.get("id")
        record = self.records.get(record_id)
        status = {
            "send": "Sending",
            "receive": "Receiving",
        }.get(event.get("direction"), "Receiving")
        if not record:
            record = TransferRecord(
                id=record_id,
                file_name=event.get("file_name") or "",
                direction=event.get("direction") or "",
                status=status,
                peer=event.get("peer") or "",
                bytes_done=0,
                bytes_total=event.get("bytes_total"),
                started_at=event.get("started_at") or time.time(),
            )
            self.records[record_id] = record
        record.file_name = event.get("file_name") or record.file_name
        record.peer = event.get("peer") or record.peer
        record.bytes_done = int(event.get("bytes_done") or record.bytes_done or 0)
        if event.get("bytes_total") is not None:
            record.bytes_total = int(event.get("bytes_total"))
        if event.get("event") == "complete":
            record.status = "Completed"
            record.ended_at = time.time()
        elif event.get("event") == "error":
            record.status = "Failed"
            record.error = event.get("error")
            record.ended_at = time.time()
        else:
            record.status = status
        self.table.upsert(record)
        self.update_footer_counts()

    def apply_client_event(self, event):
        status = event["status"]
        error = event.get("error")
        if error and status in ("Failed", "Cancelled"):
            status_text = f"{status}: {error}"
            if len(status_text) > 56:
                status_text = status_text[:53] + "..."
            self.client_status_var.set(status_text)
        else:
            self.client_status_var.set(status)
        self.client_status_label.configure(fg=status_color(status))
        self.client_progress.set(event["progress"])
        done = format_bytes(event["bytes_done"])
        total = format_bytes(event["bytes_total"]) if event["bytes_total"] else "Unknown"
        self.client_transferred_var.set(f"{done} / {total}")
        self.client_speed_var.set(format_speed(self.client_display_speed(event)))
        self.client_elapsed_var.set(format_duration(event["elapsed"]))
        self.client_estimated_var.set(format_duration(event["eta"]))

    def client_display_speed(self, event):
        client_record = event.get("record")
        if not client_record:
            return event["speed"]
        client_name = Path(client_record.file_name or "").name
        matches = [
            record
            for record in self.records.values()
            if Path(record.file_name or "").name == client_name
            and record.status in ("Receiving", "Sending", "Completed")
            and record.bytes_done > 0
        ]
        if not matches:
            return event["speed"]
        matches.sort(key=lambda record: record.ended_at or time.time(), reverse=True)
        return matches[0].speed

    def update_footer_counts(self):
        records = list(self.records.values())
        completed = sum(1 for record in records if record.status == "Completed")
        failed = sum(1 for record in records if record.status in ("Failed", "Cancelled"))
        active = sum(1 for record in records if record.status in ("Receiving", "Sending", "Transferring..."))
        self.footer_values["Total Transfers:"].set(str(len(records)))
        self.footer_values["Completed:"].set(str(completed))
        self.footer_values["In Progress:"].set(str(active))
        self.footer_values["Failed:"].set(str(failed))

    def clear_completed(self):
        for record_id, record in list(self.records.items()):
            if record.status in ("Completed", "Failed", "Cancelled"):
                del self.records[record_id]
        self.table.clear_completed()
        self.update_footer_counts()

    def on_closing(self):
        self.cancel_client_transfer()
        self.stop_server(update_status=False)
        self.root.destroy()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    app = TFTPToolApp(root)
    root.mainloop()
