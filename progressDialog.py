import os
import tkinter as tk
import tkinter.ttk as ttk
from threading import Thread
from fileTransfer import SENT_DATA


def report_data_size(size):
    units = ['bytes', 'kB', 'MB']
    unit_index = 0
    if size == 0:
        return f"0 {units[unit_index]}"
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return f"{size:.2f} {units[unit_index]}"


class FileConflictDialog(tk.Toplevel):
    def __init__(self, parent, file_path, remote_file_size, local_file_size):
        super().__init__(parent)
        self.parent = parent
        x = parent.winfo_x() + 100
        y = parent.winfo_y() + 55

        self.user_choice = None

        self.title("File Conflict")
        #self.geometry("400x150")
        self.resizable(False, False)

        label_text = (f"{file_path} ({report_data_size(remote_file_size)}) already exists on host machine.\n"
                      f"{file_path} ({report_data_size(local_file_size)}) local copy.\n"
                      "\tWhat would you like to do? ")

        label = tk.Label(self, text=label_text, wraplength=380, justify="left")
        label.pack(pady=10, padx=30)

        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)

        overwrite_button = ttk.Button(button_frame, text="Overwrite", command=lambda: self.set_choice('O'))
        overwrite_button.grid(row=0, column=0, padx=5)

        keep_both_button = ttk.Button(button_frame, text="Keep Both", command=lambda: self.set_choice('B'))
        keep_both_button.grid(row=0, column=1, padx=5)

        skip_button = ttk.Button(button_frame, text="Skip", command=lambda: self.set_choice('S'))
        skip_button.grid(row=0, column=2, padx=5)

        self.geometry(f"+{x}+{y}")

    def set_choice(self, choice):
        self.user_choice = choice
        self.destroy()


class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, filepaths, totalcount, totalsize, host, port, send_file, send_dir):
        super().__init__(parent)
        self.parent = parent
        x = parent.winfo_x() + 185
        y = parent.winfo_y() + 185
        self.filepaths = filepaths
        self.totalsize = totalsize
        self.totalsize_readable = report_data_size(self.totalsize)
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

        # Frame to contain the transfer stats
        self.stats_frame = tk.Frame(self)
        self.stats_frame.pack(fill=tk.X, padx=20, pady=3)

        self.files_label = tk.Label(self.stats_frame, text=f"files: {SENT_DATA['processed_files']}/{self.filecount}")
        self.files_label.pack(side=tk.LEFT)

        self.data_label = tk.Label(self.stats_frame, text=f"{report_data_size(SENT_DATA['bytesSent'])} / {self.totalsize_readable}")
        self.data_label.pack(side=tk.RIGHT)

        self.cancel_button = tk.Button(self, text="Cancel", command=self.cancel_transfer)
        self.cancel_button.pack(pady=10)

        self.transfer_thread = Thread(target=self.perform_transfer)
        self.transfer_thread.start()

        self.geometry(f"+{x}+{y}")

        self.update_progress()

    def update_progress(self):
        if SENT_DATA["gui_response"] == "NEEDED":
            (file_name, remote_size, local_size) = SENT_DATA["file_info"]
            while SENT_DATA["gui_response"] not in ['O', 'B', 'S']:
                user_prompt = FileConflictDialog(self, file_name, remote_size, local_size)
                user_prompt.grab_set()  # Make the popup modal
                user_prompt.wait_window()
                SENT_DATA["gui_response"] = user_prompt.user_choice

        self.prog_metric1 = (SENT_DATA["processed_files"] / (self.filecount-(1* self.filecount > 1))) * 100
        self.prog_metric2 = (SENT_DATA["bytesSent"] / self.totalsize) * 100
        max_metric = max(self.prog_metric1, self.prog_metric2)
        self.progress = (self.prog_metric1 + self.prog_metric2)/2 if max_metric < 90 else max_metric

        self.progressbar["value"] = self.progress
        self.files_label["text"] = f"files: {SENT_DATA['processed_files']}/{self.filecount}"
        self.data_label["text"] = f"{report_data_size(SENT_DATA['bytesSent'])} / {self.totalsize_readable}"
        self.after(100, self.update_progress)

    def perform_transfer(self):
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
        SENT_DATA["failed_files"] += self.filecount - (SENT_DATA["processed_files"] + 1)  # fail the rest of the files in list
