import os
import tkinter as tk
import tkinter.ttk as ttk
from threading import Thread
from fileTransfer import SENT_DATA


def report_data_size(size):
    units = ['bytes', 'kB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(size)
    if size == 0:
        return f"0 {units[0]}"
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    return f"{size:.2f} {units[unit_index]}"


class FileConflictDialog(tk.Toplevel):
    def __init__(self, parent, file_path, remote_file_size, local_file_size):
        super().__init__(parent)
        self.parent = parent
        self.user_choice = None

        # Position relative to parent
        x = parent.winfo_x() + 100
        y = parent.winfo_y() + 55
        self.geometry(f"+{x}+{y}")

        self.title("File Conflict")
        self.resizable(False, False)
        self.transient(parent)  # keep on top of parent

        label_text = (
            f"{file_path} ({report_data_size(remote_file_size)}) already exists on host machine.\n"
            f"{file_path} ({report_data_size(local_file_size)}) local copy.\n"
            "What would you like to do?"
        )

        label = tk.Label(self, text=label_text, wraplength=380, justify="left")
        label.pack(pady=10, padx=30)

        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)

        overwrite_button = ttk.Button(
            button_frame, text="Overwrite", command=lambda: self.set_choice('O')
        )
        overwrite_button.grid(row=0, column=0, padx=5)

        keep_both_button = ttk.Button(
            button_frame, text="Keep Both", command=lambda: self.set_choice('B')
        )
        keep_both_button.grid(row=0, column=1, padx=5)

        skip_button = ttk.Button(
            button_frame, text="Skip", command=lambda: self.set_choice('S')
        )
        skip_button.grid(row=0, column=2, padx=5)

        # Bind Esc to Skip for convenience
        self.bind("<Escape>", lambda e: self.set_choice('S'))

    def set_choice(self, choice):
        self.user_choice = choice
        self.destroy()


class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, filepaths, totalcount, totalsize, host, port, send_file, send_dir):
        super().__init__(parent)
        self.parent = parent

        # Position relative to parent
        x = parent.winfo_x() + 185
        y = parent.winfo_y() + 185
        self.geometry(f"+{x}+{y}")

        # Data / dependencies
        self.filepaths = filepaths
        self.totalsize = totalsize
        self.totalsize_readable = report_data_size(self.totalsize)
        self.filecount = totalcount
        self.host = host
        self.port = port
        self.send_file_func = send_file
        self.send_dir_func = send_dir
        self.failed_files = []

        self.progress = 0.0
        self.prog_metric1 = 0.0
        self.prog_metric2 = 0.0
        self.cancelled = False

        self.title("File Transfer Progress")
        self.resizable(False, False)
        self.transient(parent)

        # Widgets
        self.progressbar = ttk.Progressbar(
            self, orient="horizontal", length=200, mode="determinate"
        )
        self.progressbar.pack(pady=10, padx=40)

        # Stats frame
        self.stats_frame = tk.Frame(self)
        self.stats_frame.pack(fill=tk.X, padx=20, pady=3)

        self.files_label = tk.Label(
            self.stats_frame,
            text=f"files: {SENT_DATA['processed_files']}/{self.filecount}"
        )
        self.files_label.pack(side=tk.LEFT)

        self.data_label = tk.Label(
            self.stats_frame,
            text=f"{report_data_size(SENT_DATA['bytesSent'])} / {self.totalsize_readable}"
        )
        self.data_label.pack(side=tk.RIGHT)

        self.cancel_button = tk.Button(self, text="Cancel", command=self.cancel_transfer)
        self.cancel_button.pack(pady=10)

        # Background transfer thread
        self.transfer_thread = Thread(target=self.perform_transfer, daemon=True)
        self.transfer_thread.start()

        # Start periodic progress updates
        self._closed = False
        self.after(100, self.update_progress)

    def show_file_conflict_dialog_if_needed(self):
        """
        If SENT_DATA["gui_response"] == "NEEDED", show the conflict dialog once,
        and set SENT_DATA["gui_response"] to 'O', 'B', or 'S'.
        """
        if SENT_DATA.get("gui_response") == "NEEDED":
            file_name, remote_size, local_size = SENT_DATA["file_info"]

            dlg = FileConflictDialog(self, file_name, remote_size, local_size)
            dlg.grab_set()
            dlg.wait_window()

            # Default to 'S' (skip) if user closed the dialog without picking
            choice = dlg.user_choice or 'S'
            SENT_DATA["gui_response"] = choice

    def update_progress(self):
        # Stop if this window has been destroyed
        if self._closed or not self.winfo_exists():
            return

        # Handle conflict dialog if needed (runs on main Tk thread)
        self.show_file_conflict_dialog_if_needed()

        # Compute progress:
        # metric1 = files completed; metric2 = bytes sent
        if self.filecount > 0:
            self.prog_metric1 = (SENT_DATA["processed_files"] / self.filecount) * 100
        else:
            self.prog_metric1 = 100.0

        if self.totalsize > 0:
            self.prog_metric2 = (SENT_DATA["bytesSent"] / self.totalsize) * 100
        else:
            self.prog_metric2 = 100.0

        # Combine in a slightly “optimistic” way until near the end
        max_metric = max(self.prog_metric1, self.prog_metric2)
        if max_metric < 90:
            self.progress = (self.prog_metric1 + self.prog_metric2) / 2.0
        else:
            self.progress = max_metric

        # Clamp to [0, 100]
        self.progress = max(0.0, min(100.0, self.progress))

        # Update UI
        self.progressbar["value"] = self.progress
        self.files_label["text"] = f"files: {SENT_DATA['processed_files']}/{self.filecount}"
        self.data_label["text"] = (
            f"{report_data_size(SENT_DATA['bytesSent'])} / {self.totalsize_readable}"
        )

        # Schedule next tick
        self.after(100, self.update_progress)

    def perform_transfer(self):
        """
        Worker thread: performs the actual sending of files/directories.
        No direct Tk calls here; any UI updates must go through `after`.
        """
        failed_files = []

        for path in self.filepaths:
            # Strip the ❌ prefix if present (failed previously)
            if path.startswith("❌"):
                path = path[1:]

            if self.cancelled:
                failed_files.append(path)
                continue

            # Directory vs file
            if os.path.isdir(path):
                ok = self.send_dir_func(path)
            else:
                ok = self.send_file_func(path)

            if not ok:
                failed_files.append(path)

        self.failed_files = failed_files

        # Close the dialog on the main Tk thread
        def close_dialog():
            if not self._closed and self.winfo_exists():
                self._closed = True
                self.destroy()

        try:
            self.after(0, close_dialog)
        except tk.TclError:
            # Window may already be gone; ignore
            pass

    def cancel_transfer(self):
        self.cancelled = True
        SENT_DATA["canceled"] = True

        # Remaining files (approximate): those not processed yet.
        remaining = max(0, self.filecount - SENT_DATA.get("processed_files", 0))
        # Let the core transfer logic adjust SENT_DATA["failed_files"] per-file;
        # if you *want* to mark all remaining as failed immediately, uncomment:
        # SENT_DATA["failed_files"] += remaining

        # Button can be disabled to prevent multiple clicks
        self.cancel_button.config(state=tk.DISABLED)
