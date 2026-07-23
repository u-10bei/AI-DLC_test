"""SEC-03 IpAllowlist (US-02, NFR-S10.2, DP-01).

The compensating control that makes SECURITY-07's documented exception hold: the
server is internet-facing, but only the municipality's egress addresses can reach
it. Together with login (NFR-S10.1) this narrows the real reachable surface to
authenticated users inside the intranet.

Two fail-closed details worth stating: an unparseable IP is denied rather than
waved through, and an EMPTY allowlist denies everything. A missing configuration
must not be an open door (SECURITY-15).
"""

from __future__ import annotations

from ipaddress import ip_address, ip_network

from .config import SecurityConfig
from .exceptions import IpNotAllowedError


class IpAllowlist:
    """CIDR-aware source-IP check. Allowlist comes from configuration (NFR-M03)."""

    def __init__(self, config: SecurityConfig) -> None:
        self._networks = tuple(ip_network(entry, strict=False) for entry in config.ip_allowlist)

    def is_allowed(self, source_ip: str) -> bool:
        try:
            address = ip_address(source_ip)
        except ValueError:
            return False  # unparseable -> deny (fail closed)
        return any(address in network for network in self._networks)

    def check(self, source_ip: str) -> None:
        """Raise if the source is not allowed (DP-01)."""
        if not self.is_allowed(source_ip):
            raise IpNotAllowedError(source_ip=source_ip)


__all__ = ["IpAllowlist"]
