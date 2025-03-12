import tkinter as tk
from tkinter import ttk, messagebox
import queue
import concurrent.futures
from network import process_device
from config import save_settings, load_settings
from utils import validate_input


class NetworkToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SSH-Commander by nbaranov.vrn@gmail.com")
        self.running = False
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
        self.result_queue = queue.Queue()
        self.global_log_file = None
        self.create_widgets()
        self.temp_file = load_settings(self)
        self.update_gui()

    def create_widgets(self):
        login_frame = ttk.LabelFrame(self.root, text="Credentials")
        login_frame.pack(padx=10, pady=5, fill="x")

        ttk.Label(login_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5)
        self.username = ttk.Entry(login_frame)
        self.username.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(login_frame, text="Password:").grid(row=1, column=0, padx=5, pady=5)
        self.password = ttk.Entry(login_frame, show="*")
        self.password.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(login_frame, text="Device Type:").grid(
            row=2, column=0, padx=5, pady=5
        )
        self.device_type = ttk.Combobox(login_frame, values=["huawei", "nokia"])
        self.device_type.set("huawei")
        self.device_type.grid(row=2, column=1, padx=5, pady=5)

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

        result_frame = ttk.LabelFrame(self.root, text="Results")
        result_frame.pack(padx=10, pady=5, fill="both", expand=True)
        self.result_text = tk.Text(result_frame, height=10)
        self.result_text.pack(padx=5, pady=5, fill="both", expand=True)

    def start_execution(self):
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
        if not self.running:
            self.running = True
            self.run_button.config(state="disabled")
            self.cancel_button.config(state="normal")
            self.result_text.delete("1.0", "end")
            self.progress["value"] = 0
            self.global_log_file = None
            self.completed_tasks = 0

            username = self.username.get()
            password = self.password.get()
            device_type = self.device_type.get()
            ip_text = self.ip_text.get("1.0", "end-1c")
            cmd_text = self.cmd_text.get("1.0", "end-1c")
            thread_count = int(self.thread_count.get())

            import re

            ip_pattern = r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
            ip_list = list(set(re.findall(ip_pattern, ip_text)))
            commands = [cmd.strip() for cmd in cmd_text.split("\n") if cmd.strip()]
            self.total_devices = len(ip_list)

            self.executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=thread_count
            )
            for ip in ip_list:
                self.executor.submit(
                    process_device,
                    ip,
                    username,
                    password,
                    device_type,
                    commands,
                    self.result_queue,
                    self.running,
                    self.global_log_file,
                )

    def execution_finished(self):
        self.running = False
        self.run_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        messagebox.showinfo("Complete", "Execution finished or cancelled")
        self.global_log_file = None

    def cancel_execution(self):
        self.running = False
        self.executor.shutdown(wait=False)
        self.execution_finished()

    def update_gui(self):
        try:
            while True:
                result = self.result_queue.get_nowait()
                self.result_text.insert("end", result)
                self.result_text.see("end")
                self.progress["value"] += 100 / self.total_devices
        except queue.Empty:
            pass
        self.root.after(100, self.update_gui)

    def on_closing(self):
        self.running = False
        self.executor.shutdown(wait=False)
        self.root.destroy()
