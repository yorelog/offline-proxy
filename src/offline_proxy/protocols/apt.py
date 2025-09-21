"""
APT package management protocol support.

This module provides APT mirror functionality for offline package installation.
"""

import os
import asyncio
import logging
import hashlib
import gzip
import bz2
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse
import tempfile

import aiohttp
import aiofiles
from aiohttp import web

from ..config import Config
from ..cache import CacheManager


logger = logging.getLogger(__name__)


class APTProtocolHandler:
    """
    Handles APT repository mirroring and offline serving.
    
    Features:
    - Mirror APT repositories locally
    - Serve packages through HTTP mirror
    - Track package dependencies
    - Support multiple distributions and architectures
    """
    
    def __init__(self, config: Config, cache_manager: CacheManager):
        self.config = config
        self.cache_manager = cache_manager
        self.mirror_dir = Path(config.cache.root_dir) / "apt_mirror"
        self.mirror_dir.mkdir(parents=True, exist_ok=True)
        
        # Supported distributions and architectures
        self.distributions = config.protocols.apt.distributions
        self.architectures = config.protocols.apt.architectures
        self.default_mirrors = config.protocols.apt.default_mirrors
        
    async def initialize(self):
        """Initialize APT protocol handler."""
        logger.info("Initializing APT protocol handler")
        
    async def mirror_repository(self, distribution: str, release: str, 
                              components: List[str] = None, 
                              architectures: List[str] = None):
        """
        Mirror an APT repository for offline use.
        
        Args:
            distribution: Distribution name (ubuntu, debian)
            release: Release name (focal, bullseye, etc.)
            components: Repository components (main, universe, etc.)
            architectures: Architectures to mirror
        """
        if components is None:
            components = ["main", "universe", "multiverse", "restricted"]
        if architectures is None:
            architectures = self.architectures
            
        base_url = self.default_mirrors.get(distribution)
        if not base_url:
            raise ValueError(f"Unknown distribution: {distribution}")
            
        logger.info(f"Mirroring {distribution} {release} repository")
        
        # Create directory structure
        dist_dir = self.mirror_dir / distribution / "dists" / release
        dist_dir.mkdir(parents=True, exist_ok=True)
        
        # Download Release file
        await self._download_release_file(base_url, release, dist_dir)
        
        # Download package indices for each component and architecture
        for component in components:
            for arch in architectures:
                await self._download_package_indices(
                    base_url, release, component, arch, dist_dir
                )
                
        # Parse packages and download .deb files
        await self._download_packages(base_url, release, components, architectures)
        
    async def _download_release_file(self, base_url: str, release: str, dist_dir: Path):
        """Download and cache the Release file."""
        release_url = urljoin(base_url, f"dists/{release}/Release")
        release_file = dist_dir / "Release"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(release_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        async with aiofiles.open(release_file, 'wb') as f:
                            await f.write(content)
                        logger.info(f"Downloaded Release file for {release}")
                    else:
                        raise aiohttp.ClientError(f"HTTP {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to download Release file: {e}")
            raise
            
    async def _download_package_indices(self, base_url: str, release: str, 
                                      component: str, arch: str, dist_dir: Path):
        """Download package indices (Packages.gz files)."""
        packages_path = f"dists/{release}/{component}/binary-{arch}/Packages.gz"
        packages_url = urljoin(base_url, packages_path)
        
        # Create component directory
        comp_dir = dist_dir / component / f"binary-{arch}"
        comp_dir.mkdir(parents=True, exist_ok=True)
        
        packages_file = comp_dir / "Packages.gz"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(packages_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        async with aiofiles.open(packages_file, 'wb') as f:
                            await f.write(content)
                        logger.info(f"Downloaded Packages.gz for {release}/{component}/{arch}")
                    else:
                        logger.warning(f"Packages.gz not found: {packages_url}")
                        
        except Exception as e:
            logger.error(f"Failed to download Packages.gz: {e}")
            
    async def _download_packages(self, base_url: str, release: str, 
                               components: List[str], architectures: List[str]):
        """Download .deb packages based on package indices."""
        for component in components:
            for arch in architectures:
                packages_file = (self.mirror_dir / "ubuntu" / "dists" / release / 
                               component / f"binary-{arch}" / "Packages.gz")
                
                if not packages_file.exists():
                    continue
                    
                # Parse packages from Packages.gz
                packages = await self._parse_packages_file(packages_file)
                
                # Download each package
                for package in packages:
                    await self._download_package_file(base_url, package)
                    
    async def _parse_packages_file(self, packages_file: Path) -> List[Dict[str, Any]]:
        """Parse Packages.gz file and extract package information."""
        packages = []
        
        try:
            with gzip.open(packages_file, 'rt', encoding='utf-8') as f:
                content = f.read()
                
            # Parse package entries
            current_package = {}
            for line in content.split('\n'):
                line = line.strip()
                
                if not line:  # Empty line indicates end of package entry
                    if current_package:
                        packages.append(current_package)
                        current_package = {}
                elif ':' in line:
                    key, value = line.split(':', 1)
                    current_package[key.strip()] = value.strip()
                    
            # Add last package if file doesn't end with empty line
            if current_package:
                packages.append(current_package)
                
        except Exception as e:
            logger.error(f"Failed to parse packages file {packages_file}: {e}")
            
        return packages
        
    async def _download_package_file(self, base_url: str, package: Dict[str, Any]):
        """Download a .deb package file."""
        if 'Filename' not in package:
            return
            
        filename = package['Filename']
        package_url = urljoin(base_url, filename)
        local_path = self.mirror_dir / "ubuntu" / filename
        
        # Create directory if it doesn't exist
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Skip if already downloaded
        if local_path.exists():
            return
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(package_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Verify checksum if available
                        if 'SHA256' in package:
                            expected_hash = package['SHA256']
                            actual_hash = hashlib.sha256(content).hexdigest()
                            if expected_hash != actual_hash:
                                logger.error(f"Checksum mismatch for {filename}")
                                return
                                
                        async with aiofiles.open(local_path, 'wb') as f:
                            await f.write(content)
                            
                        logger.debug(f"Downloaded package: {filename}")
                        
                        # Track dependency
                        await self.cache_manager.add_dependency(
                            parent_url=base_url,
                            dependency_url=package_url,
                            dependency_type="apt_package"
                        )
                        
        except Exception as e:
            logger.error(f"Failed to download package {filename}: {e}")
            
    async def create_apt_server(self, host: str = "0.0.0.0", port: int = 8081):
        """
        Create HTTP server to serve APT mirror.
        
        Args:
            host: Host to bind to
            port: Port to listen on
        """
        app = web.Application()
        
        # Add routes for APT mirror
        app.router.add_route('GET', '/{path:.*}', self._handle_apt_request)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        logger.info(f"APT mirror server started on {host}:{port}")
        
    async def _handle_apt_request(self, request):
        """Handle APT mirror requests."""
        path = request.match_info['path']
        file_path = self.mirror_dir / "ubuntu" / path
        
        if not file_path.exists():
            return web.Response(status=404, text="File not found")
            
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
                
            # Determine content type
            content_type = "application/octet-stream"
            if path.endswith('.gz'):
                content_type = "application/gzip"
            elif path.endswith('.deb'):
                content_type = "application/vnd.debian.binary-package"
            elif path.endswith('.bz2'):
                content_type = "application/x-bzip2"
                
            return web.Response(
                body=content,
                headers={'Content-Type': content_type}
            )
            
        except Exception as e:
            logger.error(f"Error serving file {path}: {e}")
            return web.Response(status=500, text="Internal server error")
            
    async def get_available_packages(self, distribution: str, release: str) -> List[Dict[str, Any]]:
        """Get list of available packages in the mirror."""
        packages = []
        
        dist_dir = self.mirror_dir / distribution / "dists" / release
        if not dist_dir.exists():
            return packages
            
        # Search for Packages.gz files
        for packages_file in dist_dir.rglob("Packages.gz"):
            try:
                file_packages = await self._parse_packages_file(packages_file)
                packages.extend(file_packages)
            except Exception as e:
                logger.error(f"Failed to parse {packages_file}: {e}")
                
        return packages
        
    async def search_packages(self, query: str, distribution: str = "ubuntu", 
                            release: str = "focal") -> List[Dict[str, Any]]:
        """Search for packages by name or description."""
        all_packages = await self.get_available_packages(distribution, release)
        
        matching_packages = []
        query_lower = query.lower()
        
        for package in all_packages:
            package_name = package.get('Package', '').lower()
            description = package.get('Description', '').lower()
            
            if query_lower in package_name or query_lower in description:
                matching_packages.append(package)
                
        return matching_packages
        
    async def get_package_dependencies(self, package_name: str, 
                                     distribution: str = "ubuntu", 
                                     release: str = "focal") -> List[str]:
        """Get dependencies for a specific package."""
        all_packages = await self.get_available_packages(distribution, release)
        
        for package in all_packages:
            if package.get('Package') == package_name:
                depends = package.get('Depends', '')
                if depends:
                    # Parse dependency string
                    deps = []
                    for dep in depends.split(','):
                        dep = dep.strip()
                        # Remove version constraints
                        dep_name = dep.split('(')[0].strip()
                        deps.append(dep_name)
                    return deps
                    
        return []
        
    async def get_mirror_stats(self) -> Dict[str, Any]:
        """Get APT mirror statistics."""
        stats = {
            "mirror_dir": str(self.mirror_dir),
            "distributions": {},
            "total_size_bytes": 0,
            "total_packages": 0
        }
        
        # Calculate statistics for each distribution
        for dist_dir in self.mirror_dir.iterdir():
            if dist_dir.is_dir():
                dist_name = dist_dir.name
                dist_stats = {
                    "size_bytes": 0,
                    "packages": 0,
                    "releases": []
                }
                
                # Count packages and calculate size
                for file_path in dist_dir.rglob("*.deb"):
                    dist_stats["packages"] += 1
                    try:
                        dist_stats["size_bytes"] += file_path.stat().st_size
                    except OSError:
                        pass
                        
                # Find releases
                dists_dir = dist_dir / "dists"
                if dists_dir.exists():
                    dist_stats["releases"] = [
                        release.name for release in dists_dir.iterdir() 
                        if release.is_dir()
                    ]
                    
                stats["distributions"][dist_name] = dist_stats
                stats["total_size_bytes"] += dist_stats["size_bytes"]
                stats["total_packages"] += dist_stats["packages"]
                
        return stats