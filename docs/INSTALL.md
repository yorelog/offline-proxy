# 安装和使用指南

本指南将帮助您安装和使用 Offline Proxy 来实现无网络环境下的开发工作。

## 系统要求

- Python 3.8 或更高版本
- Ubuntu/Debian Linux（推荐）
- 足够的磁盘空间用于缓存资源（建议至少 50GB）

## 安装步骤

### 1. 克隆项目

```bash
git clone <repository-url> offline_proxy
cd offline_proxy
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 安装项目

```bash
pip install -e .
```

## 配置

### 1. 配置文件

复制并编辑配置文件：

```bash
cp config/config.yaml config/config_custom.yaml
```

根据需要修改配置：

```yaml
# 代理服务器配置
proxy:
  http_port: 8080
  https_port: 8443
  bind_address: "0.0.0.0"
  mode: "cache"  # 在线缓存模式

# 缓存配置
cache:
  root_dir: "./data"
  max_size_gb: 50
  expire_days: 30
```

### 2. 创建必要目录

```bash
mkdir -p data logs certs
```

## 使用方法

### 阶段一：在线缓存资源

#### 1. 启动代理服务器（缓存模式）

```bash
offline-proxy server start --mode cache
```

#### 2. 配置系统代理

```bash
export http_proxy=http://localhost:8080
export https_proxy=http://localhost:8080
```

#### 3. 缓存 Git 仓库

```bash
# 方法1：通过CLI直接缓存
offline-proxy git mirror https://github.com/username/repository.git

# 方法2：通过正常的git操作自动缓存
git clone https://github.com/username/repository.git
```

#### 4. 缓存 Python 包

```bash
# 方法1：通过CLI直接缓存
offline-proxy pypi mirror requests
offline-proxy pypi mirror-requirements requirements.txt

# 方法2：通过正常的pip操作自动缓存
pip install requests numpy pandas
```

#### 5. 缓存 APT 包

```bash
# 缓存Ubuntu仓库
offline-proxy apt mirror --distribution ubuntu --release focal

# 正常使用apt（会自动缓存）
sudo apt update
sudo apt install curl wget vim
```

### 阶段二：离线使用

#### 1. 设置 SSL 证书

```bash
# 生成证书
offline-proxy ssl setup

# 安装CA证书
offline-proxy ssl install
```

#### 2. 配置 hosts 文件

```bash
# 自动配置hosts文件
sudo offline-proxy hosts setup
```

#### 3. 启动代理服务器（离线模式）

```bash
offline-proxy server start --mode offline
```

#### 4. 在离线环境下使用

```bash
# 设置代理环境变量
export http_proxy=http://localhost:8080
export https_proxy=http://localhost:8080

# 正常使用各种工具
git clone https://github.com/username/repository.git
pip install requests
sudo apt install curl
```

## 常用命令

### 服务器管理

```bash
# 启动服务器
offline-proxy server start --mode cache
offline-proxy server start --mode offline

# 查看服务器状态
offline-proxy server status
```

### 缓存管理

```bash
# 查看缓存统计
offline-proxy cache stats

# 清理缓存
offline-proxy cache clear
```

### Git 仓库管理

```bash
# 镜像仓库
offline-proxy git mirror https://github.com/user/repo.git

# 列出已缓存的仓库
offline-proxy git list
```

### Python 包管理

```bash
# 镜像单个包
offline-proxy pypi mirror requests

# 从requirements.txt镜像
offline-proxy pypi mirror-requirements requirements.txt
```

### APT 包管理

```bash
# 镜像APT仓库
offline-proxy apt mirror --distribution ubuntu --release focal
```

### 系统配置

```bash
# 设置hosts文件
sudo offline-proxy hosts setup

# 恢复hosts文件
sudo offline-proxy hosts restore

# 设置SSL证书
offline-proxy ssl setup
offline-proxy ssl install
```

## 高级配置

### 1. 自定义代理规则

编辑配置文件中的协议设置：

```yaml
protocols:
  http:
    enabled: true
    timeout: 30
  git:
    enabled: true
    services:
      - "github.com"
      - "gitlab.com"
      - "gitee.com"
  pypi:
    enabled: true
    index_url: "https://pypi.org/simple/"
```

### 2. 性能调优

```yaml
performance:
  worker_threads: 10
  connection_pool_size: 100
  memory_cache_mb: 512

cache:
  compression: true
  compression_algorithm: "zstd"
```

## 故障排除

### 常见问题

1. **SSL证书错误**
   ```bash
   # 重新生成证书
   offline-proxy ssl setup
   # 确保证书已安装
   offline-proxy ssl install
   ```

2. **权限错误**
   ```bash
   # hosts文件需要sudo权限
   sudo offline-proxy hosts setup
   ```

3. **代理不工作**
   ```bash
   # 检查代理配置
   echo $http_proxy
   echo $https_proxy
   
   # 检查服务器状态
   offline-proxy server status
   ```

4. **缓存空间不足**
   ```bash
   # 查看缓存使用情况
   offline-proxy cache stats
   
   # 清理缓存
   offline-proxy cache clear
   ```

### 日志调试

启用详细日志：

```bash
offline-proxy --verbose server start
```

查看日志文件：

```bash
tail -f logs/offline_proxy.log
```

## 最佳实践

1. **定期更新缓存**：在有网络时定期更新已缓存的资源
2. **监控磁盘空间**：确保有足够的磁盘空间存储缓存
3. **备份配置**：保存自定义的配置文件
4. **测试离线模式**：在完全断网前测试所有功能

## 安全注意事项

1. **SSL证书**：在生产环境中考虑使用正式的SSL证书
2. **访问控制**：配置防火墙限制代理服务器的访问
3. **数据隔离**：为不同项目使用不同的缓存目录

## 性能优化建议

1. **使用SSD存储**：将缓存目录放在SSD上提高性能
2. **调整缓存大小**：根据实际需求调整缓存限制
3. **启用压缩**：对于大型文件启用压缩可以节省空间