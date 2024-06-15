import tkinter as tk
from tkinter import filedialog, messagebox
import argparse
import os
import subprocess
from tkinterdnd2 import DND_FILES, TkinterDnD


class FileTransferGUI(TkinterDnD.Tk):
    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.title("File Transfer GUI")
        self.geometry("400x500")

        self.create_widgets()

    def create_widgets(self):
        # Frame to contain the Browse and Clear buttons
        button_frame = tk.Frame(self)
        button_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Browse button
        self.browse_button = tk.Button(button_frame, text="Browse", command=self.browse_files)
        self.browse_button.pack(side=tk.LEFT, padx=(0, 5))

        # Clear button
        self.clear_button = tk.Button(button_frame, text="Clear", command=self.clear_files)
        self.clear_button.pack(side=tk.LEFT)

        # Drop target
        self.drop_target = tk.Label(self, text="Drag and drop files or directories here", bg="lightgray", width=50, height=10)
        self.drop_target.pack(pady=10)
        self.drop_target.drop_target_register(DND_FILES)
        self.drop_target.dnd_bind('<<Drop>>', self.drop)

        # Listbox
        self.file_listbox = tk.Listbox(self, selectmode=tk.MULTIPLE, width=60, height=15)
        self.file_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Send button
        self.send_button = tk.Button(self, text="Send", command=self.send_files)
        self.send_button.pack(side=tk.RIGHT, padx=30, pady=5)


    def browse_files(self):
        filepaths = filedialog.askopenfilenames(title="Select Files or Directories")
        for filepath in filepaths:
            self.file_listbox.insert(tk.END, filepath)

    def drop(self, event):
        filepaths = self.tk.splitlist(event.data)
        for filepath in filepaths:
            self.file_listbox.insert(tk.END, filepath)

    def send_files(self):
        selected_files = self.file_listbox.get(0, tk.END)
        if not selected_files:
            messagebox.showerror("Error", "No files or directories selected")
            return

        for path in selected_files:
            if os.path.isdir(path):
                self.transfer_directory(path)
            else:
                self.transfer_file(path)

        # Clear the listbox after sending files
        self.file_listbox.delete(0, tk.END)

    def clear_files(self):
        self.file_listbox.delete(0, tk.END)

    def transfer_file(self, filepath):
        command = ["python", "fileTransfer.py", "send", "--files", filepath, "--host", self.host, "--port", str(self.port)]
        subprocess.run(command)

    def transfer_directory(self, directory):
        command = ["python", "fileTransfer.py", "send", "--dir", directory, "--host", self.host, "--port", str(self.port)]
        subprocess.run(command)


def main():
    parser = argparse.ArgumentParser(description="File Transfer GUI")
    parser.add_argument("--host", required=True, help="Host to connect to")
    parser.add_argument("--port", type=int, required=True, help="Port to connect to")
    args = parser.parse_args()

    app = FileTransferGUI(args.host, args.port)
    app.mainloop()

if __name__ == "__main__":
    main()
