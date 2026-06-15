# INFRASTRUCTURE


# FUNCTIONS

# Build canonical key: protocol://host:port (auth stripped if present)
def proxy_key(proto: str, host_port: str) -> str:
    host, port = _parse_host_port(host_port)
    return f"{proto}://{host}:{port}"


# Return (host, port) from 'host:port' or 'user:pass@host:port'
def _parse_host_port(host_port: str) -> tuple[str, int]:
    clean        = host_port.split("@")[-1]
    host, port_s = clean.rsplit(":", 1)
    return host, int(port_s)
