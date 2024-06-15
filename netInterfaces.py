import netifaces as ni

def get_ip_and_subnet(interface):
    try:
        # Get the IP address
        ip_address = ni.ifaddresses(interface)[ni.AF_INET][0]['addr']
        # Get the subnet mask
        subnet_mask = ni.ifaddresses(interface)[ni.AF_INET][0]['netmask']
        return ip_address, subnet_mask
    except KeyError:
        return None, None

def get_default_interface():
    gws = ni.gateways()
    default_interface = gws['default'][ni.AF_INET][1]
    return default_interface

def GetNetInfo():
    return get_ip_and_subnet(get_default_interface())

if __name__ == "__main__":
    default_interface = get_default_interface()
    ip_address, subnet_mask = get_ip_and_subnet(default_interface)

    if ip_address and subnet_mask:
        print(f"Interface: {default_interface}")
        print(f"IP Address: {ip_address}")
        print(f"Subnet Mask: {subnet_mask}")
    else:
        print("Could not retrieve IP address and subnet mask.")