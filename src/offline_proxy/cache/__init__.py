"""
Cache management module for storing and retrieving network resources.

This module handles caching of HTTP responses, dependency tracking,
and resource management.
"""

import os
import json
import hashlib
import sqlite3
import asyncio
import aiofiles
import zstandard as zstd
import lz4.frame
import gzip
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from ..config import Config


class CacheManager:
    """
    Manages caching of network resources and their metadata.
    
    Features:
    - File-based storage with compression
    - SQLite metadata database
    - Dependency tracking
    - Cache expiration and cleanup
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.cache_dir = Path(config.cache.root_dir)
        self.db_path = self.cache_dir / "metadata.db"
        self.connection: Optional[sqlite3.Connection] = None
        
        # Compression setup
        self.compression_enabled = config.cache.compression
        self.compression_algorithm = config.cache.compression_algorithm
        
        if self.compression_algorithm == "zstd":
            self.compressor = zstd.ZstdCompressor(level=3)
            self.decompressor = zstd.ZstdDecompressor()
        elif self.compression_algorithm == "lz4":
            # lz4 doesn't need explicit compressor objects
            pass
        elif self.compression_algorithm == "gzip":
            # gzip doesn't need explicit compressor objects
            pass
            
    async def initialize(self):
        """Initialize the cache manager."""
        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        await self._init_database()
        
    async def close(self):
        """Close the cache manager."""
        if self.connection:
            self.connection.close()
            
    async def _init_database(self):
        """Initialize the SQLite database for metadata."""
        self.connection = sqlite3.connect(str(self.db_path))
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                cache_key TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                headers TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                accessed_at TIMESTAMP NOT NULL,
                size_bytes INTEGER NOT NULL,
                compressed BOOLEAN NOT NULL,
                compression_algorithm TEXT
            )
        """)
        
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_url TEXT NOT NULL,
                dependency_url TEXT NOT NULL,
                dependency_type TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
        """)
        
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_entries_url ON cache_entries(url);
        """)
        
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_entries_created_at ON cache_entries(created_at);
        """)
        
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_dependencies_parent ON dependencies(parent_url);
        """)
        
        self.connection.commit()
        
    def generate_cache_key(self, method: str, url: str, headers: Dict[str, str]) -> str:
        """
        Generate a unique cache key for a request.
        
        Args:
            method: HTTP method
            url: Request URL
            headers: Request headers
            
        Returns:
            Unique cache key
        """
        # Create a deterministic key based on method, URL, and relevant headers
        relevant_headers = {
            k.lower(): v for k, v in headers.items()
            if k.lower() in ['authorization', 'accept', 'accept-encoding', 'user-agent']
        }
        
        key_data = f"{method}:{url}:{json.dumps(relevant_headers, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()
        
    async def get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached response.
        
        Args:
            cache_key: Cache key to look up
            
        Returns:
            Cached response data or None if not found
        """
        if not self.connection:
            return None
            
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT url, method, status_code, headers, file_path, created_at, 
                   size_bytes, compressed, compression_algorithm
            FROM cache_entries 
            WHERE cache_key = ?
        """, (cache_key,))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        url, method, status_code, headers_json, file_path, created_at, \
        size_bytes, compressed, compression_algorithm = row
        
        # Update access time
        cursor.execute("""
            UPDATE cache_entries 
            SET accessed_at = ? 
            WHERE cache_key = ?
        """, (datetime.now(), cache_key))
        self.connection.commit()
        
        # Read the cached file
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                # File was deleted, remove from database
                cursor.execute("DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,))
                self.connection.commit()
                return None
                
            async with aiofiles.open(file_path, 'rb') as f:
                body = await f.read()
                
            # Decompress if needed
            if compressed and compression_algorithm:
                body = self._decompress_data(body, compression_algorithm)
                
            return {
                "status": status_code,
                "headers": json.loads(headers_json),
                "body": body,
                "url": url,
                "cached_at": created_at
            }
            
        except Exception as e:
            # Error reading file, remove from database
            cursor.execute("DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,))
            self.connection.commit()
            return None
            
    async def cache_response(self, cache_key: str, status: int, headers: Dict[str, str], 
                           body: bytes, url: str):
        """
        Cache a response.
        
        Args:
            cache_key: Cache key
            status: HTTP status code
            headers: Response headers
            body: Response body
            url: Request URL
        """
        if not self.connection:
            return
            
        # Create file path
        file_name = f"{cache_key}.cache"
        file_path = self.cache_dir / "responses" / file_name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Compress data if enabled
        compressed = False
        compression_algorithm = None
        if self.compression_enabled and len(body) > 1024:  # Only compress if > 1KB
            compressed_body = self._compress_data(body, self.compression_algorithm)
            if len(compressed_body) < len(body):  # Only use if compression is beneficial
                body = compressed_body
                compressed = True
                compression_algorithm = self.compression_algorithm
                
        # Write to file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(body)
            
        # Store metadata in database
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO cache_entries 
            (cache_key, url, method, status_code, headers, file_path, 
             created_at, accessed_at, size_bytes, compressed, compression_algorithm)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cache_key, url, "GET", status, json.dumps(headers), str(file_path),
            datetime.now(), datetime.now(), len(body), compressed, compression_algorithm
        ))
        self.connection.commit()
        
    def _compress_data(self, data: bytes, algorithm: str) -> bytes:
        """Compress data using the specified algorithm."""
        if algorithm == "zstd":
            return self.compressor.compress(data)
        elif algorithm == "lz4":
            return lz4.frame.compress(data)
        elif algorithm == "gzip":
            return gzip.compress(data)
        else:
            return data
            
    def _decompress_data(self, data: bytes, algorithm: str) -> bytes:
        """Decompress data using the specified algorithm."""
        if algorithm == "zstd":
            return self.decompressor.decompress(data)
        elif algorithm == "lz4":
            return lz4.frame.decompress(data)
        elif algorithm == "gzip":
            return gzip.decompress(data)
        else:
            return data
            
    async def add_dependency(self, parent_url: str, dependency_url: str, dependency_type: str):
        """
        Add a dependency relationship.
        
        Args:
            parent_url: URL of the parent resource
            dependency_url: URL of the dependency
            dependency_type: Type of dependency (css, js, image, etc.)
        """
        if not self.connection:
            return
            
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO dependencies 
            (parent_url, dependency_url, dependency_type, created_at)
            VALUES (?, ?, ?, ?)
        """, (parent_url, dependency_url, dependency_type, datetime.now()))
        self.connection.commit()
        
    async def get_dependencies(self, parent_url: str) -> List[Dict[str, str]]:
        """
        Get all dependencies for a URL.
        
        Args:
            parent_url: URL to get dependencies for
            
        Returns:
            List of dependency information
        """
        if not self.connection:
            return []
            
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT dependency_url, dependency_type, created_at
            FROM dependencies
            WHERE parent_url = ?
            ORDER BY created_at
        """, (parent_url,))
        
        return [
            {
                "url": row[0],
                "type": row[1],
                "created_at": row[2]
            }
            for row in cursor.fetchall()
        ]
        
    async def cleanup_expired_cache(self):
        """Clean up expired cache entries."""
        if not self.connection:
            return
            
        expire_date = datetime.now() - timedelta(days=self.config.cache.expire_days)
        
        cursor = self.connection.cursor()
        
        # Get expired entries
        cursor.execute("""
            SELECT cache_key, file_path
            FROM cache_entries
            WHERE created_at < ?
        """, (expire_date,))
        
        expired_entries = cursor.fetchall()
        
        # Delete files and database entries
        for cache_key, file_path in expired_entries:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass  # File already deleted or permission error
                
            cursor.execute("DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,))
            
        self.connection.commit()
        
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.connection:
            return {}
            
        cursor = self.connection.cursor()
        
        # Total entries
        cursor.execute("SELECT COUNT(*) FROM cache_entries")
        total_entries = cursor.fetchone()[0]
        
        # Total size
        cursor.execute("SELECT SUM(size_bytes) FROM cache_entries")
        total_size = cursor.fetchone()[0] or 0
        
        # Entries by status code
        cursor.execute("""
            SELECT status_code, COUNT(*) 
            FROM cache_entries 
            GROUP BY status_code
            ORDER BY status_code
        """)
        status_counts = dict(cursor.fetchall())
        
        return {
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "status_counts": status_counts,
            "cache_dir": str(self.cache_dir),
            "compression_enabled": self.compression_enabled,
            "compression_algorithm": self.compression_algorithm
        }