import socket
import argparse
import os
import struct
import threading
import datetime
from DiscoveryConsts import *

BUFFER_SIZE = 4096
SENT_DATA = {
    "bytesSent": 0,
    "failed_files": 0
             }

def send_file(filename, root_dir, base_dir, host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        # Construct the relative path to maintain directory structure
        rel_path = os.path.relpath(filename, root_dir)
        full_rel_path = os.path.join(base_dir, rel_path)
        # Send the relative path length and relative path first
        rel_path_bytes = full_rel_path.encode('utf-8')
        s.send(struct.pack('I', len(rel_path_bytes)))
        s.send(rel_path_bytes)
        # Send the file content
        with open(filename, 'rb') as file:
            print(f'Sending {full_rel_path} to {host}:{port}')
            while chunk := file.read(BUFFER_SIZE):
                try:
                    s.sendall(chunk)
                    SENT_DATA["bytesSent"] += len(chunk)
                except Exception as e:
                    print(f'Error sending {filename}: File may already exist on host machine')
                    SENT_DATA["failed_files"] += 1
                    return 0
        print(f'{full_rel_path} sent successfully')
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
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('0.0.0.0', port))
        s.listen()
        print(f'Listening for incoming connections on port {port}')
        while True:
            conn, addr = s.accept()
            file_exists = False
            with conn:
                #print(f'Connection from {addr}')
                # Receive the relative path length and relative path first
                rel_path_length = struct.unpack('I', conn.recv(4))[0]
                rel_path = conn.recv(rel_path_length).decode('utf-8')
                file_path = os.path.join(save_dir, rel_path)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                if os.path.exists(file_path):
                    file_exists = True
                    if not overwrite:
                        print(f'File {rel_path} already exists and will not be overwritten.')
                        conn.close()
                        continue

                statement = "Overwrote" if file_exists else "Received"

                # Receive the file content
                with open(file_path, 'wb') as file:
                    while chunk := conn.recv(BUFFER_SIZE):
                        if not chunk:
                            break
                        file.write(chunk)
                    print(f'{statement} {rel_path}, from {addr[0]} [{datetime.datetime.now()}]')


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
                print(f"Discovered by: {addr} [{datetime.datetime.now()}]")
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
