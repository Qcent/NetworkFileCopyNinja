import socket
import struct
import threading
import sys

from DiscoveryConsts import *
from tailscaleHosts import *
from netInterfaces import GetNetInfo


def get_broadcast_address(ip, subnet_mask):
    ip_bytes = struct.unpack('>I', socket.inet_aton(ip))[0]
    mask_bytes = struct.unpack('>I', socket.inet_aton(subnet_mask))[0]
    broadcast_bytes = ip_bytes | ~mask_bytes
    broadcast_address = socket.inet_ntoa(struct.pack('>I', broadcast_bytes & 0xffffffff))
    return broadcast_address


def discover_lan_hosts(ip, subnet_mask):
    broadcast_address = get_broadcast_address(ip, subnet_mask)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("", 0))

    #local_addr = sock.getsockname()

    #print(f"Discovery socket: {local_addr}")
    #print(f"Sending discovery to {broadcast_address}:{DiscoveryPort}")
    print(f"Pinging LAN for hosts.")
    
    sock.sendto(
        DiscoveryCode.encode(),
        (broadcast_address, DiscoveryPort)
    )

    print("Waiting for responses...")

    sock.settimeout(DEFAULT_TIMEOUT)

    hosts = []

    try:
        while True:
            data, addr = sock.recvfrom(1024)

            message = data.decode(errors="replace")

            print(f"Response from {addr}: {message}")

            if ":" not in message:
                continue

            hostname, host_port = message.split(":", 1)

            hosts.append(
                (hostname, addr[0], host_port)
            )

    except socket.timeout:
        print("Discovery finished.")

    finally:
        sock.close()

    return hosts



def discover_hosts_and_list(local_ip, subnet_mask, on_host_found):
    broadcast_address = get_broadcast_address(local_ip, subnet_mask)
    tailscale_peers = get_tailscale_peers()
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(('', 0))
    sock.settimeout(DEFAULT_TIMEOUT)

    # Send discovery
    if len(tailscale_peers):
        for host in tailscale_peers:
            ip = host['ip']
            sock.sendto(DiscoveryCode.encode(), (ip, DiscoveryPort))
    sock.sendto(DiscoveryCode.encode(), (broadcast_address, DiscoveryPort))

    try:
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                hostname, hostPort = data.decode().split(":")
                host = (hostname, addr[0], hostPort)
                on_host_found(host)

            except ConnectionResetError as e:
                #print("A probed talscale peer is not listening on the discovery port.")
                continue

    except socket.timeout:
        pass

    finally:
        sock.close()


if __name__ == "__main__":
    if "-ts" in sys.argv:
        discover_tailscale_hosts()
    else:
        ip, subnet_mask = GetNetInfo()
        discover_lan_hosts(ip, subnet_mask)

