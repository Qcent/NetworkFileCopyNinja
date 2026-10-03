import socket
import argparse
import os
import struct
import threading
import datetime
import time
import zlib
import select

from DiscoveryConsts import *

VERSION_NUM = "1.1"

BUFFER_SIZE = 64 * 1024
SENT_DATA = {
    "bytesSent": 0,
    "failed_files": 0,
    "processed_files": 0,
    "using_gui": False,
    "gui_response": None,
    "file_info": ("", 0, 0),
    "canceled": False
    }

RECV_DATA = {
    "received_files": 0,
    "rejected_files": 0,
    "failed_files": 0,
    "data_received": 0,
    "overwrite": False,
    "in_progress": False,
    "canceled": False
    }

ALL_GOOD_MSG = "0xB00B1E5"
REJECTED_MSG = "0xD6EC7ED"
REQ_CRC32_MSG = "AC710271BE"
RESUME_MSG = "0x7E50BE"
SAME_COPY_MSG = "0x5ABEC097"
DIFF_FILE_MSG = "0xD1FFF1113"
REQ_OVERWRITE_MSG = "0x0B37717E"
KEEP_BOTH_MSG = "0x4EE9B074"
SKIP_FILE_MSG = "0x5419F111E"


def calculate_crc32(file_path):
    """ Calculate the CRC32 checksum of a file. """
    crc32 = 0
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            crc32 = zlib.crc32(chunk, crc32)
    return crc32


def calculate_partial_crc32(file_path, length):
    """ Calculate the CRC32 checksum of the first 'length' bytes of a file. """
    crc32 = 0
    with open(file_path, 'rb') as f:
        remaining = length
        while remaining > 0:
            chunk = f.read(min(65536, remaining))
            if not chunk:  # Handle case if read returns empty
                break
            crc32 = zlib.crc32(chunk, crc32)
            remaining -= len(chunk)
    return crc32


def convert_path_to_os_style(filepath):
    if os.path.sep == '/':
        # Current system is Unix-like (Linux, macOS)
        if '\\' in filepath:
            return filepath.replace('\\', '/')
        else:
            return filepath
    elif os.path.sep == '\\':
        # Current system is Windows
        if '/' in filepath:
            return filepath.replace('/', '\\')
        else:
            return filepath
    else:
        raise OSError("Unsupported operating system")


def append_to_filename(file_path, append_str):
    # Split the file path into directory, base name, and extension
    directory, filename = os.path.split(file_path)
    base, ext = os.path.splitext(filename)

    # Append the base name
    new_base = base + append_str

    # Return the new file path
    return os.path.join(directory, new_base + ext)


def report_data_size(size):
    units = ['bytes', 'kB', 'MB', 'GB', 'TB']
    unit_index = 0
    if not size:
        return f"0 {units[unit_index]}"
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return f"{size:.2f} {units[unit_index]}"


def send_file(filename, root_dir, base_dir, host, port):
    resume_at_byte = None  # use None instead of False
    file_size = 0          # ensure defined for error messages

    def failed_to_send():
        SENT_DATA["failed_files"] += 1
        SENT_DATA["processed_files"] += 1

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((host, port))
        except Exception as e:
            print(f'[{datetime.datetime.now()}] Error sending {filename}: Could not establish connection : {e}')
            failed_to_send()
            return 0

        file_data_sent = 0

        rel_path = os.path.relpath(filename, root_dir)
        full_rel_path = os.path.join(base_dir, rel_path)

        rel_path_bytes = full_rel_path.encode('utf-8')

        try:
            # Send relative path
            s.sendall(struct.pack('I', len(rel_path_bytes)))
            s.sendall(rel_path_bytes)

            # Send file size
            file_size = os.path.getsize(filename)
            s.sendall(struct.pack('Q', file_size))

            # Wait for receiver message
            msg_length = struct.unpack('I', recv_exact(s, 4))[0]
            msg = recv_exact(s, msg_length).decode('utf-8')

            if msg == ALL_GOOD_MSG:
                pass

            elif msg == REJECTED_MSG:
                print(f'[{datetime.datetime.now()}] Error sending {filename}({report_data_size(file_size)}): File Rejected')
                failed_to_send()
                return 0

            elif msg == REQ_CRC32_MSG:
                # Receive file length
                dest_file_size = struct.unpack('Q', recv_exact(s, 8))[0]
                crc32 = calculate_partial_crc32(filename, dest_file_size)
                s.sendall(struct.pack('I', crc32))

                # Wait for receiver message
                msg_length = struct.unpack('I', recv_exact(s, 4))[0]
                msg = recv_exact(s, msg_length).decode('utf-8')

                if msg == SAME_COPY_MSG:
                    print(f'[{datetime.datetime.now()}] {full_rel_path}({report_data_size(file_size)}) already exists on host machine')
                    SENT_DATA["processed_files"] += 1
                    return 1
                elif msg == RESUME_MSG:
                    resume_at_byte = dest_file_size

            elif msg == DIFF_FILE_MSG:
                # Receive file length
                dest_file_size = struct.unpack('Q', recv_exact(s, 8))[0]

                response = None
                if not SENT_DATA["using_gui"]:
                    prompt = (
                        f"  {full_rel_path}({report_data_size(dest_file_size)}) already exists on host machine.\n"
                        f"  {full_rel_path}({report_data_size(file_size)}) local copy.\n"
                        "  What would you like to do? "
                        "'O' to Overwrite, 'B' to Keep Both, 'S' to Skip: "
                    )
                    response = input(prompt).strip().upper()
                    while response not in ['O', 'B', 'S']:
                        response = input("Invalid input. Please enter 'O', 'B', or 'S': ").strip().upper()
                else:
                    # GUI path
                    SENT_DATA["file_info"] = (rel_path, dest_file_size, file_size)
                    SENT_DATA["gui_response"] = "NEEDED"
                    while SENT_DATA["gui_response"] not in ['O', 'B', 'S']:
                        time.sleep(0.3)
                    response = SENT_DATA["gui_response"]

                # Send messages
                if response == 'O':
                    s.sendall(struct.pack('I', len(REQ_OVERWRITE_MSG)))
                    s.sendall(REQ_OVERWRITE_MSG.encode())
                elif response == 'B':
                    s.sendall(struct.pack('I', len(KEEP_BOTH_MSG)))
                    s.sendall(KEEP_BOTH_MSG.encode())
                elif response == 'S':
                    s.sendall(struct.pack('I', len(SKIP_FILE_MSG)))
                    s.sendall(SKIP_FILE_MSG.encode())
                    failed_to_send()
                    return 0

                # Wait for receiver message
                msg_length = struct.unpack('I', recv_exact(s, 4))[0]
                msg = recv_exact(s, msg_length).decode('utf-8')

                if msg == ALL_GOOD_MSG:
                    pass
                elif msg == REJECTED_MSG:
                    print(f'[{datetime.datetime.now()}]  Error sending {full_rel_path}({report_data_size(file_size)}) : Rejected by host.')
                    failed_to_send()
                    return 0
                else:
                    print(f'[{datetime.datetime.now()}]  Error sending {full_rel_path}({report_data_size(file_size)}) : Host error.')
                    failed_to_send()
                    return 0

        except Exception as e:
            print(f'[{datetime.datetime.now()}] Error sending {filename}({report_data_size(file_size)}): {e}')
            failed_to_send()
            return 0

        # Send the file content
        try:
            with open(filename, 'rb') as file:
                if resume_at_byte is not None:
                    file.seek(resume_at_byte)
                    print(f'[{datetime.datetime.now()}] Resuming {full_rel_path}({report_data_size(file_size)}) transfer to {host}:{port}')
                else:
                    print(f'[{datetime.datetime.now()}] Sending {full_rel_path}({report_data_size(file_size)}) to {host}:{port}')

                while True:
                    chunk = file.read(BUFFER_SIZE)
                    if not chunk:
                        break

                    if SENT_DATA["canceled"]:
                        print(f'[{datetime.datetime.now()}] User canceled transfer')
                        failed_to_send()
                        return 0

                    try:
                        s.sendall(chunk)
                        SENT_DATA["bytesSent"] += len(chunk)
                        file_data_sent += len(chunk)
                    except Exception as e:
                        print(f'Error sending {filename}({report_data_size(file_size)}): {e}')
                        failed_to_send()
                        return 0
        except Exception as e:
            print(f'[{datetime.datetime.now()}] Error reading {filename}: {e}')
            failed_to_send()
            return 0

        print(f'[{datetime.datetime.now()}] {full_rel_path} sent successfully [{report_data_size(file_data_sent)}]')
        SENT_DATA["processed_files"] += 1
        return 1


def send_directory(directory, host, port):
    success = 1
    base_dir = os.path.basename(directory)
    for root, _, files in os.walk(directory):
        for file in files:
            full_path = os.path.join(root, file)
            if not send_file(full_path, directory, base_dir, host, port):
                success = 0
    return success


def recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed while receiving data")
        data += chunk
    return data


def receive_files(save_dir, port, overwrite=False):
    RECV_DATA["overwrite"] = overwrite

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('0.0.0.0', port))
        s.listen()
        print(f'Listening for incoming connections on port {port}')

        while True:
            if RECV_DATA["canceled"]:
                return

            readable, _, _ = select.select([s], [], [], 1)  # 1 second timeout
            if s in readable:
                conn, addr = s.accept()
                file_exists = False
                different_files = True
                resuming_transfer = False

                with conn:
                    def fail_transfer():
                        RECV_DATA["failed_files"] += 1
                        RECV_DATA["in_progress"] = False

                    def reject_transfer():
                        RECV_DATA["rejected_files"] += 1
                        RECV_DATA["in_progress"] = False

                    try:
                        # Receive file name and size
                        rel_path_length = struct.unpack('I', recv_exact(conn, 4))[0]
                        rel_path = recv_exact(conn, rel_path_length).decode('utf-8')
                        sender_file_size = struct.unpack('Q', recv_exact(conn, 8))[0]

                        file_path = os.path.join(save_dir, convert_path_to_os_style(rel_path))
                        print(f'\n[{datetime.datetime.now()}]  Incoming file: {rel_path} ({report_data_size(sender_file_size)}) from {addr[0]}')

                        if os.path.exists(file_path):
                            file_exists = True
                            local_file_size = os.path.getsize(file_path)
                            print(f'\tFile {rel_path} ({report_data_size(local_file_size)}) exists locally.')

                            reason = "size_mismatch"

                            if sender_file_size >= local_file_size:
                                conn.sendall(struct.pack('I', len(REQ_CRC32_MSG)))
                                conn.sendall(REQ_CRC32_MSG.encode())
                                conn.sendall(struct.pack('Q', local_file_size))

                                crc32 = calculate_crc32(file_path)
                                sender_crc32 = struct.unpack('I', recv_exact(conn, 4))[0]

                                if sender_crc32 == crc32:
                                    different_files = False
                                    if sender_file_size == local_file_size:
                                        conn.sendall(struct.pack('I', len(SAME_COPY_MSG)))
                                        conn.sendall(SAME_COPY_MSG.encode())
                                        print(f'\t{rel_path} ({report_data_size(local_file_size)}) Checksum match, and file size match, no overwrite required.')
                                        reject_transfer()
                                        continue
                                    else:
                                        resuming_transfer = True
                                        conn.sendall(struct.pack('I', len(RESUME_MSG)))
                                        conn.sendall(RESUME_MSG.encode())
                                        print(f'\t{rel_path} ({report_data_size(local_file_size)}) Checksum match, resuming transfer.')
                                else:
                                    reason = "crc_mismatch"

                            if different_files:
                                if reason == "crc_mismatch":
                                    print(f'\t{rel_path} ({report_data_size(local_file_size)}) checksum mismatch; cannot resume safely.')
                                else:
                                    print(f'\t{rel_path} ({report_data_size(local_file_size)}) local file larger; cannot resume safely.')

                                conn.sendall(struct.pack('I', len(DIFF_FILE_MSG)))
                                conn.sendall(DIFF_FILE_MSG.encode())
                                conn.sendall(struct.pack('Q', local_file_size))

                                msg_length = struct.unpack('I', recv_exact(conn, 4))[0]
                                msg = recv_exact(conn, msg_length).decode('utf-8')

                                if msg == SKIP_FILE_MSG:
                                    print(f'[{datetime.datetime.now()}]  Transfer of file {rel_path} ({report_data_size(local_file_size)}) skipped by sender')
                                    fail_transfer()
                                    continue
                                elif msg == REQ_OVERWRITE_MSG:
                                    if not RECV_DATA["overwrite"]:
                                        print(f'[{datetime.datetime.now()}]  File {rel_path} ({report_data_size(local_file_size)}) will not be overwritten.')
                                        conn.sendall(struct.pack('I', len(REJECTED_MSG)))
                                        conn.sendall(REJECTED_MSG.encode())
                                        reject_transfer()
                                        continue
                                    else:
                                        conn.sendall(struct.pack('I', len(ALL_GOOD_MSG)))
                                        conn.sendall(ALL_GOOD_MSG.encode())
                                elif msg == KEEP_BOTH_MSG:
                                    file_version = 1
                                    new_file_path = append_to_filename(file_path, f"({file_version})")
                                    while os.path.exists(new_file_path):
                                        file_version += 1
                                        new_file_path = append_to_filename(file_path, f"({file_version})")
                                    file_path = new_file_path
                                    rel_path = append_to_filename(rel_path, f"({file_version})")
                                    file_exists = False
                                    conn.sendall(struct.pack('I', len(ALL_GOOD_MSG)))
                                    conn.sendall(ALL_GOOD_MSG.encode())
                        else:
                            conn.sendall(struct.pack('I', len(ALL_GOOD_MSG)))
                            conn.sendall(ALL_GOOD_MSG.encode())

                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        RECV_DATA["in_progress"] = True

                        statement = "Appended" if resuming_transfer else ("Overwrote" if file_exists else "Received")

                        bytes_written = 0
                        mode = 'ab' if resuming_transfer else 'wb'
                        with open(file_path, mode) as file:
                            while True:
                                chunk = conn.recv(BUFFER_SIZE)
                                if not chunk:
                                    break
                                if RECV_DATA["canceled"]:
                                    print(f"[{datetime.datetime.now()}]  Cancellation requested during file transfer")
                                    print(f'\t Cancelled {rel_path} [{report_data_size(bytes_written)} written]')
                                    fail_transfer()
                                    # if you *don't* want to stop the entire server, use `break` instead of `return`
                                    return 0
                                file.write(chunk)
                                RECV_DATA["data_received"] += len(chunk)
                                bytes_written += len(chunk)

                        print(f'[{datetime.datetime.now()}]  {statement} {rel_path} [{report_data_size(bytes_written)} written]')
                        RECV_DATA["received_files"] += 1

                    except Exception as e:
                        print(f'[{datetime.datetime.now()}] Error receiving {rel_path if "rel_path" in locals() else "unknown file"}: {e}')
                        fail_transfer()
                    finally:
                        RECV_DATA["in_progress"] = False


def listen_for_discovery(port, host_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', port))
    print("Listening for discovery messages...")

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            if data.decode() == DiscoveryCode:
                response_message = f"{socket.gethostname()}:{host_port}"
                sock.sendto(response_message.encode(), addr)
                print(f"Discovered by: {addr}  [{datetime.datetime.now()}]")

        except ConnectionResetError as e:
            # normally triggers after broadcast ends
            continue
        except Exception as e:
            print(f"Error: {e}")
            continue


def start_discovery_listener(host_port, discovery_port=DiscoveryPort):
    discovery_thread = threading.Thread(target=listen_for_discovery, args=(discovery_port, host_port))
    discovery_thread.daemon = True
    discovery_thread.start()


def main():
    parser = argparse.ArgumentParser(description=f'Qcent\'s File Transfer Program v{VERSION_NUM}')
    parser.add_argument('mode', choices=['send', 'receive'], help='Mode: send or receive')
    parser.add_argument('--files', nargs='+', help='Files to send (required in send mode)')
    parser.add_argument('--dir', help='Directory to send (required in send mode)')
    parser.add_argument('--host', help='Host to connect to (required in send mode)')
    parser.add_argument('--port', type=int, required=True, help='Port to connect/listen on')
    parser.add_argument('--savedir', help='Directory to save the received files (required in receive mode)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files (optional, default is False)')
    args = parser.parse_args()

    if args.mode == 'send':
        if not args.host:
            parser.error('send mode requires --host')
        if args.files:
            for file in args.files:
                send_file(file, os.path.dirname(file), '', args.host, args.port)
        elif args.dir:
            send_directory(args.dir, args.host, args.port)
        else:
            parser.error('send mode requires either --files or --dir')
    elif args.mode == 'receive':
        if not args.savedir:
            parser.error('receive mode requires --savedir')
        start_discovery_listener(args.port, DiscoveryPort)
        receive_files(args.savedir, args.port, args.overwrite)


if __name__ == '__main__':
    main()



