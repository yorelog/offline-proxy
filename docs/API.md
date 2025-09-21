# API 文档

Offline Proxy 提供了命令行接口和编程接口来管理离线代理功能。

## 命令行接口 (CLI)

### 服务器管理

#### 启动服务器
```bash
offline-proxy server start [OPTIONS]
```

选项：
- `--mode [cache|offline]`: 服务器模式
- `--host TEXT`: 绑定地址
- `--http-port INTEGER`: HTTP端口
- `--https-port INTEGER`: HTTPS端口

示例：
```bash
# 启动缓存模式
offline-proxy server start --mode cache

# 启动离线模式
offline-proxy server start --mode offline --host 0.0.0.0
```

#### 服务器状态
```bash
offline-proxy server status
```

### 缓存管理

#### 查看缓存统计
```bash
offline-proxy cache stats
```

#### 清理缓存
```bash
offline-proxy cache clear
```

### Git 仓库管理

#### 镜像仓库
```bash
offline-proxy git mirror <URL> [OPTIONS]
```

选项：
- `--branch TEXT`: 指定分支（默认：main）

示例：
```bash
offline-proxy git mirror https://github.com/python/cpython.git --branch main
```

#### 列出缓存的仓库
```bash
offline-proxy git list
```

### Python 包管理

#### 镜像单个包
```bash
offline-proxy pypi mirror <PACKAGE> [OPTIONS]
```

选项：
- `--version TEXT`: 指定版本
- `--no-deps`: 不镜像依赖

示例：
```bash
offline-proxy pypi mirror requests --version 2.31.0
offline-proxy pypi mirror flask --no-deps
```

#### 从requirements.txt镜像
```bash
offline-proxy pypi mirror-requirements <FILE>
```

示例：
```bash
offline-proxy pypi mirror-requirements requirements.txt
```

### APT 包管理

#### 镜像APT仓库
```bash
offline-proxy apt mirror [OPTIONS]
```

选项：
- `--distribution TEXT`: 发行版（ubuntu, debian）
- `--release TEXT`: 版本名称
- `--components TEXT`: 组件（逗号分隔）
- `--architectures TEXT`: 架构（逗号分隔）

示例：
```bash
offline-proxy apt mirror --distribution ubuntu --release focal
offline-proxy apt mirror --distribution debian --release bullseye --components main,contrib
```

### 系统配置

#### 配置hosts文件
```bash
offline-proxy hosts setup [OPTIONS]
```

选项：
- `--backup/--no-backup`: 是否创建备份

#### 恢复hosts文件
```bash
offline-proxy hosts restore
```

#### 设置SSL证书
```bash
offline-proxy ssl setup
```

#### 显示证书安装命令
```bash
offline-proxy ssl install
```

## 编程接口 (API)

### 代理服务器

```python
from offline_proxy import ProxyServer
from offline_proxy.config import Config

# 加载配置
config = Config.load_from_file("config.yaml")

# 创建代理服务器
server = ProxyServer(config)

# 启动服务器
await server.start()

# 停止服务器
await server.stop()
```

### 缓存管理

```python
from offline_proxy.cache import CacheManager
from offline_proxy.config import Config

config = Config.load_from_file("config.yaml")
cache_manager = CacheManager(config)

# 初始化
await cache_manager.initialize()

# 获取缓存统计
stats = await cache_manager.get_cache_stats()
print(f"总条目: {stats['total_entries']}")
print(f"总大小: {stats['total_size_mb']:.2f} MB")

# 清理过期缓存
await cache_manager.cleanup_expired_cache()

# 关闭
await cache_manager.close()
```

### Git 协议处理

```python
from offline_proxy.protocols import GitProtocolHandler
from offline_proxy.cache import CacheManager
from offline_proxy.config import Config

config = Config.load_from_file("config.yaml")
cache_manager = CacheManager(config)
await cache_manager.initialize()

git_handler = GitProtocolHandler(config, cache_manager)
await git_handler.initialize()

# 缓存仓库
repo_path = await git_handler.cache_repository(
    "https://github.com/python/cpython.git",
    branch="main"
)

# 获取已缓存的仓库
repositories = await git_handler.get_cached_repositories()
for repo in repositories:
    print(f"仓库: {repo['name']}, 大小: {repo['size_bytes']} bytes")
```

### PyPI 协议处理

```python
from offline_proxy.protocols import PyPIProtocolHandler
from offline_proxy.cache import CacheManager
from offline_proxy.config import Config

config = Config.load_from_file("config.yaml")
cache_manager = CacheManager(config)
await cache_manager.initialize()

pypi_handler = PyPIProtocolHandler(config, cache_manager)
await pypi_handler.initialize()

# 镜像包
result = await pypi_handler.mirror_package("requests", include_dependencies=True)
print(f"镜像完成: {result['package_name']} v{result['version']}")

# 从requirements.txt镜像
result = await pypi_handler.mirror_requirements_file("requirements.txt")
print(f"成功镜像: {len(result['mirrored_packages'])} 个包")

# 启动PyPI镜像服务器
await pypi_handler.create_pypi_server(host="0.0.0.0", port=8082)
```

### APT 协议处理

```python
from offline_proxy.protocols import APTProtocolHandler
from offline_proxy.cache import CacheManager
from offline_proxy.config import Config

config = Config.load_from_file("config.yaml")
cache_manager = CacheManager(config)
await cache_manager.initialize()

apt_handler = APTProtocolHandler(config, cache_manager)
await apt_handler.initialize()

# 镜像仓库
await apt_handler.mirror_repository(
    distribution="ubuntu",
    release="focal",
    components=["main", "universe"],
    architectures=["amd64"]
)

# 搜索包
packages = await apt_handler.search_packages("python", "ubuntu", "focal")
for pkg in packages:
    print(f"包: {pkg.get('Package')}, 版本: {pkg.get('Version')}")

# 启动APT镜像服务器
await apt_handler.create_apt_server(host="0.0.0.0", port=8081)
```

### SSL 证书管理

```python
from offline_proxy.ssl import SSLManager
from offline_proxy.config import Config

config = Config.load_from_file("config.yaml")
ssl_manager = SSLManager(config)

# 初始化（生成证书）
await ssl_manager.initialize()

# 获取服务器SSL上下文
ssl_context = ssl_manager.get_server_ssl_context()

# 获取CA证书
ca_cert = ssl_manager.get_ca_certificate_pem()

# 为特定域名生成证书
await ssl_manager.generate_domain_certificate("example.com")

# 获取安装命令
commands = ssl_manager.install_ca_certificate_commands()
for cmd in commands:
    print(cmd)
```

### 配置管理

```python
from offline_proxy.config import Config

# 从文件加载配置
config = Config.load_from_file("config.yaml")

# 修改配置
config.proxy.mode = "offline"
config.proxy.http_port = 9080

# 保存配置
config.save_to_file("config_modified.yaml")

# 创建默认配置
default_config = Config()
default_config.save_to_file("config_default.yaml")
```

## 事件和回调

### 代理事件

```python
from offline_proxy import ProxyServer

class CustomProxyServer(ProxyServer):
    async def on_request_start(self, request):
        """请求开始事件"""
        print(f"请求开始: {request.url}")
        
    async def on_request_end(self, request, response):
        """请求结束事件"""
        print(f"请求结束: {request.url}, 状态: {response.status}")
        
    async def on_cache_hit(self, request):
        """缓存命中事件"""
        print(f"缓存命中: {request.url}")
        
    async def on_cache_miss(self, request):
        """缓存未命中事件"""
        print(f"缓存未命中: {request.url}")
```

## 错误处理

### 异常类型

```python
from offline_proxy.exceptions import (
    OfflineProxyError,          # 基础异常
    ConfigurationError,         # 配置错误
    CacheError,                # 缓存错误
    ProtocolError,             # 协议错误
    SSLError,                  # SSL错误
    NetworkError               # 网络错误
)

try:
    await server.start()
except ConfigurationError as e:
    print(f"配置错误: {e}")
except NetworkError as e:
    print(f"网络错误: {e}")
except OfflineProxyError as e:
    print(f"代理错误: {e}")
```

## 日志配置

```python
import logging
from offline_proxy.config import Config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('offline_proxy.log'),
        logging.StreamHandler()
    ]
)

# 设置特定模块的日志级别
logging.getLogger('offline_proxy.proxy').setLevel(logging.DEBUG)
logging.getLogger('offline_proxy.cache').setLevel(logging.INFO)
```