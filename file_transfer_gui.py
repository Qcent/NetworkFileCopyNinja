import tkinter as tk
from tkinter import filedialog, messagebox
import argparse
import os
import sys
import subprocess
from tkinterdnd2 import DND_FILES, TkinterDnD

from discoverHosts import discover_and_list_hosts

APP_TITLE = "File Transfer GUI"
SelectedHost = {
    "port": None,
    "ip": None
}


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

        if not host:
            self.title(APP_TITLE)
        else:
            self.title(f"{APP_TITLE} --> {host}")

        if sys.platform.startswith('win'):
            # Windows
            self.geometry("400x500")
            self.pyCommand = "python"
        elif sys.platform.startswith('darwin'):
            # Mac OS
            self.geometry("400x550")
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
        self.label_text = tk.Label(self, text="0 items\n ", width=30, height=2, justify=tk.LEFT, anchor="w", font=("Helvetica", 10, "bold"))
        self.label_text.pack(side=tk.LEFT, padx=(10, 0), pady=0)

        # Send button
        self.send_button = tk.Button(self, text="  Send  ", command=self.send_files)
        self.send_button.pack(side=tk.RIGHT, padx=30, pady=5)

    def browse_files(self):
        filepaths = filedialog.askopenfilenames(title="Select Files or Directories")
        for filepath in filepaths:
            if filepath not in self.file_listbox.get(0, tk.END):
                self.file_listbox.insert(tk.END, filepath)
        self.update_items_label()

    def drop(self, event):
        filepaths = self.tk.splitlist(event.data)
        for filepath in filepaths:
            if filepath not in self.file_listbox.get(0, tk.END):
                self.file_listbox.insert(tk.END, filepath)
        self.update_items_label()

    def send_files(self):
        global SelectedHost
        if SelectedHost['ip'] and self.host is not SelectedHost['ip']:
            self.host = SelectedHost['ip']
        if SelectedHost['port'] and self.port is not SelectedHost['port']:
            self.port = SelectedHost['port']

        selected_files = self.file_listbox.get(0, tk.END)

        if not selected_files:
            messagebox.showerror("Error", "No files or directories selected")
            return

        num_items = self.file_listbox.size()
        self.failed_files.clear()  # Clear the list of failed files

        for path in selected_files:
            if path.startswith("❌"):  # Check if path starts with ❌ (previously failed to send)
                path = path[1:]  # Remove ❌
            if os.path.isdir(path):
                if not self.transfer_directory(path):
                    self.failed_files.append(path)  # Add failed directory to list
            else:
                if not self.transfer_file(path):
                    self.failed_files.append(path)  # Add failed file to list

        # Clear the listbox after sending files
        self.file_listbox.delete(0, tk.END)

        # Add failed files to listbox
        for path in self.failed_files:
            self.file_listbox.insert(tk.END, f"❌{path}")

        # Update info label
        num_fails = len(self.failed_files)
        num_success = num_items - num_fails
        if num_fails:
            self.label_text.config(text=f"Failed to send {num_fails} items\nSuccessfully sent {num_success} items")
        else:
            self.label_text.config(text=f"Successfully sent {num_success} items\n ")

    def transfer_file(self, filepath):
        command = [self.pyCommand, "fileTransfer.py", "send", "--files", filepath, "--host", self.host, "--port", str(self.port)]
        result = subprocess.run(command)
        return result.returncode == 0  # Check if command was successful

    def transfer_directory(self, directory):
        command = [self.pyCommand, "fileTransfer.py", "send", "--dir", directory, "--host", self.host, "--port", str(self.port)]
        result = subprocess.run(command)
        return result.returncode == 0  # Check if command was successful

    def clear_files(self):
        self.file_listbox.delete(0, tk.END)
        self.update_items_label()

    def update_items_label(self):
        num_items = self.file_listbox.size()
        self.label_text.config(text=f"{num_items} items\n ")


def main():
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--host", help="Host to connect to")
    parser.add_argument("--port", type=int, help="Port to connect to")
    args = parser.parse_args()

    if not args.host:
        args.host = "127.0.0.1"
    if not args.port:
        args.port = "1111"

    app = FileTransferGUI(args.host, args.port)

    def show_host_list():
        popup = HostListPopup(app, discover_and_list_hosts())
        popup.grab_set()  # Make the popup modal
        popup.wait_window()

    button = tk.Button(app.button_frame, text="Search Hosts", command=show_host_list)
    button.pack(side=tk.TOP, padx=(10, 0))

    app.mainloop()


if __name__ == "__main__":
    main()
