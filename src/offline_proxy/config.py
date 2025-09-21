"""
Configuration management for the offline proxy.

This module handles loading and validating configuration from YAML files.
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProxyConfig:
    """Proxy server configuration."""
    http_port: int = 8080
    https_port: int = 8443
    bind_address: str = "0.0.0.0"
    mode: str = "cache"  # cache or offline


@dataclass
class CacheConfig:
    """Cache configuration."""
    root_dir: str = "./data"
    max_size_gb: int = 50
    expire_days: int = 30
    compression: bool = True
    compression_algorithm: str = "zstd"


@dataclass
class SSLConfig:
    """SSL certificate configuration."""
    cert_dir: str = "./certs"
    ca_validity_days: int = 3650
    server_validity_days: int = 365
    organization: str = "Offline Proxy"
    country: str = "CN"


@dataclass
class HTTPProtocolConfig:
    """HTTP protocol configuration."""
    enabled: bool = True
    user_agent: str = "OfflineProxy/1.0"
    timeout: int = 30
    max_retries: int = 3


@dataclass
class GitProtocolConfig:
    """Git protocol configuration."""
    enabled: bool = True
    port: int = 9418
    services: List[str] = field(default_factory=lambda: [
        "github.com", "gitlab.com", "gitee.com", "bitbucket.org"
    ])


@dataclass
class APTProtocolConfig:
    """APT protocol configuration."""
    enabled: bool = True
    port: int = 8081
    distributions: List[str] = field(default_factory=lambda: ["ubuntu", "debian"])
    architectures: List[str] = field(default_factory=lambda: ["amd64", "arm64"])
    default_mirrors: Dict[str, str] = field(default_factory=lambda: {
        "ubuntu": "http://archive.ubuntu.com/ubuntu/",
        "debian": "http://deb.debian.org/debian/"
    })


@dataclass
class PyPIProtocolConfig:
    """PyPI protocol configuration."""
    enabled: bool = True
    port: int = 8082
    index_url: str = "https://pypi.org/simple/"
    python_versions: List[str] = field(default_factory=lambda: [
        "3.8", "3.9", "3.10", "3.11", "3.12"
    ])


@dataclass
class ProtocolsConfig:
    """All protocols configuration."""
    http: HTTPProtocolConfig = field(default_factory=HTTPProtocolConfig)
    git: GitProtocolConfig = field(default_factory=GitProtocolConfig)
    apt: APTProtocolConfig = field(default_factory=APTProtocolConfig)
    pypi: PyPIProtocolConfig = field(default_factory=PyPIProtocolConfig)


@dataclass
class DiscoveryConfig:
    """Resource discovery configuration."""
    enabled: bool = True
    scan_interval_hours: int = 24
    dependency_depth: int = 3
    transitive_dependencies: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: str = "./logs/offline_proxy.log"
    max_file_size_mb: int = 100
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class HostsConfig:
    """Hosts file configuration."""
    file_path: str = "/etc/hosts"
    backup_path: str = "/etc/hosts.offline_proxy_backup"
    auto_backup: bool = True


@dataclass
class PerformanceConfig:
    """Performance configuration."""
    worker_threads: int = 10
    connection_pool_size: int = 100
    cache_warmup: bool = False
    memory_cache_mb: int = 512


@dataclass
class Config:
    """Main configuration class."""
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    ssl: SSLConfig = field(default_factory=SSLConfig)
    protocols: ProtocolsConfig = field(default_factory=ProtocolsConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    hosts: HostsConfig = field(default_factory=HostsConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)

    @classmethod
    def load_from_file(cls, config_path: str) -> 'Config':
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Config object with loaded settings
        """
        if not os.path.exists(config_path):
            # Return default configuration if file doesn't exist
            return cls()
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            
        if not config_data:
            return cls()
            
        return cls._from_dict(config_data)
    
    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """
        Create Config object from dictionary.
        
        Args:
            data: Configuration dictionary
            
        Returns:
            Config object
        """
        config = cls()
        
        # Update proxy config
        if "proxy" in data:
            proxy_data = data["proxy"]
            config.proxy.http_port = proxy_data.get("http_port", config.proxy.http_port)
            config.proxy.https_port = proxy_data.get("https_port", config.proxy.https_port)
            config.proxy.bind_address = proxy_data.get("bind_address", config.proxy.bind_address)
            config.proxy.mode = proxy_data.get("mode", config.proxy.mode)
            
        # Update cache config
        if "cache" in data:
            cache_data = data["cache"]
            config.cache.root_dir = cache_data.get("root_dir", config.cache.root_dir)
            config.cache.max_size_gb = cache_data.get("max_size_gb", config.cache.max_size_gb)
            config.cache.expire_days = cache_data.get("expire_days", config.cache.expire_days)
            config.cache.compression = cache_data.get("compression", config.cache.compression)
            config.cache.compression_algorithm = cache_data.get("compression_algorithm", config.cache.compression_algorithm)
            
        # Update SSL config
        if "ssl" in data:
            ssl_data = data["ssl"]
            config.ssl.cert_dir = ssl_data.get("cert_dir", config.ssl.cert_dir)
            config.ssl.ca_validity_days = ssl_data.get("ca_validity_days", config.ssl.ca_validity_days)
            config.ssl.server_validity_days = ssl_data.get("server_validity_days", config.ssl.server_validity_days)
            config.ssl.organization = ssl_data.get("organization", config.ssl.organization)
            config.ssl.country = ssl_data.get("country", config.ssl.country)
            
        # Update protocols config
        if "protocols" in data:
            protocols_data = data["protocols"]
            
            # HTTP protocol
            if "http" in protocols_data:
                http_data = protocols_data["http"]
                config.protocols.http.enabled = http_data.get("enabled", config.protocols.http.enabled)
                config.protocols.http.user_agent = http_data.get("user_agent", config.protocols.http.user_agent)
                config.protocols.http.timeout = http_data.get("timeout", config.protocols.http.timeout)
                config.protocols.http.max_retries = http_data.get("max_retries", config.protocols.http.max_retries)
                
            # Git protocol
            if "git" in protocols_data:
                git_data = protocols_data["git"]
                config.protocols.git.enabled = git_data.get("enabled", config.protocols.git.enabled)
                config.protocols.git.port = git_data.get("port", config.protocols.git.port)
                config.protocols.git.services = git_data.get("services", config.protocols.git.services)
                
            # APT protocol
            if "apt" in protocols_data:
                apt_data = protocols_data["apt"]
                config.protocols.apt.enabled = apt_data.get("enabled", config.protocols.apt.enabled)
                config.protocols.apt.port = apt_data.get("port", config.protocols.apt.port)
                config.protocols.apt.distributions = apt_data.get("distributions", config.protocols.apt.distributions)
                config.protocols.apt.architectures = apt_data.get("architectures", config.protocols.apt.architectures)
                config.protocols.apt.default_mirrors = apt_data.get("default_mirrors", config.protocols.apt.default_mirrors)
                
            # PyPI protocol
            if "pypi" in protocols_data:
                pypi_data = protocols_data["pypi"]
                config.protocols.pypi.enabled = pypi_data.get("enabled", config.protocols.pypi.enabled)
                config.protocols.pypi.port = pypi_data.get("port", config.protocols.pypi.port)
                config.protocols.pypi.index_url = pypi_data.get("index_url", config.protocols.pypi.index_url)
                config.protocols.pypi.python_versions = pypi_data.get("python_versions", config.protocols.pypi.python_versions)
                
        # Update other configs similarly...
        
        return config
    
    def save_to_file(self, config_path: str):
        """
        Save configuration to YAML file.
        
        Args:
            config_path: Path to save the configuration file
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        config_dict = self.to_dict()
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
            
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Configuration as dictionary
        """
        return {
            "proxy": {
                "http_port": self.proxy.http_port,
                "https_port": self.proxy.https_port,
                "bind_address": self.proxy.bind_address,
                "mode": self.proxy.mode,
            },
            "cache": {
                "root_dir": self.cache.root_dir,
                "max_size_gb": self.cache.max_size_gb,
                "expire_days": self.cache.expire_days,
                "compression": self.cache.compression,
                "compression_algorithm": self.cache.compression_algorithm,
            },
            "ssl": {
                "cert_dir": self.ssl.cert_dir,
                "ca_validity_days": self.ssl.ca_validity_days,
                "server_validity_days": self.ssl.server_validity_days,
                "organization": self.ssl.organization,
                "country": self.ssl.country,
            },
            "protocols": {
                "http": {
                    "enabled": self.protocols.http.enabled,
                    "user_agent": self.protocols.http.user_agent,
                    "timeout": self.protocols.http.timeout,
                    "max_retries": self.protocols.http.max_retries,
                },
                "git": {
                    "enabled": self.protocols.git.enabled,
                    "port": self.protocols.git.port,
                    "services": self.protocols.git.services,
                },
                "apt": {
                    "enabled": self.protocols.apt.enabled,
                    "port": self.protocols.apt.port,
                    "distributions": self.protocols.apt.distributions,
                    "architectures": self.protocols.apt.architectures,
                    "default_mirrors": self.protocols.apt.default_mirrors,
                },
                "pypi": {
                    "enabled": self.protocols.pypi.enabled,
                    "port": self.protocols.pypi.port,
                    "index_url": self.protocols.pypi.index_url,
                    "python_versions": self.protocols.pypi.python_versions,
                },
            },
            # Add other config sections as needed...
        }


def get_default_config_path() -> str:
    """
    Get the default configuration file path.
    
    Returns:
        Default config file path
    """
    return os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "config.yaml")