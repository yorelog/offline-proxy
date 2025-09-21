#!/bin/bash
# Offline Proxy 示例脚本：缓存开发环境资源

set -e

echo "🚀 开始缓存开发环境资源..."

# 配置代理
export http_proxy=http://localhost:8080
export https_proxy=http://localhost:8080

# 1. 缓存常用的Git仓库
echo "📦 缓存Git仓库..."
offline-proxy git mirror https://github.com/python/cpython.git
offline-proxy git mirror https://github.com/torvalds/linux.git
offline-proxy git mirror https://github.com/microsoft/vscode.git

# 2. 缓存Python开发环境
echo "🐍 缓存Python包..."
offline-proxy pypi mirror requests
offline-proxy pypi mirror numpy
offline-proxy pypi mirror pandas
offline-proxy pypi mirror flask
offline-proxy pypi mirror django
offline-proxy pypi mirror fastapi
offline-proxy pypi mirror pytest
offline-proxy pypi mirror black
offline-proxy pypi mirror mypy

# 从requirements.txt缓存
if [ -f "requirements.txt" ]; then
    offline-proxy pypi mirror-requirements requirements.txt
fi

# 3. 缓存APT包
echo "📋 缓存APT包..."
offline-proxy apt mirror --distribution ubuntu --release focal

# 4. 通过正常命令缓存资源
echo "⚙️  通过正常使用缓存资源..."

# Git操作
git clone https://github.com/git/git.git /tmp/git-test || true
rm -rf /tmp/git-test

# Python包安装
uv pip install --no-cache virtualenv setuptools wheel

# APT包安装
sudo apt update
sudo apt install -y curl wget vim git build-essential

echo "✅ 资源缓存完成！"

# 显示缓存统计
echo "📊 缓存统计："
offline-proxy cache stats