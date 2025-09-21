"""
SSL certificate management for HTTPS proxy support.

This module handles generation and management of self-signed certificates
required for HTTPS proxy functionality in offline environments.
"""

import os
import ssl
import socket
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from ..config import Config


class SSLManager:
    """
    Manages SSL certificates for HTTPS proxy support.
    
    Features:
    - CA certificate generation
    - Server certificate generation
    - SSL context creation
    - Certificate installation helpers
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.cert_dir = Path(config.ssl.cert_dir)
        self.ca_cert_path = self.cert_dir / "ca.crt"
        self.ca_key_path = self.cert_dir / "ca.key"
        self.server_cert_path = self.cert_dir / "server.crt"
        self.server_key_path = self.cert_dir / "server.key"
        
    async def initialize(self):
        """Initialize SSL certificate management."""
        # Create certificate directory
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate CA certificate if it doesn't exist
        if not self._ca_cert_exists():
            await self._generate_ca_certificate()
            
        # Generate server certificate if it doesn't exist
        if not self._server_cert_exists():
            await self._generate_server_certificate()
            
    def _ca_cert_exists(self) -> bool:
        """Check if CA certificate exists."""
        return self.ca_cert_path.exists() and self.ca_key_path.exists()
        
    def _server_cert_exists(self) -> bool:
        """Check if server certificate exists."""
        return self.server_cert_path.exists() and self.server_key_path.exists()
        
    async def _generate_ca_certificate(self):
        """Generate a new CA certificate and private key."""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, self.config.ssl.country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.config.ssl.organization),
            x509.NameAttribute(NameOID.COMMON_NAME, "Offline Proxy CA"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=self.config.ssl.ca_validity_days)
        ).add_extension(
            x509.SubjectAlternativeName([]),
            critical=False,
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=True,
                crl_sign=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                digital_signature=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).sign(private_key, hashes.SHA256())
        
        # Write private key
        with open(self.ca_key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
            
        # Write certificate
        with open(self.ca_cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
            
    async def _generate_server_certificate(self):
        """Generate a server certificate signed by the CA."""
        # Load CA certificate and key
        with open(self.ca_cert_path, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())
            
        with open(self.ca_key_path, "rb") as f:
            ca_key = serialization.load_pem_private_key(f.read(), password=None)
            
        # Generate server private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create server certificate
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, self.config.ssl.country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.config.ssl.organization),
            x509.NameAttribute(NameOID.COMMON_NAME, "Offline Proxy Server"),
        ])
        
        # Create SAN list with common domains
        san_list = [
            x509.DNSName("localhost"),
            x509.DNSName("*.github.com"),
            x509.DNSName("*.gitlab.com"),
            x509.DNSName("*.pypi.org"),
            x509.DNSName("*.pythonhosted.org"),
            x509.DNSName("*.ubuntu.com"),
            x509.DNSName("*.debian.org"),
            x509.DNSName("*.archive.ubuntu.com"),
            x509.DNSName("*.deb.debian.org"),
            x509.IPAddress(socket.inet_aton("127.0.0.1")),
        ]
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            ca_cert.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=self.config.ssl.server_validity_days)
        ).add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=False,
                crl_sign=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                digital_signature=True,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
            ]),
            critical=True,
        ).sign(ca_key, hashes.SHA256())
        
        # Write server private key
        with open(self.server_key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
            
        # Write server certificate
        with open(self.server_cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
            
    def get_server_ssl_context(self) -> ssl.SSLContext:
        """
        Create SSL context for the proxy server.
        
        Returns:
            SSL context configured for the server
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.server_cert_path), str(self.server_key_path))
        return context
        
    def get_client_ssl_context(self) -> ssl.SSLContext:
        """
        Create SSL context for client connections.
        
        Returns:
            SSL context configured for client connections
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
        
    def get_ca_certificate_pem(self) -> str:
        """
        Get CA certificate in PEM format.
        
        Returns:
            CA certificate as PEM string
        """
        with open(self.ca_cert_path, "r") as f:
            return f.read()
            
    def install_ca_certificate_commands(self) -> List[str]:
        """
        Get commands to install CA certificate on the system.
        
        Returns:
            List of shell commands to install the CA certificate
        """
        ca_cert_path = str(self.ca_cert_path)
        
        commands = [
            f"# Install CA certificate for HTTPS support",
            f"sudo cp {ca_cert_path} /usr/local/share/ca-certificates/offline-proxy-ca.crt",
            f"sudo update-ca-certificates",
            f"",
            f"# For Python requests library",
            f"export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt",
            f"",
            f"# For curl",
            f"export CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt",
        ]
        
        return commands
        
    async def generate_domain_certificate(self, domain: str):
        """
        Generate a certificate for a specific domain.
        
        Args:
            domain: Domain name to generate certificate for
        """
        domain_cert_path = self.cert_dir / f"{domain}.crt"
        domain_key_path = self.cert_dir / f"{domain}.key"
        
        if domain_cert_path.exists() and domain_key_path.exists():
            return  # Certificate already exists
            
        # Load CA certificate and key
        with open(self.ca_cert_path, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())
            
        with open(self.ca_key_path, "rb") as f:
            ca_key = serialization.load_pem_private_key(f.read(), password=None)
            
        # Generate domain private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create domain certificate
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, self.config.ssl.country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.config.ssl.organization),
            x509.NameAttribute(NameOID.COMMON_NAME, domain),
        ])
        
        # Create SAN list
        san_list = [
            x509.DNSName(domain),
            x509.DNSName(f"*.{domain}"),
        ]
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            ca_cert.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=self.config.ssl.server_validity_days)
        ).add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=False,
                crl_sign=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                digital_signature=True,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
            ]),
            critical=True,
        ).sign(ca_key, hashes.SHA256())
        
        # Write domain private key
        with open(domain_key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
            
        # Write domain certificate
        with open(domain_cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))