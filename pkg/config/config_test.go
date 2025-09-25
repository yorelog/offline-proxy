package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestNewDefaultConfig(t *testing.T) {
	config := NewDefaultConfig()
	
	// Test default values
	if config.Proxy.HTTPPort != 8080 {
		t.Errorf("Expected HTTPPort to be 8080, got %d", config.Proxy.HTTPPort)
	}
	
	if config.Proxy.HTTPSPort != 8443 {
		t.Errorf("Expected HTTPSPort to be 8443, got %d", config.Proxy.HTTPSPort)
	}
	
	if config.Proxy.Mode != "cache" {
		t.Errorf("Expected Mode to be 'cache', got %s", config.Proxy.Mode)
	}
	
	if config.Cache.MaxSizeGB != 50 {
		t.Errorf("Expected MaxSizeGB to be 50, got %d", config.Cache.MaxSizeGB)
	}
	
	if config.SSL.Organization != "Offline Proxy" {
		t.Errorf("Expected Organization to be 'Offline Proxy', got %s", config.SSL.Organization)
	}
}

func TestConfigValidation(t *testing.T) {
	config := NewDefaultConfig()
	
	// Valid config should not return error
	if err := config.Validate(); err != nil {
		t.Errorf("Valid config should not return error: %v", err)
	}
	
	// Invalid HTTP port should return error
	config.Proxy.HTTPPort = 0
	if err := config.Validate(); err == nil {
		t.Error("Invalid HTTP port should return error")
	}
	
	// Reset to valid value
	config.Proxy.HTTPPort = 8080
	
	// Invalid mode should return error
	config.Proxy.Mode = "invalid"
	if err := config.Validate(); err == nil {
		t.Error("Invalid mode should return error")
	}
}

func TestConfigSaveAndLoad(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "config_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)
	
	configPath := filepath.Join(tempDir, "test_config.yaml")
	
	// Create and save config
	config := NewDefaultConfig()
	config.Proxy.HTTPPort = 9080
	config.Cache.MaxSizeGB = 100
	
	if err := config.SaveToFile(configPath); err != nil {
		t.Fatalf("Failed to save config: %v", err)
	}
	
	// Load config
	loadedConfig, err := LoadFromFile(configPath)
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}
	
	if loadedConfig.Proxy.HTTPPort != 9080 {
		t.Errorf("Expected HTTPPort to be 9080, got %d", loadedConfig.Proxy.HTTPPort)
	}
	
	if loadedConfig.Cache.MaxSizeGB != 100 {
		t.Errorf("Expected MaxSizeGB to be 100, got %d", loadedConfig.Cache.MaxSizeGB)
	}
}

func TestLoadNonexistentFile(t *testing.T) {
	config, err := LoadFromFile("nonexistent.yaml")
	if err != nil {
		t.Fatalf("Loading nonexistent file should not return error: %v", err)
	}
	
	// Should return default config
	if config.Proxy.HTTPPort != 8080 {
		t.Errorf("Expected default HTTPPort to be 8080, got %d", config.Proxy.HTTPPort)
	}
	
	if config.Proxy.Mode != "cache" {
		t.Errorf("Expected default Mode to be 'cache', got %s", config.Proxy.Mode)
	}
}