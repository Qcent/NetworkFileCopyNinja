import socket
import argparse
import os
import struct
import threading
import datetime
import zlib
import select

from DiscoveryConsts import *

BUFFER_SIZE = 4096
SENT_DATA = {
    "bytesSent": 0,
    "failed_files": 0,
    "processed_files": 0,
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
RESUME_MSG   = "0x7E50BE"


def calculate_crc32(file_path):
    """ Calculate the CRC32 checksum of a file. """
    crc32 = 0
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            crc32 = zlib.crc32(chunk, crc32)
    return crc32


def calculate_partial_crc32(file_path, length):
    """ Calculate the CRC32 checksum of the first 'length' bytes of a file. """
    crc32 = 0
    with open(file_path, 'rb') as f:
        remaining = length
        while remaining > 0:
            chunk = f.read(min(4096, remaining))
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
    resume_at_byte = False

    def failed_to_send():
        SENT_DATA["failed_files"] += 1
        SENT_DATA["processed_files"] += 1

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((host, port))
        except Exception as e:
            print(f'[{datetime.datetime.now()}] Error sending {filename}: Could not establish connection')
            failed_to_send()
            return 0

        # Construct the relative path to maintain directory structure
        rel_path = os.path.relpath(filename, root_dir)
        full_rel_path = os.path.join(base_dir, rel_path)

        # Send the relative path length and relative path first
        rel_path_bytes = full_rel_path.encode('utf-8')
        try:
            s.send(struct.pack('I', len(rel_path_bytes)))
            s.send(rel_path_bytes)
            # Send file size
            file_size = os.path.getsize(filename)
            s.send(struct.pack('I', file_size))

            # Wait for receiver message
            msg_length = struct.unpack('I', s.recv(4))[0]
            msg = s.recv(msg_length).decode('utf-8')

            # handle message from receiver
            if msg == ALL_GOOD_MSG:
                pass
            elif msg == RESUME_MSG:
                # Resume file-check handshake

                # Wait for 12 bytes containing dest file length or rejected message
                twelve_byte_data = s.recv(12)

                # Try to decode as REJECTED_MSG
                try:
                    decoded_msg = twelve_byte_data.decode('utf-8').rstrip('\0')
                    if decoded_msg == REJECTED_MSG:
                        print(f'[{datetime.datetime.now()}] Error sending {filename}: File Rejected')
                        failed_to_send()
                        return 0
                except Exception as e:
                    pass  # only exception should be un decodeable string in which case ...

                # Unpack as integer (dest_file_size)
                dest_file_size = struct.unpack('I', twelve_byte_data[:4])[0]

                # Calc crc32 at that length and send back
                crc32 = calculate_partial_crc32(filename, dest_file_size)
                s.send(struct.pack('I', crc32))

                # Wait for receiver message
                msg_length = struct.unpack('I', s.recv(4))[0]
                msg = s.recv(msg_length).decode('utf-8')

                if msg == RESUME_MSG:
                    resume_at_byte = dest_file_size

            if msg == REJECTED_MSG:
                print(f'[{datetime.datetime.now()}] Error sending {filename}: File Rejected')
                failed_to_send()
                return 0

        except Exception as e:
            print(f'[{datetime.datetime.now()}] Error sending {filename}: Connection lost')
            failed_to_send()
            return 0

        # Send the file content
        with open(filename, 'rb') as file:
            if resume_at_byte:
                file.seek(resume_at_byte)
                print(f'[{datetime.datetime.now()}] Resuming {full_rel_path} transfer to {host}:{port}')
            else:
                print(f'[{datetime.datetime.now()}] Sending {full_rel_path} to {host}:{port}')
            while chunk := file.read(BUFFER_SIZE):
                if SENT_DATA["canceled"]:
                    print(f'[{datetime.datetime.now()}] User canceled transfer')
                    failed_to_send()
                    return 0

                try:
                    s.sendall(chunk)
                    SENT_DATA["bytesSent"] += len(chunk)

                except Exception as e:
                    print(f'Error sending {filename}: File may already exist on host machine')
                    failed_to_send()
                    return 0

        print(f'[{datetime.datetime.now()}] {full_rel_path} sent successfully')
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
                resuming_transfer = False
                with conn:
                    def fail_transfer():
                        RECV_DATA["failed_files"] += 1
                        RECV_DATA["in_progress"] = False
                        conn.close()

                    rel_path_length = struct.unpack('I', conn.recv(4))[0]
                    rel_path = conn.recv(rel_path_length).decode('utf-8')
                    sender_file_size = struct.unpack('I', conn.recv(4))[0]

                    # Convert the received path to current machine's path style
                    file_path = os.path.join(save_dir, convert_path_to_os_style(rel_path))

                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    print(f'\n[{datetime.datetime.now()}]  Incoming file: {rel_path} ({report_data_size(sender_file_size)}) from {addr[0]}')
                    RECV_DATA["in_progress"] = True

                    if os.path.exists(file_path):
                        file_exists = True
                        local_file_size = os.path.getsize(file_path)
                        print(f'\tFile {rel_path} ({report_data_size(local_file_size)}) exists locally.')
                        # Go through resume checking handshake
                        # Send Resume Message
                        conn.send(struct.pack('I', len(RESUME_MSG)))
                        conn.send(RESUME_MSG.encode())

                        if sender_file_size <= local_file_size:
                            # REJECT THIS SMALLER OR SAME SIZE FILE
                            # Ensure REJECTED_MSG is exactly 12 bytes long, pad with null bytes
                            rejected_msg_padded = REJECTED_MSG.ljust(12, '\0')
                            # Pack the string into 12 bytes
                            twelve_byte_data = struct.pack('12s', rejected_msg_padded.encode('utf-8'))  # '12s' for 12-byte string
                            conn.send(twelve_byte_data)
                            print(f'\tFile {rel_path} ({report_data_size(local_file_size)}) is {"same size" if sender_file_size == local_file_size else "larger"} and will not be overwritten.')
                            fail_transfer()
                            continue

                        # send file size as 12 byte package
                        # Pack the integer and pad with 8 zero bytes
                        twelve_byte_data = struct.pack('I8x', local_file_size)  # 'I' for 4-byte unsigned int, '8x' for 8 padding bytes
                        conn.send(twelve_byte_data)

                        crc32 = calculate_crc32(file_path)

                        # Wait for crc32 from sender
                        sender_crc32 = struct.unpack('I', conn.recv(4))[0]

                        # Compare crc32s
                        if sender_crc32 == crc32:
                            resuming_transfer = True
                            conn.send(struct.pack('I', len(RESUME_MSG)))
                            conn.send(RESUME_MSG.encode())
                            print(f'\t{rel_path} ({report_data_size(local_file_size)}) Checksum match, resuming transfer.')

                        elif not RECV_DATA["overwrite"]:
                            print(f'\tFile {rel_path} ({report_data_size(local_file_size)}) will not be overwritten.')
                            conn.send(struct.pack('I', len(REJECTED_MSG)))
                            conn.send(REJECTED_MSG.encode())
                            fail_transfer()
                            continue

                        if not resuming_transfer:
                            conn.send(struct.pack('I', len(ALL_GOOD_MSG)))
                            conn.send(ALL_GOOD_MSG.encode())
                    else:
                        conn.send(struct.pack('I', len(ALL_GOOD_MSG)))
                        conn.send(ALL_GOOD_MSG.encode())

                    statement = "Appended" if resuming_transfer is True else ("Overwrote" if file_exists else "Received")

                    with open(file_path, 'wb' if not resuming_transfer else 'ab') as file:
                        bytes_written = 0
                        try:
                            while chunk := conn.recv(BUFFER_SIZE):
                                if RECV_DATA["canceled"]:
                                    print(f"[{datetime.datetime.now()}]  Cancellation requested during file transfer")
                                    print(f'\t Cancelled {rel_path} [{report_data_size(bytes_written)} written]')
                                    fail_transfer()
                                    return 0
                                if not chunk:
                                    break
                                file.write(chunk)
                                RECV_DATA["data_received"] += len(chunk)
                                bytes_written += len(chunk)
                            print(f'[{datetime.datetime.now()}]  {statement} {rel_path} [{report_data_size(bytes_written)} written]')
                            RECV_DATA["received_files"] += 1
                        except Exception as e:
                            print(f'[{datetime.datetime.now()}] Error receiving {rel_path} [{report_data_size(bytes_written)} written]: Connection lost')
                            fail_transfer()
                            continue
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
                sock.sendto(response_message.encode(), (addr[0], port+1))
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
    parser = argparse.ArgumentParser(description='File Transfer Program')
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
