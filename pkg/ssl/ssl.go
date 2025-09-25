package ssl

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"time"

	"github.com/yorelog/offline-proxy/pkg/config"
)

// Manager manages SSL certificates for HTTPS proxy support
type Manager struct {
	config       *config.Config
	certDir      string
	caCertPath   string
	caKeyPath    string
	serverCertPath string
	serverKeyPath  string
}

// NewManager creates a new SSL manager
func NewManager(cfg *config.Config) *Manager {
	certDir := cfg.SSL.CertDir
	return &Manager{
		config:         cfg,
		certDir:        certDir,
		caCertPath:     filepath.Join(certDir, "ca.crt"),
		caKeyPath:      filepath.Join(certDir, "ca.key"),
		serverCertPath: filepath.Join(certDir, "server.crt"),
		serverKeyPath:  filepath.Join(certDir, "server.key"),
	}
}

// Initialize initializes SSL certificate management
func (m *Manager) Initialize() error {
	// Create certificate directory
	if err := os.MkdirAll(m.certDir, 0755); err != nil {
		return fmt.Errorf("failed to create cert directory: %w", err)
	}

	// Generate CA certificate if it doesn't exist
	if !m.caCertExists() {
		if err := m.generateCACertificate(); err != nil {
			return fmt.Errorf("failed to generate CA certificate: %w", err)
		}
	}

	// Generate server certificate if it doesn't exist
	if !m.serverCertExists() {
		if err := m.generateServerCertificate(); err != nil {
			return fmt.Errorf("failed to generate server certificate: %w", err)
		}
	}

	return nil
}

func (m *Manager) caCertExists() bool {
	_, err1 := os.Stat(m.caCertPath)
	_, err2 := os.Stat(m.caKeyPath)
	return err1 == nil && err2 == nil
}

func (m *Manager) serverCertExists() bool {
	_, err1 := os.Stat(m.serverCertPath)
	_, err2 := os.Stat(m.serverKeyPath)
	return err1 == nil && err2 == nil
}

func (m *Manager) generateCACertificate() error {
	// Generate CA private key
	caKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return err
	}

	// Create CA certificate template
	caTemplate := x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject: pkix.Name{
			Country:      []string{m.config.SSL.Country},
			Organization: []string{m.config.SSL.Organization},
			CommonName:   "Offline Proxy CA",
		},
		NotBefore:             time.Now(),
		NotAfter:              time.Now().AddDate(0, 0, m.config.SSL.ValidDays),
		KeyUsage:              x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature | x509.KeyUsageCertSign,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth, x509.ExtKeyUsageServerAuth},
		BasicConstraintsValid: true,
		IsCA:                  true,
	}

	// Create CA certificate
	caCertDER, err := x509.CreateCertificate(rand.Reader, &caTemplate, &caTemplate, &caKey.PublicKey, caKey)
	if err != nil {
		return err
	}

	// Write CA certificate
	caCertOut, err := os.Create(m.caCertPath)
	if err != nil {
		return err
	}
	defer caCertOut.Close()

	if err := pem.Encode(caCertOut, &pem.Block{Type: "CERTIFICATE", Bytes: caCertDER}); err != nil {
		return err
	}

	// Write CA private key
	caKeyOut, err := os.Create(m.caKeyPath)
	if err != nil {
		return err
	}
	defer caKeyOut.Close()

	caKeyPEM := &pem.Block{
		Type:  "RSA PRIVATE KEY",
		Bytes: x509.MarshalPKCS1PrivateKey(caKey),
	}

	if err := pem.Encode(caKeyOut, caKeyPEM); err != nil {
		return err
	}

	return nil
}

func (m *Manager) generateServerCertificate() error {
	// Load CA certificate and key
	caCertPEM, err := os.ReadFile(m.caCertPath)
	if err != nil {
		return err
	}

	caCertBlock, _ := pem.Decode(caCertPEM)
	if caCertBlock == nil {
		return fmt.Errorf("failed to decode CA certificate")
	}

	caCert, err := x509.ParseCertificate(caCertBlock.Bytes)
	if err != nil {
		return err
	}

	caKeyPEM, err := os.ReadFile(m.caKeyPath)
	if err != nil {
		return err
	}

	caKeyBlock, _ := pem.Decode(caKeyPEM)
	if caKeyBlock == nil {
		return fmt.Errorf("failed to decode CA private key")
	}

	caKey, err := x509.ParsePKCS1PrivateKey(caKeyBlock.Bytes)
	if err != nil {
		return err
	}

	// Generate server private key
	serverKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return err
	}

	// Create server certificate template
	serverTemplate := x509.Certificate{
		SerialNumber: big.NewInt(2),
		Subject: pkix.Name{
			Country:      []string{m.config.SSL.Country},
			Organization: []string{m.config.SSL.Organization},
			CommonName:   "Offline Proxy Server",
		},
		NotBefore:    time.Now(),
		NotAfter:     time.Now().AddDate(0, 0, m.config.SSL.ValidDays),
		KeyUsage:     x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		IPAddresses:  []net.IP{net.IPv4(127, 0, 0, 1), net.IPv6loopback},
		DNSNames:     []string{"localhost"},
	}

	// Create server certificate
	serverCertDER, err := x509.CreateCertificate(rand.Reader, &serverTemplate, caCert, &serverKey.PublicKey, caKey)
	if err != nil {
		return err
	}

	// Write server certificate
	serverCertOut, err := os.Create(m.serverCertPath)
	if err != nil {
		return err
	}
	defer serverCertOut.Close()

	if err := pem.Encode(serverCertOut, &pem.Block{Type: "CERTIFICATE", Bytes: serverCertDER}); err != nil {
		return err
	}

	// Write server private key
	serverKeyOut, err := os.Create(m.serverKeyPath)
	if err != nil {
		return err
	}
	defer serverKeyOut.Close()

	serverKeyPEM := &pem.Block{
		Type:  "RSA PRIVATE KEY",
		Bytes: x509.MarshalPKCS1PrivateKey(serverKey),
	}

	if err := pem.Encode(serverKeyOut, serverKeyPEM); err != nil {
		return err
	}

	return nil
}

// GetServerTLSConfig returns TLS configuration for the server
func (m *Manager) GetServerTLSConfig() (*tls.Config, error) {
	cert, err := tls.LoadX509KeyPair(m.serverCertPath, m.serverKeyPath)
	if err != nil {
		return nil, err
	}

	return &tls.Config{
		Certificates: []tls.Certificate{cert},
	}, nil
}

// GetCACertificatePEM returns the CA certificate in PEM format
func (m *Manager) GetCACertificatePEM() (string, error) {
	caCertPEM, err := os.ReadFile(m.caCertPath)
	if err != nil {
		return "", err
	}
	return string(caCertPEM), nil
}

// GetInstallCommands returns commands to install the CA certificate
func (m *Manager) GetInstallCommands() []string {
	return []string{
		fmt.Sprintf("# Copy CA certificate to system trust store"),
		fmt.Sprintf("sudo cp %s /usr/local/share/ca-certificates/offline-proxy-ca.crt", m.caCertPath),
		fmt.Sprintf("sudo update-ca-certificates"),
		fmt.Sprintf(""),
		fmt.Sprintf("# Or for macOS:"),
		fmt.Sprintf("sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain %s", m.caCertPath),
		fmt.Sprintf(""),
		fmt.Sprintf("# Or manually import into browser/application trust stores"),
	}
}

// GenerateDomainCertificate generates a certificate for a specific domain
func (m *Manager) GenerateDomainCertificate(domain string) error {
	// Load CA certificate and key
	caCertPEM, err := os.ReadFile(m.caCertPath)
	if err != nil {
		return err
	}

	caCertBlock, _ := pem.Decode(caCertPEM)
	if caCertBlock == nil {
		return fmt.Errorf("failed to decode CA certificate")
	}

	caCert, err := x509.ParseCertificate(caCertBlock.Bytes)
	if err != nil {
		return err
	}

	caKeyPEM, err := os.ReadFile(m.caKeyPath)
	if err != nil {
		return err
	}

	caKeyBlock, _ := pem.Decode(caKeyPEM)
	if caKeyBlock == nil {
		return fmt.Errorf("failed to decode CA private key")
	}

	caKey, err := x509.ParsePKCS1PrivateKey(caKeyBlock.Bytes)
	if err != nil {
		return err
	}

	// Generate domain private key
	domainKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return err
	}

	// Create domain certificate template
	domainTemplate := x509.Certificate{
		SerialNumber: big.NewInt(3),
		Subject: pkix.Name{
			Country:      []string{m.config.SSL.Country},
			Organization: []string{m.config.SSL.Organization},
			CommonName:   domain,
		},
		NotBefore:   time.Now(),
		NotAfter:    time.Now().AddDate(0, 0, m.config.SSL.ValidDays),
		KeyUsage:    x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		DNSNames:    []string{domain},
	}

	// Create domain certificate
	domainCertDER, err := x509.CreateCertificate(rand.Reader, &domainTemplate, caCert, &domainKey.PublicKey, caKey)
	if err != nil {
		return err
	}

	// Write domain certificate
	domainCertPath := filepath.Join(m.certDir, fmt.Sprintf("%s.crt", domain))
	domainCertOut, err := os.Create(domainCertPath)
	if err != nil {
		return err
	}
	defer domainCertOut.Close()

	if err := pem.Encode(domainCertOut, &pem.Block{Type: "CERTIFICATE", Bytes: domainCertDER}); err != nil {
		return err
	}

	// Write domain private key
	domainKeyPath := filepath.Join(m.certDir, fmt.Sprintf("%s.key", domain))
	domainKeyOut, err := os.Create(domainKeyPath)
	if err != nil {
		return err
	}
	defer domainKeyOut.Close()

	domainKeyPEM := &pem.Block{
		Type:  "RSA PRIVATE KEY",
		Bytes: x509.MarshalPKCS1PrivateKey(domainKey),
	}

	if err := pem.Encode(domainKeyOut, domainKeyPEM); err != nil {
		return err
	}

	return nil
}