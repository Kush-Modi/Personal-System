"""
Personal-System Root Bot Entrypoint.
Provides backward compatibility for existing Termux launch scripts.
"""

import socket

# Force IPv4 because IPv6 connectivity is unreliable on Termux / mobile network
_original_getaddrinfo = socket.getaddrinfo


def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(
        host,
        port,
        socket.AF_INET,
        type,
        proto,
        flags
    )


socket.getaddrinfo = getaddrinfo_ipv4


from app.telegram.bot import main

if __name__ == "__main__":
    main()
