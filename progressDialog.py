import os
import tkinter as tk
import tkinter.ttk as ttk
from threading import Thread
from fileTransfer import SENT_DATA


class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, filepaths, totalcount, totalsize, host, port, send_file, send_dir):
        super().__init__(parent)
        self.parent = parent
        self.filepaths = filepaths
        self.totalsize = totalsize
        self.filecount = totalcount
        self.host = host
        self.port = port
        self.send_file_func = send_file
        self.send_dir_func = send_dir
        self.failed_files = []

        self.progress = 0
        self.prog_metric1 = 0
        self.prog_metric2 = 0
        self.cancelled = False

        self.title("File Transfer Progress")

        self.progressbar = ttk.Progressbar(self, orient="horizontal", length=200, mode="determinate")
        self.progressbar.pack(pady=10, padx=40)

        self.bytes_label = tk.Label(self, text="Bytes Sent: 0")
        self.bytes_label.pack()

        self.total_bytes_label = tk.Label(self, text="Total Bytes: Calculating...")
        self.total_bytes_label.pack()

        self.cancel_button = tk.Button(self, text="Cancel", command=self.cancel_transfer)
        self.cancel_button.pack(pady=10)

        self.transfer_thread = Thread(target=self.perform_transfer)
        self.transfer_thread.start()

        self.update_progress()

    def update_progress(self):
        if SENT_DATA["processed_files"]:
            self.prog_metric1 = (SENT_DATA["processed_files"] / self.filecount) * 100
        if SENT_DATA["bytesSent"]:
            self.prog_metric2 = (SENT_DATA["bytesSent"] / self.totalsize) * 100

        self.progress = max(self.prog_metric1, self.prog_metric2)

        self.progressbar["value"] = self.progress
        self.bytes_label["text"] = f"Bytes Sent: {SENT_DATA['bytesSent']}"
        self.after(100, self.update_progress)

    def perform_transfer(self):
        self.total_bytes_label["text"] = f"Total Bytes: {self.totalsize}"
        failed_files = []
        # Send the list of files
        for path in self.filepaths:
            if path.startswith("❌"):  # Check if path starts with ❌ (previously failed to send)
                path = path[1:]  # Remove ❌ from path

            if self.cancelled:
                failed_files.append(path)
                continue

            if os.path.isdir(path):
                if not self.send_dir_func(path):
                    failed_files.append(path)  # Add failed directory to list
            else:
                if not self.send_file_func(path):
                    failed_files.append(path)  # Add failed file to list

        self.failed_files = failed_files
        self.destroy()

    def cancel_transfer(self):
        self.cancelled = True
        SENT_DATA["canceled"] = True
