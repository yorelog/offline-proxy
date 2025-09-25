package main

import (
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/fatih/color"
	"github.com/spf13/cobra"
	"github.com/yorelog/offline-proxy/pkg/cache"
	"github.com/yorelog/offline-proxy/pkg/config"
	"github.com/yorelog/offline-proxy/pkg/protocols/git"
	"github.com/yorelog/offline-proxy/pkg/proxy"
	"github.com/yorelog/offline-proxy/pkg/ssl"
)

var (
	configFile string
	verbose    bool
	cfg        *config.Config
)

func main() {
	if err := rootCmd.Execute(); err != nil {
		log.Fatal(err)
	}
}

var rootCmd = &cobra.Command{
	Use:   "offline-proxy",
	Short: "Offline Proxy - Multi-protocol offline caching proxy",
	Long: `Offline Proxy is a tool that allows you to cache network resources 
in an online environment and serve them through a local proxy server 
in an offline environment.

Supports multiple protocols: HTTP/HTTPS, Git, APT, PyPI`,
	PersistentPreRun: func(cmd *cobra.Command, args []string) {
		// Load configuration
		var err error
		if configFile == "" {
			configFile = config.GetDefaultConfigPath()
		}
		
		cfg, err = config.LoadFromFile(configFile)
		if err != nil {
			log.Fatalf("Failed to load config: %v", err)
		}
		
		if verbose {
			log.SetFlags(log.LstdFlags | log.Lshortfile)
		}
	},
}

func init() {
	rootCmd.PersistentFlags().StringVarP(&configFile, "config", "c", "", "config file path")
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, "enable verbose logging")
	
	// Add subcommands
	rootCmd.AddCommand(serverCmd)
	rootCmd.AddCommand(cacheCmd)
	rootCmd.AddCommand(gitCmd)
	rootCmd.AddCommand(pypiCmd)
	rootCmd.AddCommand(aptCmd)
	rootCmd.AddCommand(hostsCmd)
	rootCmd.AddCommand(sslCmd)
}

// Server management commands
var serverCmd = &cobra.Command{
	Use:   "server",
	Short: "Server management commands",
}

var serverStartCmd = &cobra.Command{
	Use:   "start",
	Short: "Start the proxy server",
	Run: func(cmd *cobra.Command, args []string) {
		// Override config with command line options
		mode, _ := cmd.Flags().GetString("mode")
		if mode != "" {
			cfg.Proxy.Mode = mode
		}
		
		host, _ := cmd.Flags().GetString("host")
		if host != "" {
			cfg.Proxy.BindAddress = host
		}
		
		httpPort, _ := cmd.Flags().GetInt("http-port")
		if httpPort > 0 {
			cfg.Proxy.HTTPPort = httpPort
		}
		
		httpsPort, _ := cmd.Flags().GetInt("https-port")
		if httpsPort > 0 {
			cfg.Proxy.HTTPSPort = httpsPort
		}
		
		// Validate configuration
		if err := cfg.Validate(); err != nil {
			log.Fatalf("Configuration validation failed: %v", err)
		}
		
		startServer(cfg)
	},
}

var serverStatusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show server status",
	Run: func(cmd *cobra.Command, args []string) {
		color.Blue("🔍 Checking server status...")
		color.Yellow("ℹ️  Status check not implemented yet")
	},
}

func init() {
	serverStartCmd.Flags().String("mode", "", "Server mode (cache/offline)")
	serverStartCmd.Flags().String("host", "", "Host to bind to")
	serverStartCmd.Flags().Int("http-port", 0, "HTTP port")
	serverStartCmd.Flags().Int("https-port", 0, "HTTPS port")
	
	serverCmd.AddCommand(serverStartCmd)
	serverCmd.AddCommand(serverStatusCmd)
}

func startServer(cfg *config.Config) {
	server := proxy.NewServer(cfg)
	
	if err := server.Start(); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
	
	color.Green("✅ Proxy server started in %s mode", cfg.Proxy.Mode)
	color.Cyan("🌐 HTTP: http://%s:%d", cfg.Proxy.BindAddress, cfg.Proxy.HTTPPort)
	if cfg.Proxy.HTTPSPort > 0 {
		color.Cyan("🔒 HTTPS: https://%s:%d", cfg.Proxy.BindAddress, cfg.Proxy.HTTPSPort)
	}
	
	// Wait for interrupt signal
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	<-c
	
	color.Yellow("\n⏹️  Shutting down server...")
	server.Stop()
}

// Cache management commands
var cacheCmd = &cobra.Command{
	Use:   "cache",
	Short: "Cache management commands",
}

var cacheStatsCmd = &cobra.Command{
	Use:   "stats",
	Short: "Show cache statistics",
	Run: func(cmd *cobra.Command, args []string) {
		showCacheStats(cfg)
	},
}

var cacheClearCmd = &cobra.Command{
	Use:   "clear",
	Short: "Clear all cached data",
	Run: func(cmd *cobra.Command, args []string) {
		clearCache(cfg)
	},
}

func init() {
	cacheCmd.AddCommand(cacheStatsCmd)
	cacheCmd.AddCommand(cacheClearCmd)
}

func showCacheStats(cfg *config.Config) {
	cacheManager := cache.NewManager(cfg)
	if err := cacheManager.Initialize(); err != nil {
		log.Fatalf("Failed to initialize cache manager: %v", err)
	}
	defer cacheManager.Close()
	
	stats, err := cacheManager.GetCacheStats()
	if err != nil {
		log.Fatalf("Failed to get cache stats: %v", err)
	}
	
	color.Blue("📊 Cache Statistics:")
	fmt.Printf("  Total entries: %d\n", stats.TotalEntries)
	fmt.Printf("  Total size: %.2f MB\n", stats.TotalSizeMB)
	fmt.Printf("  Cache directory: %s\n", stats.CacheDir)
	fmt.Printf("  Compression: %t (%s)\n", stats.CompressionEnabled, stats.CompressionAlgorithm)
	
	if len(stats.StatusCounts) > 0 {
		fmt.Println("  Status codes:")
		for status, count := range stats.StatusCounts {
			fmt.Printf("    %d: %d\n", status, count)
		}
	}
}

func clearCache(cfg *config.Config) {
	color.Red("⚠️  This will delete all cached data. Continue? (y/N): ")
	var response string
	fmt.Scanln(&response)
	
	if response != "y" && response != "Y" {
		color.Yellow("Cache clear cancelled")
		return
	}
	
	if err := os.RemoveAll(cfg.Cache.RootDir); err != nil {
		log.Fatalf("Failed to clear cache: %v", err)
	}
	
	color.Green("🗑️  Cache cleared successfully")
}

// Git commands
var gitCmd = &cobra.Command{
	Use:   "git",
	Short: "Git repository management",
}

var gitMirrorCmd = &cobra.Command{
	Use:   "mirror [url]",
	Short: "Mirror a Git repository",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		url := args[0]
		branch, _ := cmd.Flags().GetString("branch")
		
		mirrorGitRepo(cfg, url, branch)
	},
}

var gitListCmd = &cobra.Command{
	Use:   "list",
	Short: "List cached Git repositories",
	Run: func(cmd *cobra.Command, args []string) {
		listGitRepos(cfg)
	},
}

func init() {
	gitMirrorCmd.Flags().String("branch", "main", "Branch to clone")
	gitCmd.AddCommand(gitMirrorCmd)
	gitCmd.AddCommand(gitListCmd)
}

func mirrorGitRepo(cfg *config.Config, url, branch string) {
	cacheManager := cache.NewManager(cfg)
	if err := cacheManager.Initialize(); err != nil {
		log.Fatalf("Failed to initialize cache manager: %v", err)
	}
	defer cacheManager.Close()
	
	gitHandler := git.NewHandler(cfg, cacheManager)
	if err := gitHandler.Initialize(); err != nil {
		log.Fatalf("Failed to initialize Git handler: %v", err)
	}
	
	color.Blue("📦 Mirroring Git repository: %s", url)
	repoPath, err := gitHandler.CacheRepository(url, branch)
	if err != nil {
		color.Red("❌ Failed to mirror repository: %v", err)
		os.Exit(1)
	}
	
	color.Green("✅ Repository cached at: %s", repoPath)
}

func listGitRepos(cfg *config.Config) {
	cacheManager := cache.NewManager(cfg)
	if err := cacheManager.Initialize(); err != nil {
		log.Fatalf("Failed to initialize cache manager: %v", err)
	}
	defer cacheManager.Close()
	
	gitHandler := git.NewHandler(cfg, cacheManager)
	repositories, err := gitHandler.GetCachedRepositories()
	if err != nil {
		log.Fatalf("Failed to list repositories: %v", err)
	}
	
	if len(repositories) == 0 {
		color.Yellow("ℹ️  No repositories cached")
		return
	}
	
	color.Blue("📋 Cached Git repositories:")
	for _, repo := range repositories {
		sizeMB := float64(repo.SizeBytes) / (1024 * 1024)
		fmt.Printf("  📁 %s\n", repo.Name)
		fmt.Printf("     URL: %s\n", repo.URL)
		fmt.Printf("     Size: %.2f MB\n", sizeMB)
		fmt.Printf("     Last commit: %s\n", repo.LastCommitDate)
		fmt.Printf("     Branch: %s\n", repo.Branch)
		fmt.Println()
	}
}

// PyPI commands
var pypiCmd = &cobra.Command{
	Use:   "pypi",
	Short: "Python package management",
}

var pypiMirrorCmd = &cobra.Command{
	Use:   "mirror [package]",
	Short: "Mirror a Python package",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		packageName := args[0]
		version, _ := cmd.Flags().GetString("version")
		noDeps, _ := cmd.Flags().GetBool("no-deps")
		
		color.Blue("📦 Mirroring Python package: %s", packageName)
		color.Yellow("ℹ️  PyPI mirroring not implemented yet")
		// TODO: Implement PyPI mirroring
		_, _ = version, noDeps
	},
}

func init() {
	pypiMirrorCmd.Flags().String("version", "", "Specific version to mirror")
	pypiMirrorCmd.Flags().Bool("no-deps", false, "Don't mirror dependencies")
	pypiCmd.AddCommand(pypiMirrorCmd)
}

// APT commands
var aptCmd = &cobra.Command{
	Use:   "apt",
	Short: "APT package management",
}

var aptMirrorCmd = &cobra.Command{
	Use:   "mirror",
	Short: "Mirror APT repository",
	Run: func(cmd *cobra.Command, args []string) {
		distribution, _ := cmd.Flags().GetString("distribution")
		release, _ := cmd.Flags().GetString("release")
		
		color.Blue("📦 Mirroring APT repository: %s %s", distribution, release)
		color.Yellow("ℹ️  APT mirroring not implemented yet")
		// TODO: Implement APT mirroring
	},
}

func init() {
	aptMirrorCmd.Flags().String("distribution", "ubuntu", "Distribution (ubuntu, debian)")
	aptMirrorCmd.Flags().String("release", "focal", "Release name")
	aptCmd.AddCommand(aptMirrorCmd)
}

// Hosts file management
var hostsCmd = &cobra.Command{
	Use:   "hosts",
	Short: "Hosts file management",
}

var hostsSetupCmd = &cobra.Command{
	Use:   "setup",
	Short: "Setup hosts file for offline mode",
	Run: func(cmd *cobra.Command, args []string) {
		color.Blue("🔧 Setting up hosts file for offline mode")
		color.Yellow("ℹ️  Hosts setup not implemented yet")
		// TODO: Implement hosts setup
	},
}

var hostsRestoreCmd = &cobra.Command{
	Use:   "restore",
	Short: "Restore original hosts file",
	Run: func(cmd *cobra.Command, args []string) {
		color.Blue("🔧 Restoring original hosts file")
		color.Yellow("ℹ️  Hosts restore not implemented yet")
		// TODO: Implement hosts restore
	},
}

func init() {
	hostsCmd.AddCommand(hostsSetupCmd)
	hostsCmd.AddCommand(hostsRestoreCmd)
}

// SSL certificate management
var sslCmd = &cobra.Command{
	Use:   "ssl",
	Short: "SSL certificate management",
}

var sslSetupCmd = &cobra.Command{
	Use:   "setup",
	Short: "Setup SSL certificates",
	Run: func(cmd *cobra.Command, args []string) {
		setupSSL(cfg)
	},
}

var sslInstallCmd = &cobra.Command{
	Use:   "install",
	Short: "Show commands to install CA certificate",
	Run: func(cmd *cobra.Command, args []string) {
		showSSLInstallCommands(cfg)
	},
}

func init() {
	sslCmd.AddCommand(sslSetupCmd)
	sslCmd.AddCommand(sslInstallCmd)
}

func setupSSL(cfg *config.Config) {
	sslManager := ssl.NewManager(cfg)
	if err := sslManager.Initialize(); err != nil {
		log.Fatalf("Failed to setup SSL: %v", err)
	}
	
	color.Green("🔒 SSL certificates generated successfully")
	fmt.Printf("   CA certificate: %s/ca.crt\n", cfg.SSL.CertDir)
	fmt.Printf("   Server certificate: %s/server.crt\n", cfg.SSL.CertDir)
}

func showSSLInstallCommands(cfg *config.Config) {
	sslManager := ssl.NewManager(cfg)
	
	color.Blue("🔧 Run these commands to install the CA certificate:")
	commands := sslManager.GetInstallCommands()
	for _, cmd := range commands {
		fmt.Println(cmd)
	}
}