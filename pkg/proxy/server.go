package proxy

import (
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/gorilla/mux"
	"github.com/yorelog/offline-proxy/pkg/cache"
	"github.com/yorelog/offline-proxy/pkg/config"
)

// Server represents the main proxy server
type Server struct {
	config       *config.Config
	cacheManager *cache.Manager
	httpServer   *http.Server
	httpsServer  *http.Server
}

// NewServer creates a new proxy server
func NewServer(cfg *config.Config) *Server {
	return &Server{
		config:       cfg,
		cacheManager: cache.NewManager(cfg),
	}
}

// Start starts the proxy server
func (s *Server) Start() error {
	log.Printf("Starting proxy server in %s mode", s.config.Proxy.Mode)

	// Initialize cache manager
	if err := s.cacheManager.Initialize(); err != nil {
		return fmt.Errorf("failed to initialize cache manager: %w", err)
	}

	// Setup routes
	router := mux.NewRouter()
	router.PathPrefix("/").HandlerFunc(s.handleRequest)

	// Start HTTP server
	s.httpServer = &http.Server{
		Addr:         fmt.Sprintf("%s:%d", s.config.Proxy.BindAddress, s.config.Proxy.HTTPPort),
		Handler:      router,
		ReadTimeout:  time.Duration(s.config.Proxy.ReadTimeout) * time.Second,
		WriteTimeout: time.Duration(s.config.Proxy.WriteTimeout) * time.Second,
	}

	go func() {
		log.Printf("HTTP proxy listening on %s:%d", s.config.Proxy.BindAddress, s.config.Proxy.HTTPPort)
		if err := s.httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Printf("HTTP server error: %v", err)
		}
	}()

	// Start HTTPS server if configured
	if s.config.Proxy.HTTPSPort > 0 {
		s.httpsServer = &http.Server{
			Addr:         fmt.Sprintf("%s:%d", s.config.Proxy.BindAddress, s.config.Proxy.HTTPSPort),
			Handler:      router,
			ReadTimeout:  time.Duration(s.config.Proxy.ReadTimeout) * time.Second,
			WriteTimeout: time.Duration(s.config.Proxy.WriteTimeout) * time.Second,
		}

		go func() {
			log.Printf("HTTPS proxy listening on %s:%d", s.config.Proxy.BindAddress, s.config.Proxy.HTTPSPort)
			// TODO: Add SSL/TLS configuration
			if err := s.httpsServer.ListenAndServeTLS("", ""); err != nil && err != http.ErrServerClosed {
				log.Printf("HTTPS server error: %v", err)
			}
		}()
	}

	return nil
}

// Stop stops the proxy server
func (s *Server) Stop() error {
	log.Println("Stopping proxy server")

	if s.httpServer != nil {
		s.httpServer.Close()
	}
	if s.httpsServer != nil {
		s.httpsServer.Close()
	}
	if s.cacheManager != nil {
		s.cacheManager.Close()
	}

	return nil
}

func (s *Server) handleRequest(w http.ResponseWriter, r *http.Request) {
	// Extract request information
	method := r.Method
	requestURL := s.constructURL(r)
	
	log.Printf("Handling %s request to %s", method, requestURL)

	// Prepare headers map
	headers := make(map[string]string)
	for k, v := range r.Header {
		if len(v) > 0 {
			headers[strings.ToLower(k)] = v[0]
		}
	}

	// Remove proxy-specific headers
	delete(headers, "proxy-connection")
	delete(headers, "proxy-authorization")

	// Generate cache key
	cacheKey := s.cacheManager.GenerateCacheKey(method, requestURL, headers)

	if s.config.Proxy.Mode == "offline" {
		// Offline mode: serve from cache only
		s.serveCachedResponse(w, cacheKey, requestURL)
		return
	}

	// Cache mode: try cache first, then forward if not cached
	if s.serveCachedResponse(w, cacheKey, requestURL) {
		return
	}

	// Forward request to upstream server
	s.forwardRequest(w, r, cacheKey, requestURL, headers)
}

func (s *Server) serveCachedResponse(w http.ResponseWriter, cacheKey, requestURL string) bool {
	entry, body, err := s.cacheManager.GetCachedResponse(cacheKey)
	if err != nil {
		log.Printf("Error retrieving cached response: %v", err)
		return false
	}

	if entry == nil {
		if s.config.Proxy.Mode == "offline" {
			http.Error(w, fmt.Sprintf("Resource not available in offline mode: %s", requestURL), 
				http.StatusServiceUnavailable)
			return true
		}
		return false
	}

	log.Printf("Serving from cache: %s", requestURL)

	// Set response headers
	s.parseAndSetHeaders(w, entry.Headers)
	
	// Set status code and write body
	w.WriteHeader(entry.StatusCode)
	w.Write(body)

	return true
}

func (s *Server) forwardRequest(w http.ResponseWriter, r *http.Request, cacheKey, requestURL string, headers map[string]string) {
	// Create HTTP client with timeout
	client := &http.Client{
		Timeout: time.Duration(s.config.Protocols.HTTP.Timeout) * time.Second,
	}

	// Read request body
	var body io.Reader
	if r.Body != nil {
		body = r.Body
		defer r.Body.Close()
	}

	// Create new request
	req, err := http.NewRequest(r.Method, requestURL, body)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error creating request: %v", err), http.StatusBadGateway)
		return
	}

	// Set headers
	for k, v := range headers {
		if k != "host" { // Let Go set the correct host
			req.Header.Set(k, v)
		}
	}

	// Set User-Agent
	req.Header.Set("User-Agent", s.config.Protocols.HTTP.UserAgent)

	// Make request
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("Error forwarding request to %s: %v", requestURL, err)
		http.Error(w, fmt.Sprintf("Bad Gateway: %v", err), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	// Read response body
	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		http.Error(w, fmt.Sprintf("Error reading response: %v", err), http.StatusBadGateway)
		return
	}

	// Prepare response headers for caching
	responseHeaders := make(map[string]string)
	for k, v := range resp.Header {
		if len(v) > 0 && !isHopByHopHeader(k) {
			responseHeaders[strings.ToLower(k)] = v[0]
		}
	}

	// Cache the response
	err = s.cacheManager.CacheResponse(cacheKey, resp.StatusCode, responseHeaders, 
		responseBody, requestURL, r.Method)
	if err != nil {
		log.Printf("Error caching response: %v", err)
	} else {
		log.Printf("Cached response for: %s", requestURL)
	}

	// Send response to client
	for k, v := range responseHeaders {
		w.Header().Set(k, v)
	}
	w.WriteHeader(resp.StatusCode)
	w.Write(responseBody)
}

func (s *Server) constructURL(r *http.Request) string {
	// Handle both absolute and relative URLs
	if r.URL.IsAbs() {
		return r.URL.String()
	}

	// For relative URLs, construct from Host header
	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}

	host := r.Host
	if host == "" {
		host = r.Header.Get("Host")
	}

	u := &url.URL{
		Scheme:   scheme,
		Host:     host,
		Path:     r.URL.Path,
		RawQuery: r.URL.RawQuery,
	}

	return u.String()
}

func (s *Server) parseAndSetHeaders(w http.ResponseWriter, headersStr string) {
	// Simple parsing - in a real implementation, use JSON
	if headersStr == "" {
		return
	}

	pairs := strings.Split(headersStr, "|")
	for _, pair := range pairs {
		parts := strings.SplitN(pair, ":", 2)
		if len(parts) == 2 {
			w.Header().Set(parts[0], parts[1])
		}
	}
}

func isHopByHopHeader(header string) bool {
	hopByHopHeaders := []string{
		"Connection", "Keep-Alive", "Proxy-Authenticate",
		"Proxy-Authorization", "Te", "Trailers", "Transfer-Encoding", "Upgrade",
	}

	header = strings.ToLower(header)
	for _, h := range hopByHopHeaders {
		if strings.ToLower(h) == header {
			return true
		}
	}
	return false
}