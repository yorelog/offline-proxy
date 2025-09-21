"""
Protocol handlers for different network protocols.

This module contains handlers for various protocols supported by the offline proxy:
- Git protocol
- APT package management
- PyPI Python packages
- HTTP/HTTPS (handled by main proxy)
"""

from .git import GitProtocolHandler
from .apt import APTProtocolHandler
from .pypi import PyPIProtocolHandler

__all__ = [
    "GitProtocolHandler",
    "APTProtocolHandler", 
    "PyPIProtocolHandler",
]