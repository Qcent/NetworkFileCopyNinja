# NetworkFileCopyNinja

NetworkFileCopyNinja is a Python-based tool designed to simplify file transfer between hosts (Windows, macOS, Linux) on a network when traditional methods such as Windows networking, FTP, or other protocols fail to deliver. The project includes a suite of tools with graphical user interfaces (GUIs) to facilitate seamless file sharing across different operating systems.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Tool 1: Command-Line File Sender and Receiver](#tool-1-command-line-file-sender-and-receiver)
  - [Tool 2: File Transfer GUI](#tool-2-file-transfer-gui)
- [Requirements](#requirements)
- [Screenshots](#screenshots)
- [Contributing](#contributing)
- [License](#license)

## Features

- Easy file transfer across Windows, macOS, and Linux.
- Supports both file and directory transfer.
- Maintains directory structure during transfer.
- Reliable performance even when traditional methods fail.

## Installation

To get started with NetworkFileCopyNinja, clone the repository and install the required dependencies.

```bash
git clone https://github.com/yourusername/NetworkFileCopyNinja.git
cd NetworkFileCopyNinja
pip install -r requirements.txt
```

## Usage

### Tool 1: File Sender and Receiver

The File Sender and Receiver tool allows you to send and receive files or directories over a network.

#### Requirements

- Ensure Python is installed on your system.
- Install the required dependencies listed in `requirements.txt`.

## Usage

### Tool 1: Command-Line File Sender and Receiver

The Command-Line File Sender and Receiver tool allows you to send and receive files or directories over a network using simple command-line commands.

#### Requirements

- Ensure Python is installed on your system.
- Install the required dependencies listed in `requirements.txt`.

#### Usage

1. **Sending Files/Directories:**

    To send files or directories, use the `send` mode. You need to specify the host and port to connect to. You can either send individual files or an entire directory.

    ```bash
    python file_transfer.py send --files file1.txt file2.txt --host <receiver_host> --port <port>
    ```

    Or to send a directory:

    ```bash
    python file_transfer.py send --dir /path/to/directory --host <receiver_host> --port <port>
    ```

    Example:

    ```bash
    python file_transfer.py send --dir /home/user/documents --host 192.168.1.2 --port 5001
    ```


2. **Receiving Files:**

    To receive files, use the `receive` mode. You need to specify the port to listen on and the directory to save the received files.

    ```bash
    python file_transfer.py receive --savedir /path/to/save --port <port>
    ```

    Example:

    ```bash
    python file_transfer.py receive --savedir /home/user/downloads --port 5001
    ```


### Tool 2: File Transfer GUI

The File Transfer GUI provides a graphical interface for sending files or directories over a network.

#### Requirements

- Ensure Python is installed on your system.
- Install the required dependencies listed in `requirements.txt`.
- Install `tkinterdnd2` for drag-and-drop support: 

    ```bash
    pip install tkinterdnd2
    ```

#### Usage

1. **Launching the GUI:**

    To launch the GUI, you need to specify the host and port to connect to.

    ```bash
    python file_transfer_gui.py --host <receiver_host> --port <port>
    ```

    Example:

    ```bash
    python file_transfer_gui.py --host 192.168.1.2 --port 5001
    ```

    ![File Transfer GUI Screenshot](path/to/your/screenshot1.png)

2. **Using the GUI:**

    - **Browse Files:** Click the "Browse" button to select files or directories to send.
    - **Drag and Drop:** Drag and drop files or directories into the specified area.
    - **Clear Files:** Click the "Clear" button to remove all selected files from the list.
    - **Send Files:** Click the "Send" button to transfer the selected files or directories to the specified host and port.

## Requirements

- Python 3.x
- Required dependencies listed in `requirements.txt`
- Additional dependency for GUI:
    - `tkinterdnd2` (for drag-and-drop functionality)

## Contributing

We welcome contributions to improve NetworkFileCopyNinja! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
