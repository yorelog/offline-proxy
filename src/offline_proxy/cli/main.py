"""
Main CLI entry point for offline proxy.

This module provides the command-line interface for managing the offline proxy.
"""

import asyncio
import logging
import sys
from pathlib import Path

import click
from colorama import init as colorama_init

from ..config import Config, get_default_config_path
from ..proxy import ProxyServer
from ..protocols import GitProtocolHandler, APTProtocolHandler, PyPIProtocolHandler


# Initialize colorama for colored output
colorama_init()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
@click.option('--config', '-c', type=click.Path(), 
              help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, 
              help='Enable verbose logging')
@click.pass_context
def cli(ctx, config, verbose):
    """Offline Proxy - Multi-protocol offline caching proxy."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # Load configuration
    config_path = config or get_default_config_path()
    ctx.ensure_object(dict)
    ctx.obj['config'] = Config.load_from_file(config_path)
    ctx.obj['config_path'] = config_path


# Server management commands
@cli.group()
@click.pass_context
def server(ctx):
    """Server management commands."""
    pass


@server.command()
@click.option('--mode', type=click.Choice(['cache', 'offline']), 
              help='Server mode (overrides config)')
@click.option('--host', default=None, help='Host to bind to')
@click.option('--http-port', type=int, help='HTTP port')
@click.option('--https-port', type=int, help='HTTPS port')
@click.pass_context
def start(ctx, mode, host, http_port, https_port):
    """Start the proxy server."""
    config = ctx.obj['config']
    
    # Override config with command line options
    if mode:
        config.proxy.mode = mode
    if host:
        config.proxy.bind_address = host
    if http_port:
        config.proxy.http_port = http_port
    if https_port:
        config.proxy.https_port = https_port
        
    asyncio.run(_start_server(config))


async def _start_server(config: Config):
    """Start the proxy server."""
    server = ProxyServer(config)
    
    try:
        await server.start()
        click.echo(f"✅ Proxy server started in {config.proxy.mode} mode")
        click.echo(f"🌐 HTTP: http://{config.proxy.bind_address}:{config.proxy.http_port}")
        if config.proxy.https_port:
            click.echo(f"🔒 HTTPS: https://{config.proxy.bind_address}:{config.proxy.https_port}")
            
        # Keep server running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            click.echo("\n⏹️  Shutting down server...")
            
    finally:
        await server.stop()


@server.command()
@click.pass_context
def status(ctx):
    """Show server status."""
    click.echo("🔍 Checking server status...")
    # TODO: Implement server status check
    click.echo("ℹ️  Status check not implemented yet")


# Cache management commands
@cli.group()
@click.pass_context  
def cache(ctx):
    """Cache management commands."""
    pass


@cache.command()
@click.pass_context
def stats(ctx):
    """Show cache statistics."""
    config = ctx.obj['config']
    asyncio.run(_show_cache_stats(config))


async def _show_cache_stats(config: Config):
    """Show cache statistics."""
    from ..cache import CacheManager
    
    cache_manager = CacheManager(config)
    await cache_manager.initialize()
    
    try:
        stats = await cache_manager.get_cache_stats()
        
        click.echo("📊 Cache Statistics:")
        click.echo(f"  Total entries: {stats['total_entries']}")
        click.echo(f"  Total size: {stats['total_size_mb']:.2f} MB")
        click.echo(f"  Cache directory: {stats['cache_dir']}")
        click.echo(f"  Compression: {stats['compression_enabled']} ({stats['compression_algorithm']})")
        
        if stats['status_counts']:
            click.echo("  Status codes:")
            for status, count in stats['status_counts'].items():
                click.echo(f"    {status}: {count}")
                
    finally:
        await cache_manager.close()


@cache.command()
@click.confirmation_option(prompt='Are you sure you want to clear all cache?')
@click.pass_context
def clear(ctx):
    """Clear all cached data."""
    config = ctx.obj['config']
    asyncio.run(_clear_cache(config))


async def _clear_cache(config: Config):
    """Clear all cached data."""
    from ..cache import CacheManager
    import shutil
    
    cache_dir = Path(config.cache.root_dir)
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        click.echo("🗑️  Cache cleared successfully")
    else:
        click.echo("ℹ️  Cache directory doesn't exist")


# Git commands
@cli.group()
@click.pass_context
def git(ctx):
    """Git repository management."""
    pass


@git.command()
@click.argument('url')
@click.option('--branch', default='main', help='Branch to clone')
@click.pass_context
def mirror(ctx, url, branch):
    """Mirror a Git repository."""
    config = ctx.obj['config']
    asyncio.run(_mirror_git_repo(config, url, branch))


async def _mirror_git_repo(config: Config, url: str, branch: str):
    """Mirror a Git repository."""
    from ..cache import CacheManager
    
    cache_manager = CacheManager(config)
    await cache_manager.initialize()
    
    try:
        git_handler = GitProtocolHandler(config, cache_manager)
        await git_handler.initialize()
        
        click.echo(f"📦 Mirroring Git repository: {url}")
        repo_path = await git_handler.cache_repository(url, branch)
        click.echo(f"✅ Repository cached at: {repo_path}")
        
    except Exception as e:
        click.echo(f"❌ Failed to mirror repository: {e}")
        sys.exit(1)
    finally:
        await cache_manager.close()


@git.command()
@click.pass_context
def list(ctx):
    """List cached Git repositories."""
    config = ctx.obj['config']
    asyncio.run(_list_git_repos(config))


async def _list_git_repos(config: Config):
    """List cached Git repositories."""
    from ..cache import CacheManager
    
    cache_manager = CacheManager(config)
    await cache_manager.initialize()
    
    try:
        git_handler = GitProtocolHandler(config, cache_manager)
        repositories = await git_handler.get_cached_repositories()
        
        if not repositories:
            click.echo("ℹ️  No repositories cached")
            return
            
        click.echo("📋 Cached Git repositories:")
        for repo in repositories:
            size_mb = repo['size_bytes'] / (1024 * 1024)
            click.echo(f"  📁 {repo['name']}")
            click.echo(f"     URL: {repo['url']}")
            click.echo(f"     Size: {size_mb:.2f} MB")
            click.echo(f"     Last commit: {repo['last_commit_date']}")
            
    finally:
        await cache_manager.close()


# PyPI commands
@cli.group()
@click.pass_context
def pypi(ctx):
    """Python package management."""
    pass


@pypi.command()
@click.argument('package')
@click.option('--version', help='Specific version to mirror')
@click.option('--no-deps', is_flag=True, help='Don\'t mirror dependencies')
@click.pass_context
def mirror(ctx, package, version, no_deps):
    """Mirror a Python package."""
    config = ctx.obj['config']
    asyncio.run(_mirror_pypi_package(config, package, version, not no_deps))


async def _mirror_pypi_package(config: Config, package: str, version: str, include_deps: bool):
    """Mirror a Python package."""
    from ..cache import CacheManager
    
    cache_manager = CacheManager(config)
    await cache_manager.initialize()
    
    try:
        pypi_handler = PyPIProtocolHandler(config, cache_manager)
        await pypi_handler.initialize()
        
        click.echo(f"📦 Mirroring Python package: {package}")
        result = await pypi_handler.mirror_package(package, version, include_deps)
        
        click.echo(f"✅ Package mirrored: {result['package_name']} v{result['version']}")
        click.echo(f"   Files: {len(result['mirrored_files'])}")
        if result['dependencies']:
            click.echo(f"   Dependencies: {len(result['dependencies'])}")
            
    except Exception as e:
        click.echo(f"❌ Failed to mirror package: {e}")
        sys.exit(1)
    finally:
        await cache_manager.close()


@pypi.command()
@click.argument('requirements_file', type=click.Path(exists=True))
@click.pass_context
def mirror_requirements(ctx, requirements_file):
    """Mirror packages from requirements.txt file."""
    config = ctx.obj['config']
    asyncio.run(_mirror_requirements(config, requirements_file))


async def _mirror_requirements(config: Config, requirements_file: str):
    """Mirror packages from requirements.txt."""
    from ..cache import CacheManager
    
    cache_manager = CacheManager(config)
    await cache_manager.initialize()
    
    try:
        pypi_handler = PyPIProtocolHandler(config, cache_manager)
        await pypi_handler.initialize()
        
        click.echo(f"📦 Mirroring packages from: {requirements_file}")
        result = await pypi_handler.mirror_requirements_file(requirements_file)
        
        click.echo(f"✅ Mirroring complete:")
        click.echo(f"   Total packages: {result['total_packages']}")
        click.echo(f"   Successfully mirrored: {len(result['mirrored_packages'])}")
        click.echo(f"   Failed: {len(result['failed_packages'])}")
        
        if result['failed_packages']:
            click.echo("❌ Failed packages:")
            for pkg in result['failed_packages']:
                click.echo(f"   - {pkg}")
                
    except Exception as e:
        click.echo(f"❌ Failed to mirror requirements: {e}")
        sys.exit(1)
    finally:
        await cache_manager.close()


# APT commands
@cli.group()
@click.pass_context
def apt(ctx):
    """APT package management."""
    pass


@apt.command()
@click.option('--distribution', default='ubuntu', help='Distribution (ubuntu, debian)')
@click.option('--release', default='focal', help='Release name')
@click.option('--components', default='main,universe', help='Components (comma-separated)')
@click.option('--architectures', default='amd64', help='Architectures (comma-separated)')
@click.pass_context
def mirror(ctx, distribution, release, components, architectures):
    """Mirror APT repository."""
    config = ctx.obj['config']
    comp_list = [c.strip() for c in components.split(',')]
    arch_list = [a.strip() for a in architectures.split(',')]
    
    asyncio.run(_mirror_apt_repo(config, distribution, release, comp_list, arch_list))


async def _mirror_apt_repo(config: Config, distribution: str, release: str, 
                          components: list, architectures: list):
    """Mirror APT repository."""
    from ..cache import CacheManager
    
    cache_manager = CacheManager(config)
    await cache_manager.initialize()
    
    try:
        apt_handler = APTProtocolHandler(config, cache_manager)
        await apt_handler.initialize()
        
        click.echo(f"📦 Mirroring APT repository: {distribution} {release}")
        await apt_handler.mirror_repository(distribution, release, components, architectures)
        click.echo("✅ APT repository mirrored successfully")
        
    except Exception as e:
        click.echo(f"❌ Failed to mirror APT repository: {e}")
        sys.exit(1)
    finally:
        await cache_manager.close()


# Hosts file management
@cli.group()
@click.pass_context
def hosts(ctx):
    """Hosts file management."""
    pass


@hosts.command()
@click.option('--backup/--no-backup', default=True, help='Create backup of hosts file')
@click.pass_context
def setup(ctx, backup):
    """Setup hosts file for offline mode."""
    config = ctx.obj['config']
    
    if backup:
        # Create backup
        hosts_file = Path(config.hosts.file_path)
        backup_file = Path(config.hosts.backup_path)
        
        try:
            if hosts_file.exists():
                import shutil
                shutil.copy2(hosts_file, backup_file)
                click.echo(f"✅ Backup created: {backup_file}")
        except Exception as e:
            click.echo(f"❌ Failed to create backup: {e}")
            sys.exit(1)
    
    # Add entries to hosts file
    hosts_entries = [
        "# Offline Proxy entries",
        f"{config.proxy.bind_address} github.com",
        f"{config.proxy.bind_address} gitlab.com",
        f"{config.proxy.bind_address} pypi.org",
        f"{config.proxy.bind_address} files.pythonhosted.org",
        f"{config.proxy.bind_address} archive.ubuntu.com",
        f"{config.proxy.bind_address} deb.debian.org",
    ]
    
    try:
        with open(config.hosts.file_path, 'a') as f:
            f.write('\n' + '\n'.join(hosts_entries) + '\n')
        click.echo("✅ Hosts file updated for offline mode")
    except Exception as e:
        click.echo(f"❌ Failed to update hosts file: {e}")
        click.echo("💡 Try running with sudo")
        sys.exit(1)


@hosts.command()
@click.pass_context
def restore(ctx):
    """Restore original hosts file."""
    config = ctx.obj['config']
    
    hosts_file = Path(config.hosts.file_path)
    backup_file = Path(config.hosts.backup_path)
    
    if not backup_file.exists():
        click.echo("❌ No backup file found")
        sys.exit(1)
        
    try:
        import shutil
        shutil.copy2(backup_file, hosts_file)
        click.echo("✅ Hosts file restored from backup")
    except Exception as e:
        click.echo(f"❌ Failed to restore hosts file: {e}")
        sys.exit(1)


# SSL certificate management
@cli.group()
@click.pass_context
def ssl(ctx):
    """SSL certificate management."""
    pass


@ssl.command()
@click.pass_context
def setup(ctx):
    """Setup SSL certificates."""
    config = ctx.obj['config']
    asyncio.run(_setup_ssl(config))


async def _setup_ssl(config: Config):
    """Setup SSL certificates."""
    from ..ssl import SSLManager
    
    ssl_manager = SSLManager(config)
    await ssl_manager.initialize()
    
    click.echo("🔒 SSL certificates generated successfully")
    click.echo(f"   CA certificate: {ssl_manager.ca_cert_path}")
    click.echo(f"   Server certificate: {ssl_manager.server_cert_path}")


@ssl.command()
@click.pass_context
def install(ctx):
    """Show commands to install CA certificate."""
    config = ctx.obj['config']
    
    from ..ssl import SSLManager
    ssl_manager = SSLManager(config)
    
    click.echo("🔧 Run these commands to install the CA certificate:")
    commands = ssl_manager.install_ca_certificate_commands()
    for cmd in commands:
        click.echo(cmd)


def main():
    """Main entry point."""
    cli()