# Offline Proxy

一个支持多协议的离线代理工具，允许在有网络环境下缓存各种网络资源，并在无网络环境下通过本地代理服务提供这些资源。

## 功能特性

- **多协议支持**: HTTP/HTTPS、Git、APT、PyPI 等
- **智能缓存**: 自动发现和缓存依赖资源
- **离线服务**: 通过本地代理服务器提供缓存的资源
- **SSL证书管理**: 自动生成和管理自签名证书
- **资源管理**: 智能发现缺失资源和清理过期资源
- **易于配置**: 简单的配置文件和命令行工具

## 支持的操作

- `git clone` - Git 仓库克隆
- `curl` - HTTP/HTTPS 请求
- `apt install` - Ubuntu/Debian 包安装
- `pip install` - Python 包安装
- `uv` - 现代 Python 包管理工具

## 项目结构

```
offline_proxy/
├── src/                    # 源代码
│   ├── proxy/             # 代理服务器模块
│   ├── cache/             # 缓存管理模块
│   ├── protocols/         # 协议支持模块
│   ├── ssl/               # SSL证书管理
│   └── cli/               # 命令行工具
├── config/                # 配置文件
├── data/                  # 缓存数据存储
├── certs/                 # SSL证书存储
├── docs/                  # 文档
└── examples/              # 使用示例
```

## 快速开始

### 1. 有网络环境下的设置

```bash
# 安装依赖
uv pip install -r requirements.txt

# 启动代理服务器（缓存模式）
python -m offline_proxy.cli start --mode cache

# 配置系统代理或特定应用的代理设置
export http_proxy=http://localhost:8080
export https_proxy=http://localhost:8080
```

### 2. 无网络环境下的使用

```bash
# 启动代理服务器（离线模式）
python -m offline_proxy.cli start --mode offline

# 配置hosts文件
sudo python -m offline_proxy.cli setup-hosts

# 安装SSL证书
sudo python -m offline_proxy.cli install-certs
```

## 工作原理

1. **缓存阶段（有网络）**:
   - 启动代理服务器监听请求
   - 拦截并转发网络请求
   - 缓存响应数据和相关元数据
   - 记录依赖关系

2. **离线阶段（无网络）**:
   - 修改hosts文件将域名指向本地
   - 安装自签名SSL证书
   - 启动本地代理服务器
   - 从缓存中响应请求

## 配置

主要配置文件位于 `config/config.yaml`，包含：

- 代理服务器端口配置
- 缓存策略设置
- 支持的协议配置
- SSL证书配置
- 资源清理策略

## 开发

```bash
# 开发环境设置
uv venv .venv
source .venv/bin/activate.fish  # 或 activate 对于 bash/zsh
uv pip install -r requirements-dev.txt

# 运行测试
pytest tests/

# 代码格式化
black src/
isort src/
```

## 许可证

MIT License