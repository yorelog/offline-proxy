package git

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	gogit "github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing"
	"github.com/yorelog/offline-proxy/pkg/cache"
	"github.com/yorelog/offline-proxy/pkg/config"
)

// Handler handles Git protocol caching and serving
type Handler struct {
	config       *config.Config
	cacheManager *cache.Manager
	reposDir     string
}

// RepositoryInfo contains information about a cached repository
type RepositoryInfo struct {
	Name           string
	URL            string
	SizeBytes      int64
	LastCommitDate string
	Branch         string
	CommitHash     string
}

// NewHandler creates a new Git protocol handler
func NewHandler(cfg *config.Config, cacheManager *cache.Manager) *Handler {
	reposDir := filepath.Join(cfg.Cache.RootDir, "git_repos")
	return &Handler{
		config:       cfg,
		cacheManager: cacheManager,
		reposDir:     reposDir,
	}
}

// Initialize initializes the Git protocol handler
func (h *Handler) Initialize() error {
	log.Println("Initializing Git protocol handler")
	
	// Create repositories directory
	if err := os.MkdirAll(h.reposDir, 0755); err != nil {
		return fmt.Errorf("failed to create repos directory: %w", err)
	}
	
	return nil
}

// CacheRepository clones/mirrors a Git repository
func (h *Handler) CacheRepository(url, branch string) (string, error) {
	// Generate repository name from URL
	repoName := h.generateRepoName(url)
	repoPath := filepath.Join(h.reposDir, repoName)
	
	log.Printf("Caching Git repository: %s to %s", url, repoPath)
	
	// Check if repository already exists
	if _, err := os.Stat(repoPath); err == nil {
		// Repository exists, try to update it
		return h.updateRepository(repoPath, branch)
	}
	
	// Clone the repository
	return h.cloneRepository(url, repoPath, branch)
}

func (h *Handler) cloneRepository(url, repoPath, branch string) (string, error) {
	cloneOptions := &gogit.CloneOptions{
		URL:      url,
		Progress: os.Stdout,
	}
	
	// If branch is specified, clone only that branch
	if branch != "" && branch != "main" && branch != "master" {
		cloneOptions.ReferenceName = plumbing.ReferenceName(fmt.Sprintf("refs/heads/%s", branch))
		cloneOptions.SingleBranch = true
	}
	
	repo, err := gogit.PlainClone(repoPath, false, cloneOptions)
	if err != nil {
		return "", fmt.Errorf("failed to clone repository: %w", err)
	}
	
	// Get repository info for caching metadata
	repoInfo, err := h.getRepositoryInfo(repo, url)
	if err != nil {
		log.Printf("Warning: failed to get repository info: %v", err)
	} else {
		// Cache repository metadata
		if err := h.cacheRepositoryMetadata(url, repoInfo); err != nil {
			log.Printf("Warning: failed to cache repository metadata: %v", err)
		}
	}
	
	return repoPath, nil
}

func (h *Handler) updateRepository(repoPath, branch string) (string, error) {
	// Open existing repository
	repo, err := gogit.PlainOpen(repoPath)
	if err != nil {
		return "", fmt.Errorf("failed to open repository: %w", err)
	}
	
	// Get working tree
	worktree, err := repo.Worktree()
	if err != nil {
		return "", fmt.Errorf("failed to get worktree: %w", err)
	}
	
	// Pull latest changes
	err = worktree.Pull(&gogit.PullOptions{
		RemoteName: "origin",
		Progress:   os.Stdout,
	})
	if err != nil && err != gogit.NoErrAlreadyUpToDate {
		return "", fmt.Errorf("failed to pull repository: %w", err)
	}
	
	log.Printf("Repository updated: %s", repoPath)
	return repoPath, nil
}

func (h *Handler) generateRepoName(url string) string {
	// Extract repository name from URL
	// Examples:
	// https://github.com/user/repo.git -> user_repo
	// git@github.com:user/repo.git -> user_repo
	
	url = strings.TrimSuffix(url, ".git")
	
	if strings.Contains(url, "://") {
		// HTTP/HTTPS URL
		parts := strings.Split(url, "/")
		if len(parts) >= 2 {
			user := parts[len(parts)-2]
			repo := parts[len(parts)-1]
			return fmt.Sprintf("%s_%s", user, repo)
		}
	} else if strings.Contains(url, ":") {
		// SSH URL
		parts := strings.Split(url, ":")
		if len(parts) >= 2 {
			pathParts := strings.Split(parts[1], "/")
			if len(pathParts) >= 2 {
				user := pathParts[0]
				repo := pathParts[1]
				return fmt.Sprintf("%s_%s", user, repo)
			}
		}
	}
	
	// Fallback: use the full URL with special characters replaced
	name := strings.ReplaceAll(url, "/", "_")
	name = strings.ReplaceAll(name, ":", "_")
	name = strings.ReplaceAll(name, ".", "_")
	return name
}

func (h *Handler) getRepositoryInfo(repo *gogit.Repository, url string) (*RepositoryInfo, error) {
	// Get HEAD reference
	head, err := repo.Head()
	if err != nil {
		return nil, err
	}
	
	// Get commit object
	commit, err := repo.CommitObject(head.Hash())
	if err != nil {
		return nil, err
	}
	
	// Calculate repository size (approximation)
	repoSize := int64(0)
	// Note: This is a simplified size calculation
	// In a real implementation, you might want to traverse all objects
	
	info := &RepositoryInfo{
		Name:           h.generateRepoName(url),
		URL:            url,
		SizeBytes:      repoSize,
		LastCommitDate: commit.Author.When.Format("2006-01-02 15:04:05"),
		Branch:         head.Name().Short(),
		CommitHash:     head.Hash().String(),
	}
	
	return info, nil
}

func (h *Handler) cacheRepositoryMetadata(url string, info *RepositoryInfo) error {
	// Store repository metadata as a dependency relationship
	return h.cacheManager.AddDependency("git://repositories", url, "git_repository")
}

// GetCachedRepositories returns a list of cached repositories
func (h *Handler) GetCachedRepositories() ([]RepositoryInfo, error) {
	var repositories []RepositoryInfo
	
	// Check if repositories directory exists
	if _, err := os.Stat(h.reposDir); os.IsNotExist(err) {
		return repositories, nil // Return empty list if directory doesn't exist
	}
	
	// Read repositories directory
	entries, err := os.ReadDir(h.reposDir)
	if err != nil {
		return repositories, err
	}
	
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		
		repoPath := filepath.Join(h.reposDir, entry.Name())
		repo, err := gogit.PlainOpen(repoPath)
		if err != nil {
			log.Printf("Warning: failed to open repository %s: %v", repoPath, err)
			continue
		}
		
		// Get repository info
		repoInfo, err := h.getRepositoryInfo(repo, "")
		if err != nil {
			log.Printf("Warning: failed to get info for repository %s: %v", repoPath, err)
			continue
		}
		
		// Set name from directory name
		repoInfo.Name = entry.Name()
		
		// Get actual size
		repoInfo.SizeBytes, err = h.getDirectorySize(repoPath)
		if err != nil {
			log.Printf("Warning: failed to get size for repository %s: %v", repoPath, err)
		}
		
		repositories = append(repositories, *repoInfo)
	}
	
	return repositories, nil
}

func (h *Handler) getDirectorySize(path string) (int64, error) {
	var size int64
	
	err := filepath.Walk(path, func(filePath string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() {
			size += info.Size()
		}
		return nil
	})
	
	return size, err
}

// ExtractGitDependencies extracts Git-related dependencies from repository files
func (h *Handler) ExtractGitDependencies(repoPath string) ([]string, error) {
	var dependencies []string
	
	// Check for common dependency files
	dependencyFiles := map[string]func(string) ([]string, error){
		"requirements.txt": h.extractPyPIDependencies,
		"package.json":     h.extractNPMDependencies,
		"go.mod":          h.extractGoDependencies,
		"Cargo.toml":      h.extractCargoDependencies,
		".gitmodules":     h.extractGitSubmodules,
	}
	
	for fileName, extractor := range dependencyFiles {
		filePath := filepath.Join(repoPath, fileName)
		if _, err := os.Stat(filePath); err == nil {
			deps, err := extractor(filePath)
			if err != nil {
				log.Printf("Warning: failed to extract dependencies from %s: %v", fileName, err)
				continue
			}
			dependencies = append(dependencies, deps...)
		}
	}
	
	return dependencies, nil
}

func (h *Handler) extractPyPIDependencies(filePath string) ([]string, error) {
	content, err := os.ReadFile(filePath)
	if err != nil {
		return nil, err
	}
	
	var dependencies []string
	lines := strings.Split(string(content), "\n")
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		
		// Extract package name (before version specifiers)
		packageName := strings.Split(line, "==")[0]
		packageName = strings.Split(packageName, ">=")[0]
		packageName = strings.Split(packageName, "<=")[0]
		packageName = strings.Split(packageName, ">")[0]
		packageName = strings.Split(packageName, "<")[0]
		packageName = strings.TrimSpace(packageName)
		
		if packageName != "" {
			dependencies = append(dependencies, fmt.Sprintf("https://pypi.org/project/%s/", packageName))
		}
	}
	
	return dependencies, nil
}

func (h *Handler) extractNPMDependencies(filePath string) ([]string, error) {
	// TODO: Implement NPM package.json parsing
	return []string{}, nil
}

func (h *Handler) extractGoDependencies(filePath string) ([]string, error) {
	// TODO: Implement Go mod parsing
	return []string{}, nil
}

func (h *Handler) extractCargoDependencies(filePath string) ([]string, error) {
	// TODO: Implement Cargo.toml parsing
	return []string{}, nil
}

func (h *Handler) extractGitSubmodules(filePath string) ([]string, error) {
	// TODO: Implement .gitmodules parsing
	return []string{}, nil
}