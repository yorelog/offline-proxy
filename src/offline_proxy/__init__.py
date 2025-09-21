"""
Offline Proxy - A multi-protocol offline proxy tool

This package provides functionality to cache network resources in an online environment
and serve them through a local proxy server in an offline environment.

Key features:
- Multi-protocol support (HTTP/HTTPS, Git, APT, PyPI)
- Intelligent resource caching and dependency discovery
- SSL certificate management for HTTPS support
- Automatic hosts file management
- Resource cleanup and update detection
"""

__version__ = "1.0.0"
__author__ = "Zhou"
__email__ = ""

from .proxy import ProxyServer
from .cache import CacheManager
from .ssl import SSLManager

__all__ = [
    "ProxyServer",
    "CacheManager", 
    "SSLManager",
]