import os,sys
import json
import time
import multiprocessing
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import logging
import mytftpy as tftpy
from PIL import Image, ImageTk

# 获取应用运行时的临时目录路径
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

class TFTPServerApp:
    HISTORY_FILE = "history.json"
    MAX_HISTORY = 30
    LISTEN_PORT = 69

    def __init__(self, root):
        self.root = root
        self.root.title("TFTP Server")
        self.server_process = None
        self.log_queue = multiprocessing.Queue()
        self.current_directory = os.getcwd()

        self.setup_ui()
        self.setup_logging()

        self.history = self.load_history()
        self.update_path_combo()

        self.start_server(self.current_directory)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        threading.Thread(target=self.process_log_queue, daemon=True).start()

    def setup_ui(self):
        window_width = 800
        window_height = 600

        # Calculate the position to center the window on the screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        position_top = int(screen_height / 2 - window_height / 2)
        position_right = int(screen_width / 2 - window_width / 2)

        self.root.geometry(f"{window_width}x{window_height}+{position_right}+{position_top}")

        # 图标
        icon_path = os.path.join(application_path, "icon.png")
        img = Image.open(icon_path)
        photo = ImageTk.PhotoImage(img)
        root.iconphoto(True, photo)  # 在这里设置窗口和任务栏图标

        self.frame = ttk.Frame(self.root)
        self.frame.grid(column=0, row=0, padx=10, pady=10, sticky='ew')

        self.path_label = ttk.Label(self.frame, text="Current Directory:")
        self.path_label.grid(column=0, row=0, padx=5, pady=5)

        self.path_var = tk.StringVar(value=self.current_directory)
        self.path_combo = ttk.Combobox(self.frame, textvariable=self.path_var)
        self.path_combo.grid(column=1, row=0, padx=5, pady=5, sticky='ew')
        self.path_combo.bind('<<ComboboxSelected>>', self.on_path_change)
        self.path_combo.bind('<Button-1>', self.show_dropdown)

        self.browse_button = ttk.Button(self.frame, text="Browse", command=self.browse)
        self.browse_button.grid(column=2, row=0, padx=5, pady=5)

        self.frame.columnconfigure(1, weight=1)

        self.log_text = scrolledtext.ScrolledText(self.root, width=60, height=20, state='disabled')
        self.log_text.grid(column=0, row=1, padx=10, pady=10, sticky='nsew')

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

    def setup_logging(self):
        self.logger = logging.Logger('tktftp')
        self.logger.setLevel(logging.DEBUG)
        handler = TextHandler(self.log_text, self.root)
        handler.setLevel(logging.DEBUG)
        # formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        logging.getLogger().addHandler(handler)

    def load_history(self):
        if os.path.exists(self.HISTORY_FILE):
            with open(self.HISTORY_FILE, 'r') as file:
                history = json.load(file)
            for path in list(history.keys()):
                if not os.path.exists(path):
                    del history[path]
            # Sort by timestamp (value of the dict)
            return dict(sorted(history.items(), key=lambda item: item[1], reverse=True))
        return {self.current_directory: time.time()}

    def save_history(self):
        with open(self.HISTORY_FILE, 'w') as file:
            json.dump(self.history, file)

    def update_history(self, new_path):
        self.history[new_path] = time.time()
        # Sort by timestamp (value of the dict)
        self.history = dict(sorted(self.history.items(), key=lambda item: item[1], reverse=True))
        # Trim the history to MAX_HISTORY items
        self.history = dict(list(self.history.items())[:self.MAX_HISTORY])
        self.save_history()

    def start_server(self, directory):
        self.stop_server()
        self.server_process = multiprocessing.Process(target=self.run_server, args=(directory, self.log_queue))
        self.server_process.start()
        self.log(f"TFTP Server started at {directory}")

    def run_server(self, directory, log_queue):
        # 自定义日志输出到界面
        logger = logging.getLogger('mylog')
        logger.setLevel(logging.INFO)
        handler = QueueHandler(log_queue)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # 设置原始日志输出到终端
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        logging.getLogger('tftpy').setLevel(logging.INFO)
        logging.getLogger('tftpy').addHandler(logging.StreamHandler())
        logging.getLogger('tftpy').handlers[0].setFormatter(formatter)

        server = tftpy.TftpServer(directory)
        try:
            server.listen(listenip='0.0.0.0', listenport=self.LISTEN_PORT)
        except Exception as e:
            logger.error(f"Server error: {e}")

    def stop_server(self):
        if self.server_process:
            self.server_process.terminate()
            self.server_process.join()
            self.server_process = None
            self.log("TFTP Server stopped")

    def restart_server(self, directory):
        self.stop_server()
        self.start_server(directory)

    def on_path_change(self, event):
        new_path = self.path_var.get()
        if new_path == self.current_directory:
            return
        # self.log(f"Changing working directory to: {new_path}")
        self.restart_server(new_path)
        self.update_history(new_path)
        self.update_path_combo()

    def show_dropdown(self, event):
        self.path_combo.event_generate('<Down>')

    def browse(self):
        directory = filedialog.askdirectory(initialdir=self.current_directory)
        if directory:
            self.current_directory = directory
            self.restart_server(directory)
            self.update_history(directory)
            self.update_path_combo()

    def update_path_combo(self):
        self.path_combo['values'] = list(self.history.keys())
        self.current_directory = self.path_combo['values'][0]
        self.path_combo.set(self.current_directory)

    def log(self, message):
        self.logger.info(message)

    def on_closing(self):
        self.stop_server()
        self.root.destroy()

    def process_log_queue(self):
        while True:
            record = self.log_queue.get()
            self.logger.handle(record)

class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(record)

class TextHandler(logging.Handler):
    def __init__(self, text_widget, root):
        super().__init__()
        self.text_widget = text_widget
        self.root = root

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.yview(tk.END)
        self.root.after(0, append)

if __name__ == "__main__":
    root = tk.Tk()
    app = TFTPServerApp(root)
    root.mainloop()
