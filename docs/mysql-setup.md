# WSL2、Ubuntu 与 Docker MySQL 初始化

本文使用以下安装路线：

```text
Windows
  → WSL2
  → Ubuntu
  → Docker Engine + Docker CLI
  → MySQL 容器和 patent_tutor 数据库
```

本文不安装 Docker Desktop。Docker CLI 只是客户端，不能单独运行容器，因此必须同时安装
Docker Engine 和 containerd。本文不包含项目环境变量、应用连接或数据库迁移步骤。

## 1. 下载并安装 WSL2

### 1.1 系统要求

- Windows 11，或满足 WSL 要求的 Windows 10。
- BIOS/UEFI 中已启用 CPU 虚拟化。
- 使用具有管理员权限的 Windows 账号完成安装。

### 1.2 从官方页面安装

只从 Microsoft 官方入口下载和安装 WSL：

- [Microsoft Store：Windows Subsystem for Linux](https://apps.microsoft.com/detail/9p9tqf7mrm4r)
- [Microsoft：安装 WSL](https://learn.microsoft.com/zh-cn/windows/wsl/install)

在 Microsoft Store 页面点击 **安装/获取**。安装完成后按照系统提示重新启动 Windows。不要
从第三方下载站获取 WSL 安装包。

如果 Microsoft Store 页面无法使用，按照 Microsoft 安装文档中的官方替代方法处理。

## 2. 下载并安装 Ubuntu

WSL2 是 Windows 中运行 Linux 的底层平台，Ubuntu 是运行在 WSL2 上的 Linux 发行版。由于
本文不使用 Docker Desktop，因此需要安装 Ubuntu，并在 Ubuntu 内运行 Docker Engine。

### 2.1 从 Microsoft Store 安装 Ubuntu

使用以下任一官方入口：

- [Microsoft Store：Ubuntu](https://apps.microsoft.com/detail/9pdxgncfsczv)
- [Canonical：在 WSL2 上安装 Ubuntu](https://documentation.ubuntu.com/wsl/latest/guides/install-ubuntu-wsl2/)

安装步骤：

1. 打开 Microsoft Store 的 Ubuntu 页面。
2. 确认发布者为 **Canonical Group Limited**。
3. 点击 **安装/获取**，等待下载完成。
4. 从 Windows 开始菜单打开 **Ubuntu**。
5. 首次启动会解压和初始化文件系统，等待终端出现用户名提示。

### 2.2 创建 Ubuntu 用户

首次启动 Ubuntu 时，根据提示输入：

1. Linux 用户名，例如 `patentdev`。
2. Linux 密码。
3. 再次输入密码确认。

输入密码时终端不会显示字符或星号，这是 Linux 的正常安全行为。该用户名和密码属于
Ubuntu，与 Windows 账号和 MySQL 密码无关。后续执行 `sudo` 命令时使用这里设置的 Linux
密码。

### 2.3 确认 Ubuntu 使用 WSL2

关闭 Ubuntu，在 Windows PowerShell 中执行：

```powershell
wsl --list --verbose
```

输出中 Ubuntu 对应的 `VERSION` 应为 `2`。如果显示 `1`，执行：

```powershell
wsl --set-version Ubuntu 2
```

发行版名称必须与 `wsl --list --verbose` 输出一致；例如显示 `Ubuntu-24.04` 时，应使用：

```powershell
wsl --set-version Ubuntu-24.04 2
```

转换完成后再次运行 `wsl --list --verbose`，确认版本为 `2`。

### 2.4 更新 Ubuntu

从开始菜单重新打开 Ubuntu，在 Ubuntu 终端中执行：

```bash
sudo apt update
sudo apt upgrade -y
```

至此，WSL2 和 Ubuntu 安装完成。后续命令都在 Ubuntu 终端中执行。

## 3. 安装 Docker Engine 和 Docker CLI

使用 Docker 官方 Ubuntu 软件仓库，不安装 Docker Desktop，也不使用 Ubuntu 自带的非官方
`docker.io` 包。

官方参考：

- [Docker：在 Ubuntu 上安装 Docker Engine](https://docs.docker.com/engine/install/ubuntu/)

### 3.1 添加 Docker 官方仓库

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

继续执行：

```bash
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

更新软件包索引：

```bash
sudo apt update
```

### 3.2 安装 Engine、CLI 和 containerd

```bash
sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

各软件包的作用：

| 软件包 | 作用 |
|---|---|
| `docker-ce` | Docker Engine 守护进程，实际创建和运行容器 |
| `docker-ce-cli` | `docker` 命令行客户端 |
| `containerd.io` | 容器运行时 |
| `docker-buildx-plugin` | Docker 镜像构建插件 |
| `docker-compose-plugin` | `docker compose` 插件 |

### 3.3 启动并验证 Docker

```bash
sudo systemctl start docker
sudo systemctl status docker --no-pager
sudo docker run --rm hello-world
```

`hello-world` 输出成功提示后，说明 Docker Engine 和 Docker CLI 已经可以正常工作。本文后续
统一使用 `sudo docker`，不修改 Docker 用户组权限。

如果 `systemctl` 提示系统没有以 systemd 启动，先参考
[Microsoft：在 WSL 中使用 systemd](https://learn.microsoft.com/zh-cn/windows/wsl/systemd)。
在 Ubuntu 中执行：

```bash
sudo nano /etc/wsl.conf
```

加入：

```ini
[boot]
systemd=true
```

保存并退出后，在 Windows PowerShell 中执行：

```powershell
wsl --shutdown
```

重新打开 Ubuntu，再执行本节的 Docker 启动和验证命令。

## 4. 拉取 MySQL 官方镜像

本项目要求 MySQL 8.0 及以上。这里固定使用 MySQL 8.4 LTS，避免 `latest` 标签将来自动切换到
不兼容的主版本。

```bash
sudo docker pull mysql:8.4
```

镜像来源：

- [Docker Hub：MySQL 官方镜像](https://hub.docker.com/_/mysql)

## 5. 创建持久化数据卷

创建项目专用 Docker 数据卷：

```bash
sudo docker volume create patent-tutor-mysql-data
```

该数据卷保存 MySQL 数据。删除或重建容器时，只要保留数据卷，数据库数据就不会随容器一起
删除。

## 6. 创建 MySQL 容器和数据库

以下命令使用这些固定名称：

| 配置 | 值 |
|---|---|
| Docker 容器 | `patent-tutor-mysql` |
| Docker 数据卷 | `patent-tutor-mysql-data` |
| MySQL 镜像 | `mysql:8.4` |
| MySQL 端口 | `3306` |
| 数据库 | `patent_tutor` |
| 应用账号 | `patent_tutor` |
| root 示例密码 | `PatentTutorRoot_2026!` |
| 应用账号示例密码 | `PatentTutorApp_2026!` |

示例密码只适合本地开发。执行前可以把两个密码替换成自己的强密码。

```bash
sudo docker run -d \
  --name patent-tutor-mysql \
  --restart unless-stopped \
  -p 3306:3306 \
  -v patent-tutor-mysql-data:/var/lib/mysql \
  -e MYSQL_ROOT_PASSWORD='PatentTutorRoot_2026!' \
  -e MYSQL_DATABASE='patent_tutor' \
  -e MYSQL_USER='patent_tutor' \
  -e MYSQL_PASSWORD='PatentTutorApp_2026!' \
  mysql:8.4 \
  --character-set-server=utf8mb4 \
  --collation-server=utf8mb4_0900_ai_ci
```

容器第一次使用空数据卷启动时，MySQL 官方镜像会自动：

1. 设置 `root` 用户密码。
2. 创建名为 `patent_tutor` 的数据库。
3. 创建名为 `patent_tutor` 的普通用户。
4. 把 `patent_tutor` 数据库的权限授予该普通用户。
5. 使用 `utf8mb4` 字符集和 `utf8mb4_0900_ai_ci` 排序规则。

## 7. 确认容器启动完成

查看容器状态：

```bash
sudo docker ps --filter name=patent-tutor-mysql
```

查看 MySQL 初始化日志：

```bash
sudo docker logs patent-tutor-mysql
```

日志出现 `ready for connections` 后，说明 MySQL 容器和初始化数据库已准备完成。

## 8. 重要说明

- `MYSQL_ROOT_PASSWORD`、`MYSQL_DATABASE`、`MYSQL_USER` 和 `MYSQL_PASSWORD` 只在空数据卷首次
  初始化时生效。
- 容器已经产生数据后，即使修改上述参数并重启容器，也不会修改已有数据库、用户或密码。
- 不要将真实密码提交到 Git、截图、聊天记录或公开文档。
- 不要使用空 root 密码。
- Docker CLI 不能独立运行容器；本方案同时安装了 Docker Engine 和 containerd。
- 本方案不安装 Docker Desktop，Docker 服务运行在 Ubuntu/WSL2 内。
- 本文到 MySQL 容器和 `patent_tutor` 数据库创建完成为止，不包含后续项目配置。
