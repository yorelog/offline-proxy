package cache

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/yorelog/offline-proxy/pkg/config"
)

func TestNewManager(t *testing.T) {
	cfg := config.NewDefaultConfig()
	manager := NewManager(cfg)
	
	if manager.config != cfg {
		t.Error("Manager config should match provided config")
	}
	
	if manager.cacheDir != cfg.Cache.RootDir {
		t.Errorf("Expected cacheDir to be %s, got %s", cfg.Cache.RootDir, manager.cacheDir)
	}
}

func TestManagerInitialization(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "cache_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)
	
	cfg := config.NewDefaultConfig()
	cfg.Cache.RootDir = tempDir
	
	manager := NewManager(cfg)
	
	if err := manager.Initialize(); err != nil {
		t.Fatalf("Failed to initialize manager: %v", err)
	}
	defer manager.Close()
	
	// Check that database file was created
	dbPath := filepath.Join(tempDir, "metadata.db")
	if _, err := os.Stat(dbPath); os.IsNotExist(err) {
		t.Error("Database file should be created")
	}
}

func TestGenerateCacheKey(t *testing.T) {
	cfg := config.NewDefaultConfig()
	manager := NewManager(cfg)
	
	headers1 := map[string]string{"accept": "text/html"}
	headers2 := map[string]string{"accept": "text/html"}
	headers3 := map[string]string{"accept": "application/json"}
	
	key1 := manager.GenerateCacheKey("GET", "https://example.com", headers1)
	key2 := manager.GenerateCacheKey("GET", "https://example.com", headers2)
	key3 := manager.GenerateCacheKey("GET", "https://example.com", headers3)
	
	// Same method, URL, and headers should generate same key
	if key1 != key2 {
		t.Error("Same requests should generate same cache key")
	}
	
	// Different headers should generate different key
	if key1 == key3 {
		t.Error("Different headers should generate different cache key")
	}
	
	// Different method should generate different key
	key4 := manager.GenerateCacheKey("POST", "https://example.com", headers1)
	if key1 == key4 {
		t.Error("Different methods should generate different cache key")
	}
}

func TestCacheResponse(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "cache_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)
	
	cfg := config.NewDefaultConfig()
	cfg.Cache.RootDir = tempDir
	
	manager := NewManager(cfg)
	if err := manager.Initialize(); err != nil {
		t.Fatalf("Failed to initialize manager: %v", err)
	}
	defer manager.Close()
	
	// Cache a response
	cacheKey := "test_key"
	headers := map[string]string{"content-type": "text/plain"}
	body := []byte("Hello, World!")
	
	err = manager.CacheResponse(cacheKey, 200, headers, body, "https://example.com", "GET")
	if err != nil {
		t.Fatalf("Failed to cache response: %v", err)
	}
	
	// Retrieve the response
	entry, cachedBody, err := manager.GetCachedResponse(cacheKey)
	if err != nil {
		t.Fatalf("Failed to get cached response: %v", err)
	}
	
	if entry == nil {
		t.Fatal("Cached response should not be nil")
	}
	
	if entry.StatusCode != 200 {
		t.Errorf("Expected status code 200, got %d", entry.StatusCode)
	}
	
	if entry.URL != "https://example.com" {
		t.Errorf("Expected URL to be https://example.com, got %s", entry.URL)
	}
	
	if string(cachedBody) != "Hello, World!" {
		t.Errorf("Expected body to be 'Hello, World!', got %s", string(cachedBody))
	}
}

func TestGetCacheStats(t *testing.T) {
	// Create temporary directory
	tempDir, err := os.MkdirTemp("", "cache_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)
	
	cfg := config.NewDefaultConfig()
	cfg.Cache.RootDir = tempDir
	
	manager := NewManager(cfg)
	if err := manager.Initialize(); err != nil {
		t.Fatalf("Failed to initialize manager: %v", err)
	}
	defer manager.Close()
	
	// Initially should have no entries
	stats, err := manager.GetCacheStats()
	if err != nil {
		t.Fatalf("Failed to get cache stats: %v", err)
	}
	
	if stats.TotalEntries != 0 {
		t.Errorf("Expected 0 entries, got %d", stats.TotalEntries)
	}
	
	if stats.TotalSizeBytes != 0 {
		t.Errorf("Expected 0 bytes, got %d", stats.TotalSizeBytes)
	}
	
	// Add some cached responses
	for i := 0; i < 3; i++ {
		cacheKey := manager.GenerateCacheKey("GET", "https://example.com", map[string]string{})
		headers := map[string]string{"content-type": "text/plain"}
		body := []byte("Response")
		
		manager.CacheResponse(cacheKey, 200, headers, body, "https://example.com", "GET")
	}
	
	// Check stats again
	stats, err = manager.GetCacheStats()
	if err != nil {
		t.Fatalf("Failed to get cache stats: %v", err)
	}
	
	if stats.TotalEntries != 1 { // Should be 1 because same cache key
		t.Errorf("Expected 1 entry, got %d", stats.TotalEntries)
	}
	
	if stats.TotalSizeBytes <= 0 {
		t.Errorf("Expected positive size, got %d", stats.TotalSizeBytes)
	}
}