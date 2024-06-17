import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import argparse
import os
import datetime
import time

from DiscoveryConsts import DiscoveryPort
from stdoutputCapture import StdOutputCaptureThread
from fileTransfer import receive_files, report_data_size, start_discovery_listener, RECV_DATA


APP_TITLE = "File Receiver GUI"
recv_thread = None


def is_capture():
    return 1    # set this to enable/disable output capture (set to 0 for debug)


def is_logging():
    return 1    # set this to enable/disable logging


def recv_start(savedir, port, overwrite):
    RECV_DATA["canceled"] = False
    global recv_thread
    recv_thread = threading.Thread(target=receive_files, args=(savedir, port, overwrite))
    recv_thread.start()


def recv_stop():
    RECV_DATA["canceled"] = True
    global recv_thread
    recv_thread.join()


def get_default_download_folder():
    if os.name == 'posix':  # macOS or Linux
        return os.path.expanduser("~/Downloads")
    elif os.name == 'nt':  # Windows
        userprofile = os.environ.get('USERPROFILE')
        if userprofile:
            return os.path.join(userprofile, 'Downloads')
        else:
            print("USERPROFILE environment variable not found.")
            return None


def save_settings(savedir, port,  overwrite):
    settings = {
        "savedir": savedir,
        "port": port,
        "overwrite": overwrite
    }
    with open("recvr.settings", "w") as f:
        for key, value in settings.items():
            f.write(f"{key}={value}\n")


def load_settings():
    settings = {}
    try:
        with open("recvr.settings", "r") as f:
            for line in f:
                key, value = line.strip().split('=')
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                settings[key] = value
    except FileNotFoundError:
        return None, None, None  # File not found, return default values
    return settings.get("savedir"), settings.get("port"), settings.get("overwrite")


class FileReceiverGUI(tk.Tk):
    def __init__(self, savedir, port, overwrite, log_file):
        super().__init__()
        self.savedir = savedir
        self.port = port
        #self.overwrite = overwrite
        RECV_DATA["overwrite"] = overwrite
        self.log_file = log_file

        self.title(APP_TITLE)
        self.geometry("760x350")
        self.auto_updater_running = False
        self.auto_updater_thread = None

        # Set protocol handler for window close event
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.create_widgets()

    def create_widgets(self):
        # Frame to contain the Browse and Clear buttons
        self.button_frame = tk.Frame(self)
        self.button_frame.pack(side=tk.TOP, fill=tk.X, padx=0, pady=3)

        # Browse button
        self.choose_savedir_button = tk.Button(self.button_frame, text="Choose Save Folder", command=self.choose_savedir)
        self.choose_savedir_button.pack(side=tk.LEFT, padx=(10, 0))

        # Open Directory button
        self.open_dir_button = tk.Button(self.button_frame, text="Open Save Folder", command=self.open_directory)
        self.open_dir_button.pack(side=tk.LEFT, padx=(10, 0))

        # Save folder path text
        self.path_text = tk.Label(self.button_frame, text=f"{self.savedir} ", justify=tk.LEFT, anchor="w")
        self.path_text.pack(side=tk.LEFT, padx=(10, 0), pady=0)

        # Overwrite checkbox
        self.overwrite_var = tk.BooleanVar(value=RECV_DATA["overwrite"])
        self.overwrite_checkbox = tk.Checkbutton(self.button_frame, text="Overwrite", variable=self.overwrite_var, command=self.toggle_overwrite)
        self.overwrite_checkbox.pack(side=tk.RIGHT, padx=(10, 0))

        # Scrollable text area
        self.text_frame = tk.Frame(self)
        self.text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0,0))

        self.scrollbar = tk.Scrollbar(self.text_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_area = tk.Text(self.text_frame, width=60, height=15, wrap=tk.WORD, yscrollcommand=self.scrollbar.set)
        self.text_area.pack(fill=tk.BOTH, expand=True)

        self.scrollbar.config(command=self.text_area.yview)

        # Make text area uneditable
        self.text_area.config(state=tk.DISABLED)

        # Stats Label
        self.stats_text = tk.Label(self, text=f"{RECV_DATA['received_files']} files received, {RECV_DATA['failed_files']} failed, {RECV_DATA['rejected_files']} rejected\n{report_data_size(RECV_DATA['data_received'])} received", height=2, justify=tk.LEFT, anchor="w", font=("Helvetica", 10, "bold"))
        self.stats_text.pack(side=tk.LEFT, padx=(10, 0), pady=0)

        # Cler button
        self.clear_button = tk.Button(self, text="  Clear  ", command=self.clear_func)
        self.clear_button.pack(side=tk.RIGHT, padx=30, pady=5)

    def choose_savedir(self):
        old_path = self.savedir
        new_path = filedialog.askdirectory(title="Select Save Directory")
        if not new_path or new_path == old_path:
            return

        recv_stop()
        self.savedir = new_path
        self.path_text.config(text=f"{self.savedir}")
        print(f"[{datetime.datetime.now()}] <<NEW SAVE DIRECTORY SELECTED>>:: {self.savedir}")

        recv_start(self.savedir, self.port, RECV_DATA["overwrite"])

    def open_directory(self, dir=None):
        if not dir:
            # open savedir by default
            if os.path.isdir(self.savedir):
                if os.name == 'posix':  # macOS or Linux
                    os.system(f'open "{self.savedir}"')
                elif os.name == 'nt':  # Windows
                    os.system(f'start "" "{self.savedir}"')
            else:
                messagebox.showerror("Error", "No valid save directory selected")
            return

        if os.path.isdir(dir):
            if os.name == 'posix':  # macOS or Linux
                os.system(f'open "{dir}"')
            elif os.name == 'nt':  # Windows
                os.system(f'start "" "{dir}"')
        else:
            print("Directory does not exist")

    def toggle_overwrite(self):
        RECV_DATA["overwrite"] = self.overwrite_var.get()

    def clear_func(self):
        self.clear_text_area()
        self.reset_stats()

    def reset_stats(self):
        RECV_DATA["received_files"] = 0
        RECV_DATA["rejected_files"] = 0
        RECV_DATA["failed_files"] = 0
        RECV_DATA["data_received"] = 0
        self.update_stats_label()

    def clear_text_area(self):
        # Clear the text area
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)
        self.text_area.config(state=tk.DISABLED)

    def update_stats_label(self):
        self.stats_text.config(text=f"{RECV_DATA['received_files']} files received, {RECV_DATA['failed_files']} failed, {RECV_DATA['rejected_files']} rejected\n{report_data_size(RECV_DATA['data_received'])} received")

    def auto_updater(self):
        if not RECV_DATA["in_progress"]:
            self.update_stats_label()  # update the stats just to be safe / avoid race conditions
            # self.auto_updater_running = False
            return

        if not self.auto_updater_running:
            self.auto_updater_running = True

            while RECV_DATA["in_progress"]:
                self.update_stats_label()
                time.sleep(.3)

            self.auto_updater_running = False

    def add_text(self, text):
        # Add text to the text area
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, text + "\n")
        self.text_area.config(state=tk.DISABLED)
        self.text_area.see(tk.END)  # Scroll to the bottom

    def add_stdtext(self, source, text):
        if text.isspace():
            return
        # Add stdtext to the text area
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, text + "\n")
        self.text_area.config(state=tk.DISABLED)
        self.text_area.see(tk.END)  # Scroll to the bottom

        self.auto_updater_thread = threading.Thread(target=self.auto_updater)
        self.auto_updater_thread.start()

        if self.log_file:
            self.log_file.write(f"{text}\n")

    def on_closing(self):
        save_settings(self.savedir, self.port, RECV_DATA["overwrite"])
        self.destroy()


def main():
    log_file = None
    if is_logging():
        # Open a log file in append mode
        log_file = open("receiver.log", "a", buffering=1)
        log_file.write("\n")

    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--savedir", help="Host to connect to")
    parser.add_argument("--port", type=int, help="Port to connect to")
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files (optional, default is False)')
    args = parser.parse_args()

    saved_dir, saved_port, saved_overwrite = load_settings()

    if not args.savedir:
        args.savedir = saved_dir if saved_dir else get_default_download_folder()
    if not args.port:
        args.port = int(saved_port) if saved_port else 1111
    if not args.overwrite:
        args.overwrite = saved_overwrite if saved_overwrite else False

    app = FileReceiverGUI(args.savedir, args.port, args.overwrite, log_file)

    # Start std out and std error capture
    if is_capture():
        output_capture = StdOutputCaptureThread(app.add_stdtext)
        output_capture.start()

    print(f'[{datetime.datetime.now()}] <<< NEW STARTUP >>>')

    # Start host discovery server
    start_discovery_listener(args.port, DiscoveryPort)

    # Start receiving file handling thread
    recv_start(args.savedir, args.port, args.overwrite)

    # Start main window
    app.mainloop()

    # Stop the receiving thread
    recv_stop()

    # Stop the output capture thread
    if is_capture():
        output_capture.stop()
        output_capture.join()

    if is_logging():
        log_file.close()


if __name__ == "__main__":
    main()
