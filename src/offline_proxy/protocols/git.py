"""
Git protocol support for offline proxy.

This module provides Git repository caching and offline serving capabilities.
"""

import os
import asyncio
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
import tempfile

import git
from dulwich import porcelain
from dulwich.repo import Repo as DulwichRepo

from ..config import Config
from ..cache import CacheManager


logger = logging.getLogger(__name__)


class GitProtocolHandler:
    """
    Handles Git protocol operations for caching and offline serving.
    
    Features:
    - Clone repositories and cache them locally
    - Serve repositories through Git protocol
    - Track repository dependencies and submodules
    - Support for multiple Git hosting services
    """
    
    def __init__(self, config: Config, cache_manager: CacheManager):
        self.config = config
        self.cache_manager = cache_manager
        self.repos_dir = Path(config.cache.root_dir) / "git_repos"
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        
    async def initialize(self):
        """Initialize Git protocol handler."""
        logger.info("Initializing Git protocol handler")
        
    async def cache_repository(self, git_url: str, branch: str = "main") -> str:
        """
        Cache a Git repository locally.
        
        Args:
            git_url: Git repository URL
            branch: Branch to cache (default: main)
            
        Returns:
            Local path to cached repository
        """
        repo_key = self._generate_repo_key(git_url)
        repo_path = self.repos_dir / repo_key
        
        if repo_path.exists():
            # Repository already cached, update it
            logger.info(f"Updating cached repository: {git_url}")
            await self._update_repository(repo_path, branch)
        else:
            # Clone repository
            logger.info(f"Caching repository: {git_url}")
            await self._clone_repository(git_url, repo_path, branch)
            
        # Cache repository metadata
        await self._cache_repository_metadata(git_url, repo_path)
        
        # Discover and cache submodules
        await self._cache_submodules(repo_path, git_url)
        
        return str(repo_path)
        
    async def _clone_repository(self, git_url: str, repo_path: Path, branch: str):
        """Clone a repository to local path."""
        try:
            # Use GitPython for cloning with progress
            repo = git.Repo.clone_from(
                git_url,
                str(repo_path),
                branch=branch,
                depth=1,  # Shallow clone to save space
                single_branch=True
            )
            logger.info(f"Successfully cloned {git_url} to {repo_path}")
            
        except git.GitCommandError as e:
            logger.error(f"Failed to clone {git_url}: {e}")
            # Cleanup on failure
            if repo_path.exists():
                shutil.rmtree(repo_path)
            raise
            
    async def _update_repository(self, repo_path: Path, branch: str):
        """Update an existing repository."""
        try:
            repo = git.Repo(str(repo_path))
            
            # Fetch latest changes
            origin = repo.remotes.origin
            origin.fetch()
            
            # Reset to latest commit
            repo.git.reset('--hard', f'origin/{branch}')
            
            logger.info(f"Successfully updated repository at {repo_path}")
            
        except git.GitCommandError as e:
            logger.error(f"Failed to update repository at {repo_path}: {e}")
            raise
            
    async def _cache_repository_metadata(self, git_url: str, repo_path: Path):
        """Cache repository metadata in the cache manager."""
        try:
            repo = git.Repo(str(repo_path))
            
            metadata = {
                "url": git_url,
                "path": str(repo_path),
                "head_commit": repo.head.commit.hexsha,
                "last_commit_date": repo.head.commit.committed_datetime.isoformat(),
                "branches": [str(ref).split('/')[-1] for ref in repo.refs if 'origin' in str(ref)],
                "tags": [str(tag) for tag in repo.tags],
                "size_bytes": self._get_directory_size(repo_path)
            }
            
            # Store metadata
            cache_key = f"git_metadata:{self._generate_repo_key(git_url)}"
            await self.cache_manager.cache_response(
                cache_key=cache_key,
                status=200,
                headers={"Content-Type": "application/json"},
                body=str(metadata).encode(),
                url=git_url
            )
            
        except Exception as e:
            logger.error(f"Failed to cache metadata for {git_url}: {e}")
            
    async def _cache_submodules(self, repo_path: Path, parent_url: str):
        """Discover and cache Git submodules."""
        try:
            repo = git.Repo(str(repo_path))
            
            # Check if repository has submodules
            gitmodules_path = repo_path / ".gitmodules"
            if not gitmodules_path.exists():
                return
                
            # Parse .gitmodules file
            config = repo.config_reader()
            submodules = []
            
            for section_name in config.sections():
                if section_name.startswith('submodule'):
                    submodule_name = section_name.split('"')[1]
                    submodule_url = config.get(section_name, 'url')
                    submodule_path = config.get(section_name, 'path')
                    
                    submodules.append({
                        "name": submodule_name,
                        "url": submodule_url,
                        "path": submodule_path
                    })
                    
                    # Add dependency relationship
                    await self.cache_manager.add_dependency(
                        parent_url=parent_url,
                        dependency_url=submodule_url,
                        dependency_type="git_submodule"
                    )
                    
            # Cache submodules recursively
            for submodule in submodules:
                try:
                    await self.cache_repository(submodule["url"])
                except Exception as e:
                    logger.warning(f"Failed to cache submodule {submodule['url']}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to process submodules for {parent_url}: {e}")
            
    def _generate_repo_key(self, git_url: str) -> str:
        """Generate a unique key for a Git repository."""
        parsed = urlparse(git_url)
        # Remove .git suffix if present
        path = parsed.path.rstrip('.git')
        return f"{parsed.netloc}{path}".replace('/', '_').replace(':', '_')
        
    def _get_directory_size(self, path: Path) -> int:
        """Get total size of directory in bytes."""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    pass  # Skip files that can't be accessed
        return total_size
        
    async def get_cached_repositories(self) -> List[Dict[str, Any]]:
        """Get list of all cached repositories."""
        repositories = []
        
        for repo_dir in self.repos_dir.iterdir():
            if repo_dir.is_dir() and (repo_dir / ".git").exists():
                try:
                    repo = git.Repo(str(repo_dir))
                    remote_url = None
                    
                    # Get remote URL
                    if repo.remotes:
                        remote_url = repo.remotes.origin.url
                        
                    repositories.append({
                        "name": repo_dir.name,
                        "path": str(repo_dir),
                        "url": remote_url,
                        "head_commit": repo.head.commit.hexsha,
                        "last_commit_date": repo.head.commit.committed_datetime.isoformat(),
                        "size_bytes": self._get_directory_size(repo_dir)
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to get info for repository {repo_dir}: {e}")
                    
        return repositories
        
    async def create_git_server(self, host: str = "0.0.0.0", port: int = 9418):
        """
        Start a Git daemon to serve cached repositories.
        
        Args:
            host: Host to bind to
            port: Port to listen on
        """
        # This would require implementing a Git protocol server
        # For now, we'll use simple HTTP serving of bare repositories
        logger.info(f"Git server functionality would be implemented here")
        logger.info(f"Would serve repositories from {self.repos_dir} on {host}:{port}")
        
    async def convert_to_bare_repository(self, repo_path: Path) -> Path:
        """
        Convert a regular repository to bare repository for serving.
        
        Args:
            repo_path: Path to the regular repository
            
        Returns:
            Path to the bare repository
        """
        bare_repo_path = repo_path.parent / f"{repo_path.name}.git"
        
        if bare_repo_path.exists():
            return bare_repo_path
            
        try:
            # Clone as bare repository
            repo = git.Repo(str(repo_path))
            repo.clone(str(bare_repo_path), bare=True)
            
            logger.info(f"Created bare repository at {bare_repo_path}")
            return bare_repo_path
            
        except Exception as e:
            logger.error(f"Failed to create bare repository: {e}")
            raise
            
    async def extract_git_dependencies(self, repo_path: Path) -> List[str]:
        """
        Extract Git-related dependencies from repository files.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            List of dependency URLs
        """
        dependencies = []
        
        try:
            # Check common dependency files
            dependency_files = [
                "requirements.txt",  # Python
                "package.json",      # Node.js
                "Gemfile",          # Ruby
                "go.mod",           # Go
                "Cargo.toml",       # Rust
                "pom.xml",          # Maven
                "build.gradle",     # Gradle
                ".gitmodules",      # Git submodules
            ]
            
            for dep_file in dependency_files:
                dep_path = repo_path / dep_file
                if dep_path.exists():
                    deps = await self._parse_dependency_file(dep_path, dep_file)
                    dependencies.extend(deps)
                    
        except Exception as e:
            logger.error(f"Failed to extract dependencies from {repo_path}: {e}")
            
        return dependencies
        
    async def _parse_dependency_file(self, file_path: Path, file_type: str) -> List[str]:
        """Parse a dependency file and extract URLs."""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if file_type == "requirements.txt":
                # Extract PyPI packages
                for line in content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        package_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0]
                        dependencies.append(f"https://pypi.org/project/{package_name}/")
                        
            elif file_type == "package.json":
                # Extract npm packages
                import json
                data = json.loads(content)
                for dep_type in ['dependencies', 'devDependencies']:
                    if dep_type in data:
                        for package_name in data[dep_type]:
                            dependencies.append(f"https://www.npmjs.com/package/{package_name}")
                            
            elif file_type == ".gitmodules":
                # Extract Git submodules
                import configparser
                config = configparser.ConfigParser()
                config.read_string(content)
                
                for section in config.sections():
                    if 'url' in config[section]:
                        dependencies.append(config[section]['url'])
                        
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            
        return dependencies