import tkinter as tk
from tkinter import filedialog, messagebox
import argparse
import os
import sys
import datetime
from tkinterdnd2 import DND_FILES, TkinterDnD

from discoverHosts import discover_and_list_hosts
from fileTransfer import SENT_DATA, send_file
from progressDialog import ProgressDialog

APP_TITLE = "File Transfer GUI"
SelectedHost = {
    "port": None,
    "ip": None,
}


def is_logging():
    return 0    # set this to enable/disable logging


class HostListPopup(tk.Toplevel):
    def __init__(self, parent, host_list):
        super().__init__(parent)
        self.title("Discovered Hosts")
        self.geometry("300x150")

        self.parent = parent
        self.host_list = host_list

        self.create_widgets()

    def create_widgets(self):
        self.listbox = tk.Listbox(self)
        self.listbox.pack(fill=tk.BOTH, expand=True)

        # Add hosts to the listbox
        for host in self.host_list:
            self.listbox.insert(tk.END, f"  {host[0]}   :   {host[1]}   :   {host[2]}")

        # Bind double click event to set title
        self.listbox.bind("<Double-Button-1>", self.select_host)

    def select_host(self, event):
        index = self.listbox.curselection()[0]
        selected_host = self.host_list[index]
        self.parent.title(f"{APP_TITLE} --> {selected_host[0]}")
        global SelectedHost
        SelectedHost["ip"] = selected_host[1]
        SelectedHost["port"] = selected_host[2]
        self.destroy()


class FileTransferGUI(TkinterDnD.Tk):
    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.total_file_size = 0
        self.total_file_count = 0

        if not host:
            self.title(APP_TITLE)
        else:
            self.title(f"{APP_TITLE} --> {host}")

        if sys.platform.startswith('win'):
            # Windows
            self.geometry("420x505")
            self.pyCommand = "python"
        elif sys.platform.startswith('darwin'):
            # Mac OS
            self.geometry("420x550")
            self.pyCommand = "python3"

        self.failed_files = []  # List to store paths of failed files
        self.create_widgets()

    def create_widgets(self):
        # Frame to contain the Browse and Clear buttons
        self.button_frame = tk.Frame(self)
        self.button_frame.pack(side=tk.TOP, fill=tk.X, padx=0, pady=3)

        # Browse button
        self.browse_button = tk.Button(self.button_frame, text="Browse", command=self.browse_files)
        self.browse_button.pack(side=tk.LEFT, padx=(10, 0))

        # Clear button
        self.clear_button = tk.Button(self.button_frame, text="Clear", command=self.clear_files)
        self.clear_button.pack(side=tk.RIGHT, padx=10, pady=0)

        # Drop target
        self.drop_target = tk.Label(self, text="Drag and drop files or directories here", bg="lightgray", width=60, height=10)
        self.drop_target.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0,5))
        self.drop_target.drop_target_register(DND_FILES)
        self.drop_target.dnd_bind('<<Drop>>', self.drop)

        # Listbox
        self.file_listbox = tk.Listbox(self, selectmode=tk.MULTIPLE, width=60, height=15)
        self.file_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0,0))

        # Label
        self.label_text = tk.Label(self, text="0 files\n ", height=2, justify=tk.LEFT, anchor="w", font=("Helvetica", 10, "bold"))
        self.label_text.pack(side=tk.LEFT, padx=(10, 0), pady=0)

        # Send button
        self.send_button = tk.Button(self, text="  Send  ", command=self.send_files)
        self.send_button.pack(side=tk.RIGHT, padx=30, pady=5)

    def browse_files(self):
        filepaths = filedialog.askopenfilenames(title="Select Files or Directories")
        for filepath in filepaths:
            if filepath not in self.file_listbox.get(0, tk.END):
                self.file_listbox.insert(tk.END, filepath)
                self.total_file_size += self.get_file_size(filepath)
        self.update_items_label()

    def drop(self, event):
        filepaths = self.tk.splitlist(event.data)
        for filepath in filepaths:
            filepath_fail = f"❌{filepath}"
            if (filepath not in self.file_listbox.get(0, tk.END) and
                    filepath_fail not in self.file_listbox.get(0, tk.END)):
                self.file_listbox.insert(tk.END, filepath)
                self.total_file_size += self.get_file_size(filepath)
        self.update_items_label()

    def failed_file_redrop(self, filepath):
        self.file_listbox.insert(tk.END, f"❌{filepath}")
        self.total_file_size += self.get_file_size(filepath)

    def send_files(self):
        global SelectedHost
        if SelectedHost['ip'] and self.host is not SelectedHost['ip']:
            self.host = SelectedHost['ip']
        if SelectedHost['port'] and self.port is not int(SelectedHost['port']):
            self.port = int(SelectedHost['port'])

        # Reset all SEND_DATA
        SENT_DATA['bytesSent'] = 0
        SENT_DATA['failed_files'] = 0
        SENT_DATA['processed_files'] = 0
        SENT_DATA["canceled"] = False

        selected_files = self.file_listbox.get(0, tk.END)

        if not selected_files:
            messagebox.showerror("Error", "No files or directories selected")
            return

        num_items = self.total_file_count
        self.failed_files.clear()

        tranferWindow = ProgressDialog(None, selected_files, self.total_file_count, self.total_file_size, self.host, self.port, self.transfer_file, self.transfer_directory)
        tranferWindow.grab_set()  # Make the popup modal
        tranferWindow.wait_window()

        self.failed_files = tranferWindow.failed_files

        '''
        # Send the list of files
        for path in selected_files:
            if path.startswith("❌"):  # Check if path starts with ❌ (previously failed to send)
                path = path[1:]  # Remove ❌ from path
            if os.path.isdir(path):
                if not self.transfer_directory(path):
                    self.failed_files.append(path)  # Add failed directory to list
            else:
                if not self.transfer_file(path):
                    self.failed_files.append(path)  # Add failed file to list   
        '''

        # Update info label
        num_fails = SENT_DATA["failed_files"]
        num_success = num_items - num_fails
        if num_fails:
            self.label_text.config(text=f"Failed to send {num_fails} files ({self.report_total_file_size(self.total_file_size-SENT_DATA['bytesSent'])})\nSuccessfully sent {num_success} files ({self.report_total_file_size(SENT_DATA['bytesSent'])})")
        else:
            self.label_text.config(text=f"Successfully sent {num_success} files ({self.report_total_file_size(SENT_DATA['bytesSent'])})\n ")

        # Clear the listbox after sending files
        self.file_listbox.delete(0, tk.END)
        self.total_file_size = 0
        self.total_file_count = 0

        # Add failed files to listbox
        for path in self.failed_files:
            self.failed_file_redrop(path)

    def transfer_file(self, filepath):
        return send_file(filepath, os.path.dirname(filepath), '', self.host, self.port)

    def transfer_directory(self, directory):
        success = True
        base_dir = os.path.basename(directory)
        for root, _, files in os.walk(directory):
            for file in files:
                full_path = os.path.join(root, file)
                if not send_file(full_path, directory, base_dir, self.host, self.port):
                    success = False
        return success

    def clear_files(self):
        self.file_listbox.delete(0, tk.END)
        self.total_file_size = 0
        self.total_file_count = 0
        self.update_items_label()

    def update_items_label(self):
        num_items = self.total_file_count
        if self.total_file_size:
            self.label_text.config(text=f"{num_items} files ({self.report_total_file_size()})\n ")
        else:
            self.label_text.config(text=f"{num_items} files\n ")

    def get_file_size(self, path):
        total_size = 0
        if os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
                    self.total_file_count += 1
        else:
            total_size += os.path.getsize(path)
            self.total_file_count += 1
        return total_size

    def report_total_file_size(self, size=None):
        units = ['bytes', 'kB', 'MB', 'GB', 'TB']
        unit_index = 0
        if size is None:
            size = self.total_file_size

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        return f"{size:.2f} {units[unit_index]}"


def main():
    if is_logging():
        # Open a log file in append mode
        log_file = open("send.log", "a")

        # Redirect stdout and stderr to the log file
        sys.stdout = log_file
        sys.stderr = log_file

        print(f'[{datetime.datetime.now()}] <<< NEW SESSION >>>')

    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--host", help="Host to connect to")
    parser.add_argument("--port", type=int, help="Port to connect to")
    args = parser.parse_args()

    if not args.host:
        args.host = "127.0.0.1"
    if not args.port:
        args.port = 1111

    app = FileTransferGUI(args.host, args.port)

    def show_host_list():
        popup = HostListPopup(app, discover_and_list_hosts())
        popup.grab_set()  # Make the popup modal
        popup.wait_window()

    button = tk.Button(app.button_frame, text="Search Hosts", command=show_host_list)
    button.pack(side=tk.TOP, padx=(10, 0))

    app.mainloop()

    if is_logging():
        log_file.close()


if __name__ == "__main__":
    main()
