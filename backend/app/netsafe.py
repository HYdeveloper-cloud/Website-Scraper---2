import ipaddress
import socket
from urllib.parse import urlparse

from . import config


def safe_public_url(raw: str) -> str:
    """Returns a clean https/http URL, or raises ValueError with a message the owner can act on."""
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Enter a website address.")
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    host = urlparse(raw).hostname
    if not host:
        raise ValueError("Enter a valid website address.")
    if config.ALLOW_PRIVATE_URLS:
        return raw
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("That address points to a private network, so it was not opened.")
    except socket.gaierror:
        raise ValueError("Could not find that website. Check the address.")
    return raw
