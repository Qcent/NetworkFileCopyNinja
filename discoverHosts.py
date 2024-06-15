import socket
import struct
import threading

from DiscoveryConsts import *
from netInterfaces import GetNetInfo

DEFAULT_TIMEOUT = 2


def get_broadcast_address(ip, subnet_mask):
    ip_bytes = struct.unpack('>I', socket.inet_aton(ip))[0]
    mask_bytes = struct.unpack('>I', socket.inet_aton(subnet_mask))[0]
    broadcast_bytes = ip_bytes | ~mask_bytes
    broadcast_address = socket.inet_ntoa(struct.pack('>I', broadcast_bytes & 0xffffffff))
    return broadcast_address


def send_discovery_message(broadcast_address, port, message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(message.encode(), (broadcast_address, port))
    sock.close()


def listen_for_responses(port, timeout=DEFAULT_TIMEOUT, lst=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', port+1))
    sock.settimeout(timeout)

    if lst is None:
        print("Listening for responses...")

    try:
        while True:
            data, addr = sock.recvfrom(1024)
            if lst is None:
                print(f"Received response from {addr}: {data.decode()}")
            else:
                hostname, hostPort = data.decode().split(":")
                lst.append((hostname, addr[0], hostPort))
    except socket.timeout:
        if lst is None:
            print("Listening timed out.")


def discover_hosts(ip, subnet_mask, port, message):
    broadcast_address = get_broadcast_address(ip, subnet_mask)
    print(f"Broadcast address: {broadcast_address}")

    listener_thread = threading.Thread(target=listen_for_responses, args=(port,))
    listener_thread.start()

    send_discovery_message(broadcast_address, port, message)


def discover_and_list_hosts():
    port = DiscoveryPort
    message = DiscoveryCode
    ip, subnet_mask = GetNetInfo()
    broadcast_address = get_broadcast_address(ip, subnet_mask)

    list_of_hosts = []

    listener_thread = threading.Thread(target=listen_for_responses, args=(port, DEFAULT_TIMEOUT, list_of_hosts))
    listener_thread.start()

    send_discovery_message(broadcast_address, port, message)

    listener_thread.join()
    return list_of_hosts


if __name__ == "__main__":
    # Replace with your network details
    my_ip, my_subnet_mask = GetNetInfo()

    discover_hosts(my_ip, my_subnet_mask, DiscoveryPort, DiscoveryCode)
