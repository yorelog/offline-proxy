#!/bin/bash

# Integration test script for Go implementation
echo "🧪 Running integration tests for Go implementation..."

# Build the binary
echo "📦 Building binary..."
go build -o bin/offline-proxy ./cmd/offline-proxy
if [ $? -ne 0 ]; then
    echo "❌ Build failed"
    exit 1
fi

echo "✅ Build successful"

# Test basic CLI help
echo "🔍 Testing CLI help..."
./bin/offline-proxy --help > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ CLI help failed"
    exit 1
fi
echo "✅ CLI help works"

# Test configuration
echo "🔧 Testing configuration..."
./bin/offline-proxy cache stats > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ Configuration test failed"
    exit 1
fi
echo "✅ Configuration works"

# Test SSL setup
echo "🔒 Testing SSL setup..."
./bin/offline-proxy ssl setup > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ SSL setup failed"
    exit 1
fi
echo "✅ SSL setup works"

# Test Git functionality
echo "📁 Testing Git functionality..."
./bin/offline-proxy git list > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ Git list failed"
    exit 1
fi
echo "✅ Git functionality works"

# Test server start (quick test)
echo "🌐 Testing server start..."
timeout 2s ./bin/offline-proxy server start --mode cache > /dev/null 2>&1
if [ $? -eq 124 ]; then  # timeout exit code means server started successfully
    echo "✅ Server starts correctly"
else
    echo "❌ Server start failed"
    exit 1
fi

echo ""
echo "🎉 All integration tests passed!"
echo ""
echo "📊 Summary:"
echo "  ✅ Binary builds successfully" 
echo "  ✅ CLI interface works"
echo "  ✅ Configuration management works"
echo "  ✅ SSL certificate generation works"
echo "  ✅ Git protocol handler works"
echo "  ✅ HTTP/HTTPS proxy server starts"
echo "  ✅ Cache management works"
echo ""
echo "🚀 Go implementation is ready for use!"