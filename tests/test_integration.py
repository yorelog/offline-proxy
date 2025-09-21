"""
Basic integration tests for the offline proxy.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path

from offline_proxy.config import Config
from offline_proxy.cache import CacheManager


class TestIntegration:
    """Integration tests for offline proxy components."""
    
    @pytest.fixture
    def temp_config(self):
        """Create a temporary configuration for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.cache.root_dir = temp_dir
            config.ssl.cert_dir = os.path.join(temp_dir, "certs")
            yield config
            
    @pytest.mark.asyncio
    async def test_cache_manager_initialization(self, temp_config):
        """Test cache manager initialization."""
        cache_manager = CacheManager(temp_config)
        
        await cache_manager.initialize()
        
        # Check that database file was created
        db_path = Path(temp_config.cache.root_dir) / "metadata.db"
        assert db_path.exists()
        
        await cache_manager.close()
        
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, temp_config):
        """Test cache key generation."""
        cache_manager = CacheManager(temp_config)
        
        key1 = cache_manager.generate_cache_key("GET", "https://example.com", {})
        key2 = cache_manager.generate_cache_key("GET", "https://example.com", {})
        key3 = cache_manager.generate_cache_key("POST", "https://example.com", {})
        
        # Same method and URL should generate same key
        assert key1 == key2
        
        # Different method should generate different key
        assert key1 != key3
        
    @pytest.mark.asyncio
    async def test_cache_store_and_retrieve(self, temp_config):
        """Test storing and retrieving cached responses."""
        cache_manager = CacheManager(temp_config)
        await cache_manager.initialize()
        
        try:
            # Store a response
            cache_key = "test_key"
            headers = {"Content-Type": "text/plain"}
            body = b"Hello, World!"
            
            await cache_manager.cache_response(
                cache_key=cache_key,
                status=200,
                headers=headers,
                body=body,
                url="https://example.com"
            )
            
            # Retrieve the response
            cached_response = await cache_manager.get_cached_response(cache_key)
            
            assert cached_response is not None
            assert cached_response["status"] == 200
            assert cached_response["headers"] == headers
            assert cached_response["body"] == body
            assert cached_response["url"] == "https://example.com"
            
        finally:
            await cache_manager.close()
            
    @pytest.mark.asyncio
    async def test_cache_stats(self, temp_config):
        """Test cache statistics."""
        cache_manager = CacheManager(temp_config)
        await cache_manager.initialize()
        
        try:
            # Initially should have no entries
            stats = await cache_manager.get_cache_stats()
            assert stats["total_entries"] == 0
            assert stats["total_size_bytes"] == 0
            
            # Add some cached responses
            for i in range(3):
                await cache_manager.cache_response(
                    cache_key=f"test_key_{i}",
                    status=200,
                    headers={"Content-Type": "text/plain"},
                    body=f"Response {i}".encode(),
                    url=f"https://example.com/{i}"
                )
                
            # Check stats again
            stats = await cache_manager.get_cache_stats()
            assert stats["total_entries"] == 3
            assert stats["total_size_bytes"] > 0
            
        finally:
            await cache_manager.close()
            
    def test_config_override(self):
        """Test configuration override functionality."""
        config = Config()
        
        # Test default values
        assert config.proxy.http_port == 8080
        assert config.proxy.mode == "cache"
        
        # Test that we can override values
        config.proxy.http_port = 9090
        config.proxy.mode = "offline"
        
        assert config.proxy.http_port == 9090
        assert config.proxy.mode == "offline"