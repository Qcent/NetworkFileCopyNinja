import socket
import subprocess
import json

from DiscoveryConsts import *

def discover_tailscale_hosts():
    ts_peers = get_tailscale_peers()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(DEFAULT_TIMEOUT)

    # Bind to an ephemeral local port.
    sock.bind(("", 0))

    #local_addr = sock.getsockname()
    #print(f"Discovery socket: {local_addr}")
    print(f"Pinging {len(hosts)} Tailscale peers.")

    for host in ts_peers:
        ip = host['ip']
        #print(f"Sending discovery to {ip}:{DiscoveryPort}")
        sock.sendto(DiscoveryCode.encode(), (ip, DiscoveryPort))

    print("Waiting for responses...")

    try:
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                print(f"Response from {addr}: {data.decode(errors='replace')}")

            except ConnectionResetError as e:
                #print("A probed host is not listening on the discovery port.")
                continue

    except socket.timeout:
        print("Discovery finished.")

    finally:
        sock.close()


def get_tailscale_peers():
    result = subprocess.run(
        ["tailscale", "status", "--json"],
        capture_output=True,
        text=True,
        check=True
    )

    status = json.loads(result.stdout)

    self_ips = status.get("Self", {}).get("TailscaleIPs", [])

    self_ipv4 = next(
        (ip for ip in self_ips if "." in ip),
        None
    )

    hosts = []

    for peer in status.get("Peer", {}).values():

        if not peer.get("Online", False):
            continue

        tailscale_ips = peer.get("TailscaleIPs", [])

        ipv4 = next(
            (ip for ip in tailscale_ips if "." in ip),
            None
        )

        if ipv4 is None:
            continue

        if ipv4 == self_ipv4:
            continue

        hosts.append({
            "hostname": peer.get("HostName", ""),
            "ip": ipv4,
            "dns_name": peer.get("DNSName", ""),
        })

    return hosts
