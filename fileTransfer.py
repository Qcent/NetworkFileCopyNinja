import socket
import argparse
import os
import struct
import threading
import datetime
import time
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

def send_file(filename, root_dir, base_dir, host, port):
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
        except Exception as e:
            print(f'[{datetime.datetime.now()}] Error sending {filename}: Conection lost')
            failed_to_send()
            return 0

        # Send the file content
        with open(filename, 'rb') as file:
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
                with conn:
                    rel_path_length = struct.unpack('I', conn.recv(4))[0]
                    rel_path = conn.recv(rel_path_length).decode('utf-8')
                    file_path = os.path.join(save_dir, rel_path)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    print(f'[{datetime.datetime.now()}]  Incoming file: {rel_path} from {addr[0]}')
                    RECV_DATA["in_progress"] = True

                    if os.path.exists(file_path):
                        file_exists = True
                        if not RECV_DATA["overwrite"]:
                            print(f'\tFile {rel_path} already exists and will not be overwritten.')
                            RECV_DATA["rejected_files"] += 1
                            conn.close()
                            continue

                    statement = "Overwrote" if file_exists else "Received"

                    with open(file_path, 'wb') as file:
                        try:
                            while chunk := conn.recv(BUFFER_SIZE):
                                if RECV_DATA["canceled"]:
                                    print(f"[{datetime.datetime.now()}]  Cancellation requested during file transfer, stopping receive_files.")
                                    RECV_DATA["failed_files"] += 1
                                    RECV_DATA["in_progress"] = False
                                    conn.close()
                                    return 0
                                if not chunk:
                                    break
                                file.write(chunk)
                                RECV_DATA["data_received"] += len(chunk)
                            print(f'[{datetime.datetime.now()}]  {statement} {rel_path}')
                            RECV_DATA["received_files"] += 1
                        except Exception as e:
                            print(f'[{datetime.datetime.now()}] Error receiving {filename}: Conection lost')
                            RECV_DATA["failed_files"] += 1
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
