package config

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/viper"
	"gopkg.in/yaml.v3"
)

// ProxyConfig represents proxy server configuration
type ProxyConfig struct {
	HTTPPort     int    `yaml:"http_port" mapstructure:"http_port"`
	HTTPSPort    int    `yaml:"https_port" mapstructure:"https_port"`
	BindAddress  string `yaml:"bind_address" mapstructure:"bind_address"`
	Mode         string `yaml:"mode" mapstructure:"mode"`
	ReadTimeout  int    `yaml:"read_timeout" mapstructure:"read_timeout"`
	WriteTimeout int    `yaml:"write_timeout" mapstructure:"write_timeout"`
}

// CacheConfig represents cache configuration
type CacheConfig struct {
	RootDir             string `yaml:"root_dir" mapstructure:"root_dir"`
	MaxSizeGB           int    `yaml:"max_size_gb" mapstructure:"max_size_gb"`
	ExpireDays          int    `yaml:"expire_days" mapstructure:"expire_days"`
	Compression         bool   `yaml:"compression" mapstructure:"compression"`
	CompressionAlgorithm string `yaml:"compression_algorithm" mapstructure:"compression_algorithm"`
	CleanupInterval     int    `yaml:"cleanup_interval" mapstructure:"cleanup_interval"`
}

// SSLConfig represents SSL certificate configuration
type SSLConfig struct {
	CertDir      string `yaml:"cert_dir" mapstructure:"cert_dir"`
	Country      string `yaml:"country" mapstructure:"country"`
	Organization string `yaml:"organization" mapstructure:"organization"`
	ValidDays    int    `yaml:"valid_days" mapstructure:"valid_days"`
}

// HTTPProtocolConfig represents HTTP protocol configuration
type HTTPProtocolConfig struct {
	Enabled    bool
	UserAgent  string `yaml:"user_agent" mapstructure:"user_agent"`
	Timeout    int    `yaml:"timeout" mapstructure:"timeout"`
	MaxRetries int    `yaml:"max_retries" mapstructure:"max_retries"`
}

// GitProtocolConfig represents Git protocol configuration
type GitProtocolConfig struct {
	Enabled  bool
	Port     int      `yaml:"port" mapstructure:"port"`
	Services []string `yaml:"services" mapstructure:"services"`
}

// APTProtocolConfig represents APT protocol configuration
type APTProtocolConfig struct {
	Enabled       bool
	Mirror        string   `yaml:"mirror" mapstructure:"mirror"`
	Distributions []string `yaml:"distributions" mapstructure:"distributions"`
	Components    []string `yaml:"components" mapstructure:"components"`
	Architectures []string `yaml:"architectures" mapstructure:"architectures"`
}

// PyPIProtocolConfig represents PyPI protocol configuration
type PyPIProtocolConfig struct {
	Enabled  bool
	IndexURL string `yaml:"index_url" mapstructure:"index_url"`
	Mirror   string `yaml:"mirror" mapstructure:"mirror"`
}

// ProtocolsConfig represents all protocols configuration
type ProtocolsConfig struct {
	HTTP HTTPProtocolConfig `yaml:"http" mapstructure:"http"`
	Git  GitProtocolConfig  `yaml:"git" mapstructure:"git"`
	APT  APTProtocolConfig  `yaml:"apt" mapstructure:"apt"`
	PyPI PyPIProtocolConfig `yaml:"pypi" mapstructure:"pypi"`
}

// DiscoveryConfig represents resource discovery configuration
type DiscoveryConfig struct {
	Enabled         bool `yaml:"enabled" mapstructure:"enabled"`
	MaxDepth        int  `yaml:"max_depth" mapstructure:"max_depth"`
	FollowRedirects bool `yaml:"follow_redirects" mapstructure:"follow_redirects"`
}

// LoggingConfig represents logging configuration
type LoggingConfig struct {
	Level  string `yaml:"level" mapstructure:"level"`
	Format string `yaml:"format" mapstructure:"format"`
	File   string `yaml:"file" mapstructure:"file"`
}

// HostsConfig represents hosts file configuration
type HostsConfig struct {
	FilePath   string `yaml:"file_path" mapstructure:"file_path"`
	BackupPath string `yaml:"backup_path" mapstructure:"backup_path"`
}

// PerformanceConfig represents performance configuration
type PerformanceConfig struct {
	MaxConcurrentRequests int `yaml:"max_concurrent_requests" mapstructure:"max_concurrent_requests"`
	MaxConcurrentDownloads int `yaml:"max_concurrent_downloads" mapstructure:"max_concurrent_downloads"`
	BufferSize            int `yaml:"buffer_size" mapstructure:"buffer_size"`
}

// Config represents the main configuration
type Config struct {
	Proxy       ProxyConfig       `yaml:"proxy" mapstructure:"proxy"`
	Cache       CacheConfig       `yaml:"cache" mapstructure:"cache"`
	SSL         SSLConfig         `yaml:"ssl" mapstructure:"ssl"`
	Protocols   ProtocolsConfig   `yaml:"protocols" mapstructure:"protocols"`
	Discovery   DiscoveryConfig   `yaml:"discovery" mapstructure:"discovery"`
	Logging     LoggingConfig     `yaml:"logging" mapstructure:"logging"`
	Hosts       HostsConfig       `yaml:"hosts" mapstructure:"hosts"`
	Performance PerformanceConfig `yaml:"performance" mapstructure:"performance"`
}

// NewDefaultConfig creates a new configuration with default values
func NewDefaultConfig() *Config {
	homeDir, _ := os.UserHomeDir()
	dataDir := filepath.Join(homeDir, ".offline-proxy")
	
	return &Config{
		Proxy: ProxyConfig{
			HTTPPort:     8080,
			HTTPSPort:    8443,
			BindAddress:  "127.0.0.1",
			Mode:         "cache",
			ReadTimeout:  30,
			WriteTimeout: 30,
		},
		Cache: CacheConfig{
			RootDir:             filepath.Join(dataDir, "cache"),
			MaxSizeGB:           50,
			ExpireDays:          30,
			Compression:         true,
			CompressionAlgorithm: "zstd",
			CleanupInterval:     3600,
		},
		SSL: SSLConfig{
			CertDir:      filepath.Join(dataDir, "certs"),
			Country:      "US",
			Organization: "Offline Proxy",
			ValidDays:    365,
		},
		Protocols: ProtocolsConfig{
			HTTP: HTTPProtocolConfig{
				Enabled:    true,
				UserAgent:  "OfflineProxy/1.0",
				Timeout:    30,
				MaxRetries: 3,
			},
			Git: GitProtocolConfig{
				Enabled:  true,
				Port:     9418,
				Services: []string{"github.com", "gitlab.com", "gitee.com", "bitbucket.org"},
			},
			APT: APTProtocolConfig{
				Enabled:       true,
				Mirror:        "http://archive.ubuntu.com/ubuntu/",
				Distributions: []string{"ubuntu", "debian"},
				Components:    []string{"main", "universe", "restricted", "multiverse"},
				Architectures: []string{"amd64", "i386"},
			},
			PyPI: PyPIProtocolConfig{
				Enabled:  true,
				IndexURL: "https://pypi.org/simple/",
				Mirror:   "https://files.pythonhosted.org/packages/",
			},
		},
		Discovery: DiscoveryConfig{
			Enabled:         true,
			MaxDepth:        3,
			FollowRedirects: true,
		},
		Logging: LoggingConfig{
			Level:  "info",
			Format: "json",
			File:   "",
		},
		Hosts: HostsConfig{
			FilePath:   "/etc/hosts",
			BackupPath: "/etc/hosts.backup",
		},
		Performance: PerformanceConfig{
			MaxConcurrentRequests:  100,
			MaxConcurrentDownloads: 10,
			BufferSize:            32768,
		},
	}
}

// LoadFromFile loads configuration from a YAML file
func LoadFromFile(configPath string) (*Config, error) {
	config := NewDefaultConfig()
	
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		// Return default configuration if file doesn't exist
		return config, nil
	}
	
	viper.SetConfigFile(configPath)
	if err := viper.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}
	
	if err := viper.Unmarshal(config); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}
	
	return config, nil
}

// SaveToFile saves configuration to a YAML file
func (c *Config) SaveToFile(configPath string) error {
	// Ensure directory exists
	if err := os.MkdirAll(filepath.Dir(configPath), 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}
	
	data, err := yaml.Marshal(c)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}
	
	if err := os.WriteFile(configPath, data, 0644); err != nil {
		return fmt.Errorf("failed to write config file: %w", err)
	}
	
	return nil
}

// GetDefaultConfigPath returns the default configuration file path
func GetDefaultConfigPath() string {
	homeDir, _ := os.UserHomeDir()
	return filepath.Join(homeDir, ".offline-proxy", "config.yaml")
}

// Validate validates the configuration
func (c *Config) Validate() error {
	if c.Proxy.HTTPPort <= 0 || c.Proxy.HTTPPort > 65535 {
		return fmt.Errorf("invalid HTTP port: %d", c.Proxy.HTTPPort)
	}
	
	if c.Proxy.HTTPSPort != 0 && (c.Proxy.HTTPSPort <= 0 || c.Proxy.HTTPSPort > 65535) {
		return fmt.Errorf("invalid HTTPS port: %d", c.Proxy.HTTPSPort)
	}
	
	if c.Proxy.Mode != "cache" && c.Proxy.Mode != "offline" {
		return fmt.Errorf("invalid proxy mode: %s (must be 'cache' or 'offline')", c.Proxy.Mode)
	}
	
	if c.Cache.MaxSizeGB <= 0 {
		return fmt.Errorf("invalid cache max size: %d GB", c.Cache.MaxSizeGB)
	}
	
	if c.Cache.CompressionAlgorithm != "zstd" && c.Cache.CompressionAlgorithm != "lz4" && c.Cache.CompressionAlgorithm != "gzip" {
		return fmt.Errorf("invalid compression algorithm: %s", c.Cache.CompressionAlgorithm)
	}
	
	return nil
}