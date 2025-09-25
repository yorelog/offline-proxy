package cache

import (
	"crypto/sha256"
	"database/sql"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"

	"github.com/klauspost/compress/zstd"
	_ "github.com/mattn/go-sqlite3"
	"github.com/yorelog/offline-proxy/pkg/config"
)

// CacheEntry represents a cached entry
type CacheEntry struct {
	CacheKey              string
	URL                   string
	Method                string
	StatusCode            int
	Headers               string
	FilePath              string
	CreatedAt             time.Time
	AccessedAt            time.Time
	SizeBytes             int64
	Compressed            bool
	CompressionAlgorithm  string
}

// Dependency represents a dependency relationship
type Dependency struct {
	ID             int
	ParentURL      string
	DependencyURL  string
	DependencyType string
	CreatedAt      time.Time
}

// CacheStats represents cache statistics
type CacheStats struct {
	TotalEntries        int64
	TotalSizeBytes      int64
	TotalSizeMB         float64
	StatusCounts        map[int]int64
	CacheDir            string
	CompressionEnabled  bool
	CompressionAlgorithm string
}

// Manager handles caching of network resources and their metadata
type Manager struct {
	config     *config.Config
	cacheDir   string
	dbPath     string
	db         *sql.DB
	compressor *zstd.Encoder
	decompressor *zstd.Decoder
}

// NewManager creates a new cache manager
func NewManager(cfg *config.Config) *Manager {
	return &Manager{
		config:   cfg,
		cacheDir: cfg.Cache.RootDir,
		dbPath:   filepath.Join(cfg.Cache.RootDir, "metadata.db"),
	}
}

// Initialize initializes the cache manager
func (m *Manager) Initialize() error {
	// Create cache directory
	if err := os.MkdirAll(m.cacheDir, 0755); err != nil {
		return fmt.Errorf("failed to create cache directory: %w", err)
	}

	// Initialize database
	if err := m.initDatabase(); err != nil {
		return fmt.Errorf("failed to initialize database: %w", err)
	}

	// Initialize compression
	if m.config.Cache.Compression && m.config.Cache.CompressionAlgorithm == "zstd" {
		var err error
		m.compressor, err = zstd.NewWriter(nil)
		if err != nil {
			return fmt.Errorf("failed to create zstd compressor: %w", err)
		}
		
		m.decompressor, err = zstd.NewReader(nil)
		if err != nil {
			return fmt.Errorf("failed to create zstd decompressor: %w", err)
		}
	}

	return nil
}

// Close closes the cache manager
func (m *Manager) Close() error {
	if m.compressor != nil {
		m.compressor.Close()
	}
	if m.decompressor != nil {
		m.decompressor.Close()
	}
	if m.db != nil {
		return m.db.Close()
	}
	return nil
}

func (m *Manager) initDatabase() error {
	var err error
	m.db, err = sql.Open("sqlite3", m.dbPath)
	if err != nil {
		return err
	}

	// Create tables
	createTablesSQL := `
	CREATE TABLE IF NOT EXISTS cache_entries (
		cache_key TEXT PRIMARY KEY,
		url TEXT NOT NULL,
		method TEXT NOT NULL,
		status_code INTEGER NOT NULL,
		headers TEXT NOT NULL,
		file_path TEXT NOT NULL,
		created_at TIMESTAMP NOT NULL,
		accessed_at TIMESTAMP NOT NULL,
		size_bytes INTEGER NOT NULL,
		compressed BOOLEAN NOT NULL,
		compression_algorithm TEXT
	);

	CREATE TABLE IF NOT EXISTS dependencies (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		parent_url TEXT NOT NULL,
		dependency_url TEXT NOT NULL,
		dependency_type TEXT NOT NULL,
		created_at TIMESTAMP NOT NULL
	);

	CREATE INDEX IF NOT EXISTS idx_cache_entries_url ON cache_entries(url);
	CREATE INDEX IF NOT EXISTS idx_cache_entries_created_at ON cache_entries(created_at);
	CREATE INDEX IF NOT EXISTS idx_dependencies_parent ON dependencies(parent_url);
	`

	_, err = m.db.Exec(createTablesSQL)
	return err
}

// GenerateCacheKey generates a unique cache key for a request
func (m *Manager) GenerateCacheKey(method, url string, headers map[string]string) string {
	// Create a deterministic key based on method, URL, and relevant headers
	h := sha256.New()
	h.Write([]byte(method))
	h.Write([]byte(url))
	
	// Include relevant headers that affect the response
	relevantHeaders := []string{"authorization", "accept", "accept-encoding", "user-agent"}
	for _, header := range relevantHeaders {
		if value, exists := headers[header]; exists {
			h.Write([]byte(header))
			h.Write([]byte(value))
		}
	}
	
	return fmt.Sprintf("%x", h.Sum(nil))
}

// GetCachedResponse retrieves a cached response
func (m *Manager) GetCachedResponse(cacheKey string) (*CacheEntry, []byte, error) {
	query := `
	SELECT url, method, status_code, headers, file_path, created_at, 
		   size_bytes, compressed, compression_algorithm
	FROM cache_entries 
	WHERE cache_key = ?`

	var entry CacheEntry
	
	err := m.db.QueryRow(query, cacheKey).Scan(
		&entry.URL, &entry.Method, &entry.StatusCode, &entry.Headers,
		&entry.FilePath, &entry.CreatedAt, &entry.SizeBytes,
		&entry.Compressed, &entry.CompressionAlgorithm,
	)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil, nil // Not found
		}
		return nil, nil, err
	}

	// Update access time
	_, err = m.db.Exec("UPDATE cache_entries SET accessed_at = ? WHERE cache_key = ?", 
		time.Now(), cacheKey)
	if err != nil {
		return nil, nil, err
	}

	// Read the cached file
	if _, err := os.Stat(entry.FilePath); os.IsNotExist(err) {
		// File was deleted, remove from database
		m.db.Exec("DELETE FROM cache_entries WHERE cache_key = ?", cacheKey)
		return nil, nil, nil
	}

	file, err := os.Open(entry.FilePath)
	if err != nil {
		return nil, nil, err
	}
	defer file.Close()

	body, err := io.ReadAll(file)
	if err != nil {
		return nil, nil, err
	}

	// Decompress if needed
	if entry.Compressed && entry.CompressionAlgorithm == "zstd" {
		body, err = m.decompressor.DecodeAll(body, nil)
		if err != nil {
			return nil, nil, err
		}
	}

	entry.CacheKey = cacheKey
	return &entry, body, nil
}

// CacheResponse caches a response
func (m *Manager) CacheResponse(cacheKey string, statusCode int, headers map[string]string, 
	body []byte, url, method string) error {
	
	// Create file path
	fileName := cacheKey + ".cache"
	responsesDir := filepath.Join(m.cacheDir, "responses")
	if err := os.MkdirAll(responsesDir, 0755); err != nil {
		return err
	}
	filePath := filepath.Join(responsesDir, fileName)

	// Compress data if enabled
	compressed := false
	compressionAlgorithm := ""
	dataToStore := body
	
	if m.config.Cache.Compression && len(body) > 1024 && m.config.Cache.CompressionAlgorithm == "zstd" {
		compressedBody := m.compressor.EncodeAll(body, nil)
		if len(compressedBody) < len(body) { // Only use if compression is beneficial
			dataToStore = compressedBody
			compressed = true
			compressionAlgorithm = "zstd"
		}
	}

	// Write to file
	if err := os.WriteFile(filePath, dataToStore, 0644); err != nil {
		return err
	}

	// Store metadata in database
	headersJSON := m.serializeHeaders(headers)
	
	_, err := m.db.Exec(`
		INSERT OR REPLACE INTO cache_entries 
		(cache_key, url, method, status_code, headers, file_path, 
		 created_at, accessed_at, size_bytes, compressed, compression_algorithm)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		cacheKey, url, method, statusCode, headersJSON, filePath,
		time.Now(), time.Now(), len(dataToStore), compressed, compressionAlgorithm,
	)

	return err
}

// AddDependency adds a dependency relationship
func (m *Manager) AddDependency(parentURL, dependencyURL, dependencyType string) error {
	_, err := m.db.Exec(`
		INSERT OR IGNORE INTO dependencies 
		(parent_url, dependency_url, dependency_type, created_at)
		VALUES (?, ?, ?, ?)`,
		parentURL, dependencyURL, dependencyType, time.Now(),
	)
	return err
}

// GetDependencies gets all dependencies for a URL
func (m *Manager) GetDependencies(parentURL string) ([]Dependency, error) {
	rows, err := m.db.Query(`
		SELECT dependency_url, dependency_type, created_at
		FROM dependencies
		WHERE parent_url = ?
		ORDER BY created_at`,
		parentURL,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var dependencies []Dependency
	for rows.Next() {
		var dep Dependency
		dep.ParentURL = parentURL
		err := rows.Scan(&dep.DependencyURL, &dep.DependencyType, &dep.CreatedAt)
		if err != nil {
			return nil, err
		}
		dependencies = append(dependencies, dep)
	}

	return dependencies, nil
}

// CleanupExpiredCache cleans up expired cache entries
func (m *Manager) CleanupExpiredCache() error {
	expireDate := time.Now().AddDate(0, 0, -m.config.Cache.ExpireDays)
	
	// Get expired entries
	rows, err := m.db.Query(`
		SELECT cache_key, file_path
		FROM cache_entries
		WHERE created_at < ?`,
		expireDate,
	)
	if err != nil {
		return err
	}
	defer rows.Close()

	// Delete files and database entries
	for rows.Next() {
		var cacheKey, filePath string
		if err := rows.Scan(&cacheKey, &filePath); err != nil {
			continue
		}

		// Remove file
		os.Remove(filePath) // Ignore errors

		// Remove from database
		m.db.Exec("DELETE FROM cache_entries WHERE cache_key = ?", cacheKey)
	}

	return nil
}

// GetCacheStats gets cache statistics
func (m *Manager) GetCacheStats() (*CacheStats, error) {
	stats := &CacheStats{
		CacheDir:            m.cacheDir,
		CompressionEnabled:  m.config.Cache.Compression,
		CompressionAlgorithm: m.config.Cache.CompressionAlgorithm,
		StatusCounts:        make(map[int]int64),
	}

	// Total entries
	err := m.db.QueryRow("SELECT COUNT(*) FROM cache_entries").Scan(&stats.TotalEntries)
	if err != nil {
		return nil, err
	}

	// Total size
	err = m.db.QueryRow("SELECT COALESCE(SUM(size_bytes), 0) FROM cache_entries").Scan(&stats.TotalSizeBytes)
	if err != nil {
		return nil, err
	}
	stats.TotalSizeMB = float64(stats.TotalSizeBytes) / (1024 * 1024)

	// Entries by status code
	rows, err := m.db.Query(`
		SELECT status_code, COUNT(*) 
		FROM cache_entries 
		GROUP BY status_code
		ORDER BY status_code`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var statusCode int
		var count int64
		if err := rows.Scan(&statusCode, &count); err != nil {
			continue
		}
		stats.StatusCounts[statusCode] = count
	}

	return stats, nil
}

func (m *Manager) serializeHeaders(headers map[string]string) string {
	// Simple serialization - in a real implementation, use JSON
	result := ""
	for k, v := range headers {
		if result != "" {
			result += "|"
		}
		result += k + ":" + v
	}
	return result
}