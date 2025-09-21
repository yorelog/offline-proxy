"""
PyPI (Python Package Index) protocol support.

This module provides PyPI mirror functionality for offline Python package installation.
"""

import os
import asyncio
import logging
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urljoin, urlparse
import tempfile
import tarfile
import zipfile

import aiohttp
import aiofiles
from aiohttp import web

from ..config import Config
from ..cache import CacheManager


logger = logging.getLogger(__name__)


class PyPIProtocolHandler:
    """
    Handles PyPI repository mirroring and offline serving.
    
    Features:
    - Mirror PyPI packages locally
    - Serve packages through PyPI-compatible API
    - Track package dependencies
    - Support for wheels and source distributions
    """
    
    def __init__(self, config: Config, cache_manager: CacheManager):
        self.config = config
        self.cache_manager = cache_manager
        self.mirror_dir = Path(config.cache.root_dir) / "pypi_mirror"
        self.mirror_dir.mkdir(parents=True, exist_ok=True)
        
        # PyPI configuration
        self.index_url = config.protocols.pypi.index_url
        self.python_versions = config.protocols.pypi.python_versions
        
        # Create directory structure
        self.packages_dir = self.mirror_dir / "packages"
        self.simple_dir = self.mirror_dir / "simple"
        self.metadata_dir = self.mirror_dir / "metadata"
        
        for dir_path in [self.packages_dir, self.simple_dir, self.metadata_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            
    async def initialize(self):
        """Initialize PyPI protocol handler."""
        logger.info("Initializing PyPI protocol handler")
        
    async def mirror_package(self, package_name: str, version: str = None, 
                           include_dependencies: bool = True) -> Dict[str, Any]:
        """
        Mirror a Python package and optionally its dependencies.
        
        Args:
            package_name: Name of the package to mirror
            version: Specific version to mirror (None for latest)
            include_dependencies: Whether to mirror dependencies
            
        Returns:
            Dictionary with mirror information
        """
        logger.info(f"Mirroring package: {package_name}")
        
        # Get package metadata from PyPI
        metadata = await self._get_package_metadata(package_name)
        if not metadata:
            raise ValueError(f"Package not found: {package_name}")
            
        # Determine version to mirror
        if version is None:
            version = metadata['info']['version']
            
        if version not in metadata['releases']:
            raise ValueError(f"Version {version} not found for {package_name}")
            
        # Mirror the specific version
        release_info = metadata['releases'][version]
        mirrored_files = await self._mirror_package_files(package_name, version, release_info)
        
        # Create simple index page
        await self._create_simple_index(package_name, metadata)
        
        # Mirror dependencies if requested
        dependencies = []
        if include_dependencies:
            dependencies = await self._mirror_dependencies(package_name, version, metadata)
            
        return {
            "package_name": package_name,
            "version": version,
            "mirrored_files": mirrored_files,
            "dependencies": dependencies
        }
        
    async def _get_package_metadata(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Get package metadata from PyPI JSON API."""
        api_url = f"https://pypi.org/pypi/{package_name}/json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Failed to get metadata for {package_name}: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting metadata for {package_name}: {e}")
            return None
            
    async def _mirror_package_files(self, package_name: str, version: str, 
                                  release_info: List[Dict[str, Any]]) -> List[str]:
        """Mirror package files (wheels and source distributions)."""
        mirrored_files = []
        
        for file_info in release_info:
            filename = file_info['filename']
            url = file_info['url']
            
            # Create package directory
            package_dir = self.packages_dir / package_name
            package_dir.mkdir(exist_ok=True)
            
            file_path = package_dir / filename
            
            # Skip if already downloaded
            if file_path.exists():
                # Verify hash if available
                if await self._verify_file_hash(file_path, file_info):
                    mirrored_files.append(filename)
                    continue
                    
            # Download file
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content = await response.read()
                            
                            # Verify hash
                            if not self._verify_content_hash(content, file_info):
                                logger.error(f"Hash verification failed for {filename}")
                                continue
                                
                            async with aiofiles.open(file_path, 'wb') as f:
                                await f.write(content)
                                
                            mirrored_files.append(filename)
                            logger.debug(f"Downloaded: {filename}")
                            
                            # Track dependency
                            await self.cache_manager.add_dependency(
                                parent_url="pypi",
                                dependency_url=url,
                                dependency_type="python_package"
                            )
                            
            except Exception as e:
                logger.error(f"Failed to download {filename}: {e}")
                
        return mirrored_files
        
    async def _verify_file_hash(self, file_path: Path, file_info: Dict[str, Any]) -> bool:
        """Verify downloaded file hash."""
        if 'digests' not in file_info:
            return True  # No hash to verify
            
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
            return self._verify_content_hash(content, file_info)
        except Exception:
            return False
            
    def _verify_content_hash(self, content: bytes, file_info: Dict[str, Any]) -> bool:
        """Verify content hash against expected values."""
        if 'digests' not in file_info:
            return True
            
        digests = file_info['digests']
        
        # Check SHA256 if available
        if 'sha256' in digests:
            expected = digests['sha256']
            actual = hashlib.sha256(content).hexdigest()
            return expected == actual
            
        # Check MD5 if available
        if 'md5' in digests:
            expected = digests['md5']
            actual = hashlib.md5(content).hexdigest()
            return expected == actual
            
        return True
        
    async def _create_simple_index(self, package_name: str, metadata: Dict[str, Any]):
        """Create simple index page for package."""
        simple_package_dir = self.simple_dir / package_name
        simple_package_dir.mkdir(exist_ok=True)
        
        index_file = simple_package_dir / "index.html"
        
        # Generate HTML content
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Links for {package_name}</title>
</head>
<body>
    <h1>Links for {package_name}</h1>
"""
        
        # Add links for all available versions
        for version, files in metadata['releases'].items():
            for file_info in files:
                filename = file_info['filename']
                # Use local URL
                file_url = f"../../packages/{package_name}/{filename}"
                html_content += f'    <a href="{file_url}">{filename}</a><br>\n'
                
        html_content += """</body>
</html>"""
        
        async with aiofiles.open(index_file, 'w', encoding='utf-8') as f:
            await f.write(html_content)
            
    async def _mirror_dependencies(self, package_name: str, version: str, 
                                 metadata: Dict[str, Any]) -> List[str]:
        """Mirror package dependencies recursively."""
        dependencies = []
        
        try:
            # Get dependencies from package metadata
            requires_dist = metadata['info'].get('requires_dist', [])
            if not requires_dist:
                return dependencies
                
            for requirement in requires_dist:
                # Parse requirement string (simplified parsing)
                dep_name = requirement.split()[0].split('>=')[0].split('==')[0].split('>')[0].split('<')[0]
                dep_name = dep_name.strip()
                
                # Skip if already processed
                if dep_name in dependencies:
                    continue
                    
                try:
                    # Mirror dependency
                    await self.mirror_package(dep_name, include_dependencies=False)
                    dependencies.append(dep_name)
                    
                    # Add dependency relationship
                    await self.cache_manager.add_dependency(
                        parent_url=f"pypi:{package_name}",
                        dependency_url=f"pypi:{dep_name}",
                        dependency_type="python_dependency"
                    )
                    
                except Exception as e:
                    logger.warning(f"Failed to mirror dependency {dep_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to process dependencies for {package_name}: {e}")
            
        return dependencies
        
    async def mirror_requirements_file(self, requirements_file: str) -> Dict[str, Any]:
        """
        Mirror packages from a requirements.txt file.
        
        Args:
            requirements_file: Path to requirements.txt file
            
        Returns:
            Dictionary with mirror results
        """
        results = {
            "mirrored_packages": [],
            "failed_packages": [],
            "total_packages": 0
        }
        
        try:
            with open(requirements_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                # Parse package name and version
                if '==' in line:
                    package_name, version = line.split('==', 1)
                else:
                    package_name = line.split('>=')[0].split('>')[0].split('<')[0]
                    version = None
                    
                package_name = package_name.strip()
                results["total_packages"] += 1
                
                try:
                    await self.mirror_package(package_name, version)
                    results["mirrored_packages"].append(package_name)
                except Exception as e:
                    logger.error(f"Failed to mirror {package_name}: {e}")
                    results["failed_packages"].append(package_name)
                    
        except Exception as e:
            logger.error(f"Failed to process requirements file: {e}")
            
        return results
        
    async def create_pypi_server(self, host: str = "0.0.0.0", port: int = 8082):
        """
        Create HTTP server to serve PyPI mirror.
        
        Args:
            host: Host to bind to
            port: Port to listen on
        """
        app = web.Application()
        
        # Add routes for PyPI mirror
        app.router.add_route('GET', '/simple/', self._handle_simple_index)
        app.router.add_route('GET', '/simple/{package}/', self._handle_package_index)
        app.router.add_route('GET', '/packages/{package}/{filename}', self._handle_package_file)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        logger.info(f"PyPI mirror server started on {host}:{port}")
        
    async def _handle_simple_index(self, request):
        """Handle requests to /simple/ (package index)."""
        # Generate simple index with all available packages
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Simple Index</title>
</head>
<body>
    <h1>Simple Index</h1>
"""
        
        # List all packages
        for package_dir in self.simple_dir.iterdir():
            if package_dir.is_dir():
                package_name = package_dir.name
                html_content += f'    <a href="{package_name}/">{package_name}</a><br>\n'
                
        html_content += """</body>
</html>"""
        
        return web.Response(text=html_content, content_type='text/html')
        
    async def _handle_package_index(self, request):
        """Handle requests to /simple/{package}/."""
        package_name = request.match_info['package']
        index_file = self.simple_dir / package_name / "index.html"
        
        if not index_file.exists():
            return web.Response(status=404, text="Package not found")
            
        try:
            async with aiofiles.open(index_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            return web.Response(text=content, content_type='text/html')
        except Exception as e:
            logger.error(f"Error serving package index {package_name}: {e}")
            return web.Response(status=500, text="Internal server error")
            
    async def _handle_package_file(self, request):
        """Handle requests to /packages/{package}/{filename}."""
        package_name = request.match_info['package']
        filename = request.match_info['filename']
        
        file_path = self.packages_dir / package_name / filename
        
        if not file_path.exists():
            return web.Response(status=404, text="File not found")
            
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
                
            # Determine content type
            content_type = "application/octet-stream"
            if filename.endswith('.whl'):
                content_type = "application/zip"
            elif filename.endswith('.tar.gz'):
                content_type = "application/gzip"
                
            return web.Response(
                body=content,
                headers={'Content-Type': content_type}
            )
            
        except Exception as e:
            logger.error(f"Error serving file {filename}: {e}")
            return web.Response(status=500, text="Internal server error")
            
    async def get_mirrored_packages(self) -> List[Dict[str, Any]]:
        """Get list of all mirrored packages."""
        packages = []
        
        for package_dir in self.packages_dir.iterdir():
            if package_dir.is_dir():
                package_info = {
                    "name": package_dir.name,
                    "files": [],
                    "total_size": 0
                }
                
                for file_path in package_dir.iterdir():
                    if file_path.is_file():
                        file_info = {
                            "filename": file_path.name,
                            "size": file_path.stat().st_size
                        }
                        package_info["files"].append(file_info)
                        package_info["total_size"] += file_info["size"]
                        
                packages.append(package_info)
                
        return packages
        
    async def get_mirror_stats(self) -> Dict[str, Any]:
        """Get PyPI mirror statistics."""
        packages = await self.get_mirrored_packages()
        
        stats = {
            "mirror_dir": str(self.mirror_dir),
            "total_packages": len(packages),
            "total_files": sum(len(pkg["files"]) for pkg in packages),
            "total_size_bytes": sum(pkg["total_size"] for pkg in packages),
            "packages": packages
        }
        
        return stats