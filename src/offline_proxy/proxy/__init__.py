"""
Proxy server module for handling HTTP/HTTPS requests.

This module provides the core proxy functionality for both caching and offline modes.
"""

import asyncio
import logging
import ssl
from typing import Dict, Optional, Tuple, Any
from urllib.parse import urlparse

import aiohttp
from aiohttp import web, ClientSession, ClientTimeout
from aiohttp.web_request import Request
from aiohttp.web_response import Response

from ..cache import CacheManager
from ..ssl import SSLManager
from ..config import Config


logger = logging.getLogger(__name__)


class ProxyServer:
    """
    Main proxy server that handles HTTP/HTTPS requests.
    
    Supports two modes:
    - cache: Forward requests to real servers and cache responses
    - offline: Serve cached responses without external network access
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.cache_manager = CacheManager(config)
        self.ssl_manager = SSLManager(config)
        self.app = web.Application()
        self.client_session: Optional[ClientSession] = None
        self.setup_routes()
        
    def setup_routes(self):
        """Setup HTTP routes for the proxy server."""
        self.app.router.add_route("*", "/{path:.*}", self.handle_request)
        
    async def start(self):
        """Start the proxy server."""
        logger.info(f"Starting proxy server in {self.config.proxy.mode} mode")
        
        # Initialize cache manager
        await self.cache_manager.initialize()
        
        # Initialize SSL manager
        await self.ssl_manager.initialize()
        
        # Create client session for forwarding requests (cache mode only)
        if self.config.proxy.mode == "cache":
            timeout = ClientTimeout(total=self.config.protocols.http.timeout)
            self.client_session = ClientSession(
                timeout=timeout,
                headers={"User-Agent": self.config.protocols.http.user_agent}
            )
            
        # Setup SSL context for HTTPS
        ssl_context = None
        if self.config.proxy.https_port:
            ssl_context = self.ssl_manager.get_server_ssl_context()
            
        # Start HTTP server
        http_runner = web.AppRunner(self.app)
        await http_runner.setup()
        
        http_site = web.TCPSite(
            http_runner,
            self.config.proxy.bind_address,
            self.config.proxy.http_port
        )
        await http_site.start()
        logger.info(f"HTTP proxy listening on {self.config.proxy.bind_address}:{self.config.proxy.http_port}")
        
        # Start HTTPS server if configured
        if self.config.proxy.https_port and ssl_context:
            https_site = web.TCPSite(
                http_runner,
                self.config.proxy.bind_address, 
                self.config.proxy.https_port,
                ssl_context=ssl_context
            )
            await https_site.start()
            logger.info(f"HTTPS proxy listening on {self.config.proxy.bind_address}:{self.config.proxy.https_port}")
            
    async def stop(self):
        """Stop the proxy server."""
        logger.info("Stopping proxy server")
        
        if self.client_session:
            await self.client_session.close()
            
        await self.cache_manager.close()
        
    async def handle_request(self, request: Request) -> Response:
        """
        Handle incoming HTTP/HTTPS requests.
        
        Args:
            request: The incoming request
            
        Returns:
            The response (either from cache or forwarded from upstream)
        """
        try:
            # Extract request information
            method = request.method
            url = str(request.url)
            headers = dict(request.headers)
            
            # Remove proxy-specific headers
            headers.pop("Proxy-Connection", None)
            headers.pop("Proxy-Authorization", None)
            
            # Check if we have cached response
            cache_key = self.cache_manager.generate_cache_key(method, url, headers)
            
            if self.config.proxy.mode == "offline":
                # Offline mode: serve from cache only
                cached_response = await self.cache_manager.get_cached_response(cache_key)
                if cached_response:
                    return self._create_response_from_cache(cached_response)
                else:
                    return web.Response(
                        status=503,
                        text=f"Resource not available in offline mode: {url}",
                        headers={"Content-Type": "text/plain"}
                    )
                    
            else:
                # Cache mode: try cache first, then forward if not cached
                cached_response = await self.cache_manager.get_cached_response(cache_key)
                if cached_response and not self._should_refresh_cache(cached_response):
                    logger.debug(f"Serving from cache: {url}")
                    return self._create_response_from_cache(cached_response)
                    
                # Forward request to upstream server
                return await self._forward_request(request, cache_key)
                
        except Exception as e:
            logger.error(f"Error handling request {request.url}: {e}")
            return web.Response(
                status=500,
                text=f"Proxy error: {str(e)}",
                headers={"Content-Type": "text/plain"}
            )
            
    async def _forward_request(self, request: Request, cache_key: str) -> Response:
        """
        Forward request to upstream server and cache the response.
        
        Args:
            request: The original request
            cache_key: Cache key for storing the response
            
        Returns:
            The response from upstream server
        """
        if not self.client_session:
            raise RuntimeError("Client session not initialized")
            
        # Prepare request data
        method = request.method
        url = str(request.url)
        headers = dict(request.headers)
        
        # Remove proxy-specific headers
        headers.pop("Proxy-Connection", None)
        headers.pop("Proxy-Authorization", None)
        headers.pop("Host", None)  # Let aiohttp set the correct host
        
        # Read request body
        body = None
        if request.can_read_body:
            body = await request.read()
            
        try:
            # Make request to upstream server
            async with self.client_session.request(
                method=method,
                url=url,
                headers=headers,
                data=body,
                allow_redirects=False
            ) as upstream_response:
                
                # Read response body
                response_body = await upstream_response.read()
                
                # Prepare response headers
                response_headers = dict(upstream_response.headers)
                
                # Remove hop-by-hop headers
                hop_by_hop_headers = [
                    "Connection", "Keep-Alive", "Proxy-Authenticate",
                    "Proxy-Authorization", "TE", "Trailers", "Transfer-Encoding", "Upgrade"
                ]
                for header in hop_by_hop_headers:
                    response_headers.pop(header, None)
                    
                # Cache the response
                await self.cache_manager.cache_response(
                    cache_key=cache_key,
                    status=upstream_response.status,
                    headers=response_headers,
                    body=response_body,
                    url=url
                )
                
                logger.debug(f"Cached response for: {url}")
                
                # Return response
                return web.Response(
                    status=upstream_response.status,
                    headers=response_headers,
                    body=response_body
                )
                
        except aiohttp.ClientError as e:
            logger.error(f"Error forwarding request to {url}: {e}")
            return web.Response(
                status=502,
                text=f"Bad Gateway: {str(e)}",
                headers={"Content-Type": "text/plain"}
            )
            
    def _create_response_from_cache(self, cached_response: Dict[str, Any]) -> Response:
        """
        Create aiohttp Response from cached response data.
        
        Args:
            cached_response: Cached response data
            
        Returns:
            aiohttp Response object
        """
        return web.Response(
            status=cached_response["status"],
            headers=cached_response["headers"],
            body=cached_response["body"]
        )
        
    def _should_refresh_cache(self, cached_response: Dict[str, Any]) -> bool:
        """
        Determine if cached response should be refreshed.
        
        Args:
            cached_response: Cached response data
            
        Returns:
            True if cache should be refreshed
        """
        # TODO: Implement cache expiration logic based on Cache-Control headers
        # For now, always use cache if available
        return False