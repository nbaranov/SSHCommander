import tkinter as tk
from tkinter import ttk, messagebox
import queue
import concurrent.futures
from network import process_device
from config import save_settings, load_settings
from utils import validate_input
from datetime import datetime
import os
import re
import threading
import subprocess
import platform


class NetworkToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SSH-Commander by nbaranov.vrn@gmail.com")
        self.running_event = threading.Event()
        self.running_event.clear()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
        self.result_queue = queue.Queue()
        self.futures = []
        self.create_widgets()
        self.temp_file = load_settings(self)
        self.update_gui()
        self.lock = threading.Lock()

    def create_widgets(self):
        login_frame = ttk.LabelFrame(self.root, text="Credentials")
        login_frame.pack(padx=10, pady=5, fill="x")

        login_frame.grid_columnconfigure(0, weight=1)  # Пустой столбец слева
        login_frame.grid_columnconfigure(4, weight=1)  # Пустой столбец справа

        # Метки и поля ввода
        ttk.Label(login_frame, text="Username:").grid(
            row=0, column=1, padx=5, pady=5, sticky="w"
        )
        self.username = ttk.Entry(login_frame)
        self.username.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(login_frame, text="Password:").grid(
            row=0, column=2, padx=5, pady=5, sticky="w"
        )
        self.password = ttk.Entry(login_frame, show="*")
        self.password.grid(row=1, column=2, padx=5, pady=5, sticky="w")

        ttk.Label(login_frame, text="Device Type:").grid(
            row=0, column=3, padx=5, pady=5, sticky="w"
        )
        self.device_type = ttk.Combobox(login_frame, values=["huawei", "nokia_sros"])
        self.device_type.set("huawei")
        self.device_type.grid(row=1, column=3, padx=5, pady=5, sticky="w")

        ip_frame = ttk.LabelFrame(self.root, text="IP Addresses")
        ip_frame.pack(padx=10, pady=5, fill="both")
        self.ip_text = tk.Text(ip_frame, height=5)
        self.ip_text.pack(padx=5, pady=5, fill="both")
        self.ip_text.bind(
            "<Control-a>", lambda e: self.ip_text.tag_add("sel", "1.0", "end")
        )

        cmd_frame = ttk.LabelFrame(self.root, text="Commands")
        cmd_frame.pack(padx=10, pady=5, fill="both")
        self.cmd_text = tk.Text(cmd_frame, height=5)
        self.cmd_text.pack(padx=5, pady=5, fill="both")
        self.cmd_text.bind(
            "<Control-a>", lambda e: self.cmd_text.tag_add("sel", "1.0", "end")
        )

        control_frame = ttk.Frame(self.root)
        control_frame.pack(padx=10, pady=5, fill="x")
        ttk.Label(control_frame, text="Concurrent connections:").pack(
            side="left", padx=5
        )
        self.thread_count = ttk.Spinbox(control_frame, from_=1, to=50, width=5)
        self.thread_count.set(20)
        self.thread_count.pack(side="left", padx=5)

        self.progress = ttk.Progressbar(control_frame, length=200)
        self.progress.pack(side="left", padx=5, fill="x", expand=True)

        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)
        self.run_button = ttk.Button(
            button_frame, text="Run", command=self.start_execution
        )
        self.run_button.pack(side="left", padx=5)
        self.cancel_button = ttk.Button(
            button_frame, text="Cancel", command=self.cancel_execution, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=5)

        self.logs_button = ttk.Button(
            button_frame, text="Open Logs", command=self.open_logs_folder
        )
        self.logs_button.pack(side="left", padx=5)

        result_frame = ttk.LabelFrame(self.root, text="Results")
        result_frame.pack(padx=10, pady=5, fill="both", expand=True)
        self.result_text = tk.Text(result_frame, height=10)
        self.result_text.pack(padx=5, pady=5, fill="both", expand=True)

    def start_execution(self):
        self.failed_devices = []
        validation_error = validate_input(
            self.username.get(),
            self.password.get(),
            self.ip_text.get("1.0", "end-1c"),
            self.cmd_text.get("1.0", "end-1c"),
        )
        if validation_error:
            messagebox.showerror("Validation Error", validation_error)
            return

        save_settings(self)
        if not self.running_event.is_set():
            self.running_event.set()
            self.run_button.config(state="disabled")
            self.cancel_button.config(state="normal")
            self.result_text.delete("1.0", "end")
            self.progress["value"] = 0
            self.completed_tasks = 0

            # Создаём подпапку с таймстампом
            timestamp = datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
            self.log_dir = f"device_logs/{timestamp}"
            os.makedirs(self.log_dir, exist_ok=True)
            self.all_devices_log = f"{self.log_dir}/_all_devices_log.log"
            self.failed_log_file = f"{self.log_dir}/_failed_connections.csv"

            # Создаём заголовок для CSV-файла
            with open(self.failed_log_file, "w") as f_failed:
                f_failed.write("IP,Reason\n")

            username = self.username.get()
            password = self.password.get()
            device_type = self.device_type.get()
            ip_text = self.ip_text.get("1.0", "end-1c")
            cmd_text = self.cmd_text.get("1.0", "end-1c")
            thread_count = int(self.thread_count.get())

            ip_pattern = r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
            ip_list = [ip.strip() for ip in re.findall(ip_pattern, ip_text)]
            ip_list = list(filter(None, ip_list))
            ip_list = list(set(ip_list))
            commands = [cmd.strip() for cmd in cmd_text.split("\n") if cmd.strip()]
            self.total_devices = len(ip_list)

            self.futures = []
            self.executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=thread_count
            )
            for ip in ip_list:
                future = self.executor.submit(
                    process_device,
                    ip,
                    username,
                    password,
                    device_type,
                    commands,
                    self.result_queue,
                    self.running_event,
                    self.log_dir,
                    self.all_devices_log,
                    self.failed_devices,
                    self.lock,
                )
                self.futures.append(future)

    def update_gui(self):
        try:
            while True:
                result = self.result_queue.get_nowait()
                self.result_text.insert("end", result)
                self.result_text.see("end")
                if "Success" in result or "Error" in result:
                    self.completed_tasks += 1
                    self.progress["value"] = (
                        self.completed_tasks / self.total_devices
                    ) * 100
        except queue.Empty:
            pass
        if (
            hasattr(self, "futures")
            and self.running_event.is_set()
            and all(future.done() for future in self.futures)
        ):
            self.execution_finished()

        self.root.after(100, self.update_gui)

    def execution_finished(self):
        self.running_event.clear()
        if hasattr(self, "futures") and self.futures:
            done, not_done = concurrent.futures.wait(self.futures)
            print(f"Completed tasks: {len(done)}, Pending tasks: {len(not_done)}")
        self.executor.shutdown(wait=True)
        self.run_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        self.result_queue.put("Execution finished")
        messagebox.showinfo("Complete", "Execution finished")

        if self.failed_devices:
            failed_log_file = f"{self.log_dir}/_failed_connections.csv"
            with open(failed_log_file, "w", newline="") as f_failed:
                f_failed.write("IP,Reason\n")
                for ip, reason in self.failed_devices:
                    f_failed.write(f"{ip},{reason}\n")

    def execution_canceled(self):
        self.run_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        self.result_queue.put(f"Execution cancelled")
        messagebox.showinfo("Cancel", "Execution cancelled")

    def cancel_execution(self):
        self.running_event.clear()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.execution_canceled()

    def on_closing(self):
        self.running_event.clear()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()

    def open_logs_folder(self):
        logs_dir = os.path.abspath("device_logs")

        if not os.path.exists(logs_dir):
            try:
                os.makedirs(logs_dir, exist_ok=True)
                messagebox.showinfo("Info", f"Logs directory created: {logs_dir}")
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to create logs directory: {str(e)}"
                )
                return

        try:
            os_name = platform.system()
            if os_name == "Windows":
                os.startfile(logs_dir)  # Для Windows
            elif os_name == "Darwin":  # macOS
                subprocess.run(["open", logs_dir])
            elif os_name == "Linux":
                subprocess.run(["xdg-open", logs_dir])
            else:
                messagebox.showerror("Error", f"Unsupported OS: {os_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open logs directory: {str(e)}")
