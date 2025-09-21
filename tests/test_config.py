"""
Tests for configuration management.
"""

import pytest
import tempfile
import os
from pathlib import Path

from offline_proxy.config import Config, get_default_config_path


class TestConfig:
    """Test configuration management."""
    
    def test_default_config(self):
        """Test default configuration creation."""
        config = Config()
        
        assert config.proxy.http_port == 8080
        assert config.proxy.https_port == 8443
        assert config.proxy.mode == "cache"
        assert config.cache.max_size_gb == 50
        assert config.ssl.organization == "Offline Proxy"
        
    def test_config_to_dict(self):
        """Test configuration to dictionary conversion."""
        config = Config()
        config_dict = config.to_dict()
        
        assert "proxy" in config_dict
        assert "cache" in config_dict
        assert "ssl" in config_dict
        assert "protocols" in config_dict
        
        assert config_dict["proxy"]["http_port"] == 8080
        assert config_dict["cache"]["max_size_gb"] == 50
        
    def test_config_save_and_load(self):
        """Test configuration save and load."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "test_config.yaml")
            
            # Create and save config
            config = Config()
            config.proxy.http_port = 9080
            config.cache.max_size_gb = 100
            config.save_to_file(config_path)
            
            # Load config
            loaded_config = Config.load_from_file(config_path)
            
            assert loaded_config.proxy.http_port == 9080
            assert loaded_config.cache.max_size_gb == 100
            
    def test_config_load_nonexistent_file(self):
        """Test loading config from non-existent file returns default."""
        config = Config.load_from_file("nonexistent.yaml")
        
        # Should return default config
        assert config.proxy.http_port == 8080
        assert config.proxy.mode == "cache"
        
    def test_get_default_config_path(self):
        """Test getting default config path."""
        config_path = get_default_config_path()
        assert config_path.endswith("config.yaml")
        
    def test_protocol_configurations(self):
        """Test protocol-specific configurations."""
        config = Config()
        
        # Test HTTP protocol config
        assert config.protocols.http.enabled is True
        assert config.protocols.http.timeout == 30
        
        # Test Git protocol config
        assert config.protocols.git.enabled is True
        assert "github.com" in config.protocols.git.services
        
        # Test APT protocol config
        assert config.protocols.apt.enabled is True
        assert "ubuntu" in config.protocols.apt.distributions
        
        # Test PyPI protocol config
        assert config.protocols.pypi.enabled is True
        assert config.protocols.pypi.index_url == "https://pypi.org/simple/"