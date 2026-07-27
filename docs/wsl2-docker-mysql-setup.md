# WSL2 与 Docker MySQL 初始化

本文只说明以下内容：

1. 从官方页面下载安装 WSL2。
2. 安装并启用 Docker Desktop 的 WSL2 后端。
3. 使用 Docker 官方 MySQL 镜像创建 MySQL 容器。
4. 在容器首次启动时创建 `patent_tutor` 数据库和专用账号。

本文不包含项目环境变量配置、应用连接或数据库迁移步骤。

## 1. 下载并安装 WSL2

访问 Microsoft 官方安装页面：

- [Microsoft：安装 WSL](https://learn.microsoft.com/zh-cn/windows/wsl/install)

页面适用于 Windows 10 版本 2004（内部版本 19041）及以上或 Windows 11。按照页面引导完成
WSL 和 Ubuntu 的安装，然后重新启动 Windows。安装结束后，确认所安装的 Ubuntu 发行版运行
在 WSL2 模式。

本步骤只使用 Microsoft 官方页面或其指向的 Microsoft Store，不从第三方站点下载 WSL。

## 2. 下载并安装 Docker Desktop

访问 Docker 官方下载页面：

- [Docker：安装 Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
- [Docker：在 Windows 上使用 WSL2 后端](https://docs.docker.com/desktop/features/wsl/)

完成安装后打开 Docker Desktop：

1. 在 **Settings → General** 中启用 **Use WSL 2 based engine**。
2. 在 **Settings → Resources → WSL Integration** 中启用 Ubuntu。
3. 点击 **Apply**，等待 Docker Desktop 重新启动。

后续 Docker 命令均在已启用集成的 Ubuntu/WSL2 终端中执行。

## 3. 拉取 MySQL 官方镜像

本项目要求 MySQL 8.0 及以上。这里固定使用 MySQL 8.4 LTS，避免 `latest` 标签将来自动切换到
不兼容的主版本。

```bash
docker pull mysql:8.4
```

镜像来源：

- [Docker Hub：MySQL 官方镜像](https://hub.docker.com/_/mysql)

## 4. 创建持久化数据卷

创建项目专用 Docker 数据卷：

```bash
docker volume create patent-tutor-mysql-data
```

该数据卷保存 MySQL 数据。删除或重建容器时，只要保留数据卷，数据库数据就不会随容器一起
删除。

## 5. 创建 MySQL 容器和数据库

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
docker run -d \
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

## 6. 确认容器启动完成

查看容器状态：

```bash
docker ps --filter name=patent-tutor-mysql
```

查看 MySQL 初始化日志：

```bash
docker logs patent-tutor-mysql
```

日志出现 `ready for connections` 后，说明 MySQL 容器和初始化数据库已准备完成。

## 7. 重要说明

- `MYSQL_ROOT_PASSWORD`、`MYSQL_DATABASE`、`MYSQL_USER` 和 `MYSQL_PASSWORD` 只在空数据卷首次
  初始化时生效。
- 容器已经产生数据后，即使修改上述参数并重启容器，也不会修改已有数据库、用户或密码。
- 不要将真实密码提交到 Git、截图、聊天记录或公开文档。
- 不要使用空 root 密码。
- 本文到 MySQL 容器和 `patent_tutor` 数据库创建完成为止，不包含后续项目配置。
