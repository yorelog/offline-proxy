#!/bin/bash
# Offline Proxy 示例脚本：设置离线环境

set -e

echo "🔧 设置离线环境..."

# 1. 生成SSL证书
echo "🔒 生成SSL证书..."
offline-proxy ssl setup

# 2. 安装CA证书
echo "📜 安装CA证书..."
offline-proxy ssl install

# 3. 备份并配置hosts文件
echo "🌐 配置hosts文件..."
sudo offline-proxy hosts setup

# 4. 启动离线代理服务器
echo "🚀 启动离线代理服务器..."
offline-proxy server start --mode offline &

# 等待服务器启动
sleep 5

# 5. 配置环境变量
echo "⚙️  配置环境变量..."
export http_proxy=http://localhost:8080
export https_proxy=http://localhost:8080

# 6. 测试离线功能
echo "🧪 测试离线功能..."

echo "测试Git克隆..."
git clone https://github.com/python/cpython.git /tmp/cpython-test || echo "Git测试失败"

echo "测试Python包安装..."
uv pip install --no-cache requests || echo "Python包安装测试失败"

echo "测试APT包安装..."
sudo apt install curl || echo "APT包安装测试失败"

# 清理测试文件
rm -rf /tmp/cpython-test

echo "✅ 离线环境设置完成！"
echo "💡 请确保在 ~/.bashrc 中添加代理环境变量："
echo "export http_proxy=http://localhost:8080"
echo "export https_proxy=http://localhost:8080"