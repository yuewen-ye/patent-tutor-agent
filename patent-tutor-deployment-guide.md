# Patent Tutor 部署指南git reset --hard HEAD~1 

## 1. 环境信息

| 项目 | 值 |
| --- | --- |
| 服务器域名 | htc.goip.it |
| 公网 IP | 180.165.48.19 |
| 内网 IP | 192.168.10.218 |
| SSH 端口 | 2222 |
| 登录用户 | leo（`su` 可切 root，密码相同） |
| 路由器 | OpenWrt 软路由 192.168.10.1（VMware 虚拟机），由管理员维护 |
| 外网访问 | 前端 http://htc.goip.it:28080/ ，接口文档 http://htc.goip.it:28080/api/docs |
| 代码仓库 | https://github.com/yuewen-ye/patent-tutor-agent.git（main 分支） |

## 2. 架构一览

```
外网用户 → 路由器 28080(TCP) 端口转发 → 服务器 80(nginx)
                                           ├─ /          前端静态文件（/opt/patent-tutor-frontend）
                                           ├─ /api/      反代到 127.0.0.1:8000（剥掉 /api 前缀）
                                           └─ /openapi.json  精确代理到后端（Swagger 依赖）
后端 FastAPI(uvicorn) 绑定 127.0.0.1:8000，systemd 服务 patent-tutor 管理
MySQL 本地 3306，数据库 patent_tutor（18 张表）
本地 RAG：bge-m3 + bge-reranker-v2-m3 + milvus_lite
```

要点：
- 选 28080 作外网入口，是因为国内电信家宽常封锁入站 80/443/8080，高位端口最稳。
- 前端与后端同源（同域名同端口），无跨域问题。
- 前后端均为 HTTP 明文；若长期公网开放，建议后续上 HTTPS。

## 3. 后端部署

以下为新机重部署时的步骤概要（当前服务器已完成）。

1. 安装系统依赖：git、Python 3.11+、nginx、mysql-server。
2. 拉代码：
```
git clone https://github.com/yuewen-ye/patent-tutor-agent.git /opt/patent-tutor-agent
```
3. 包管理一律用 uv + .venv（不要用 pip）：
```
cd /opt/patent-tutor-agent
uv venv
uv pip install -r requirements.txt
```
（具体依赖清单以仓库 README 为准）
4. 创建 /opt/patent-tutor-agent/.env，写入数据库连接串与模型路径，权限设为 600。模型路径由仓库自带的下载脚本自动回写，不要手改。
5. 用仓库自带脚本下载 RAG 模型到 models/bge-m3、models/bge-reranker-v2-m3。
6. MySQL 建库建用户并执行迁移：数据库 patent_tutor，用户 patent@localhost（密码见 .env，勿外传）。
7. systemd 服务：unit 文件位于 /etc/systemd/system/patent-tutor.service（开机自启、崩溃自动重启）。重部署时直接从现有服务器复制该文件即可。
```
systemctl daemon-reload
systemctl enable --now patent-tutor
```

注意：服务重启后首个请求会触发模型冷加载，约 15~30 秒，属正常现象。

## 4. 前端构建与部署

### 4.1 构建（在任意装有 Node 18+ 的机器上）

```
cd frontend
npm install
VITE_API_BASE_URL=/api npx vite build
```

Windows PowerShell 下：
```
$env:VITE_API_BASE_URL="/api"
npx vite build
```

要点：
- 必须把 VITE_API_BASE_URL 烧成 /api，前端才会走同源反代；不设置会默认请求 localhost:8000，线上必挂。
- 仓库当前有 3 个历史 TypeScript 类型错误（CoursePage.tsx 两处未使用变量、SessionPage.tsx 一处类型不匹配），`npm run build` 会因 tsc 报错失败。直接用 `npx vite build` 绕过类型检查即可，不影响运行。建议后续修复。

### 4.2 上传与部署

在**本地电脑**（不是服务器）打包并上传：
```
tar -czf frontend-dist.tar.gz -C dist .
scp -P 2222 frontend-dist.tar.gz leo@htc.goip.it:~/
```

在服务器上解压（用绝对路径，避免 ~ 指向歧义）：
```
sudo mkdir -p /opt/patent-tutor-frontend
sudo tar -xzf /home/leo/frontend-dist.tar.gz -C /opt/patent-tutor-frontend
```

静态文件覆盖不需要重启任何服务，刷新浏览器即生效。

## 5. nginx 配置

配置文件位于 /etc/nginx/sites-available/patent-tutor，当前生效内容：

```
server {
    listen 80 default_server;
    server_name _;

    root /opt/patent-tutor-frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location = /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_connect_timeout 10s;
    }
}
```

要点：
- `location = /openapi.json` 这条精确代理**不能删**。Swagger 文档页要从根路径取 openapi.json，没有这条会被前端的 try_files 回退成 index.html，文档页报 "Unable to render this definition"。
- /api/ 超时设 300 秒，容忍 RAG 冷加载与长 LLM 调用。
- 改完必须 `nginx -t && systemctl reload nginx` 验证后生效。
- 项目空间 /deploy/patent-tutor-sync.sh 同级归档了该配置备份；最新含修复版本以服务器上的为准。

## 6. 路由器端口转发

规则：外部 28080(TCP) → 192.168.10.218:80。

- 路由器管理密码不在我们手中，规则由管理员（admin）配置，需要变更端口时直接联系管理员。
- 路由器 SSH（22 端口）开放，但密码未知；dropbear 密码错误会立即断开连接，属正常现象，不要反复试密码。
- 验证转发是否生效（在任意电脑执行）：
```
tcping 180.165.48.19 28080
```
显示 Port is open 即通。

## 7. 部署验收清单

按顺序逐项确认：
1. `systemctl status patent-tutor` —— 服务 active (running)
2. `nginx -t` —— 配置语法通过
3. `curl http://127.0.0.1:8000/health` —— 后端健康检查（服务器内执行）
4. 浏览器打开 http://htc.goip.it:28080/ —— 前端页面正常加载
5. 浏览器打开 http://htc.goip.it:28080/api/docs —— Swagger 文档正常渲染
6. 页面上发起一次实际对话 —— 数据正常返回（首次较慢是冷加载）

## 8. Git 自动同步（15 分钟轮询）

已部署。逻辑：每 15 分钟（整点 :00/:15/:30/:45）检查 GitHub main 分支，有新提交才动作；前端有改动自动重新构建，后端有改动才重启服务（前端改动不重启，避免无谓冷加载）。日志在 /var/log/patent-tutor-sync.log。

组件（已归档到项目空间 /deploy，服务器上对应位置）：
- /usr/local/bin/patent-tutor-sync.sh —— 同步脚本
- /etc/systemd/system/patent-tutor-sync.service —— oneshot 服务
- /etc/systemd/system/patent-tutor-sync.timer —— 定时器

重新部署步骤：
1. 把 /deploy 下三个文件放到服务器对应位置，脚本加执行权限：
```
chmod +x /usr/local/bin/patent-tutor-sync.sh
```
2. 避免 root 操作 git 仓库报 dubious ownership：
```
git config --global --add safe.directory /opt/patent-tutor-agent
```
3. 前端自动构建依赖 Node（已装 20.x）：
```
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
```
4. 启用定时器：
```
systemctl daemon-reload && systemctl enable --now patent-tutor-sync.timer
```
5. 手动触发验证：
```
systemctl start patent-tutor-sync.service && tail -n 20 /var/log/patent-tutor-sync.log
```

日常查看：
```
systemctl list-timers patent-tutor-sync.timer
tail -n 50 /var/log/patent-tutor-sync.log
```

注意事项：
- 服务器时区是 UTC，list-timers 显示的时间比北京时间慢 8 小时，不是故障。
- 自动同步意味着"推了就上线"，只往 main 推验证过的代码。
- 若服务器本地有未提交改动，pull 会失败并记日志，不影响下次运行。

## 9. 踩坑记录

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `npm run build` 失败 | 仓库有 3 个历史 TS 类型错误，tsc 拦截 | 改用 `npx vite build` 绕过类型检查 |
| 线上页面请求 localhost:8000 | 构建时未设置 VITE_API_BASE_URL | 构建前设置 VITE_API_BASE_URL=/api |
| 多行命令粘贴后失效 | 本地终端把多行粘贴挤成一行 | 一律使用单行命令，一条一条执行 |
| heredoc 写 nginx 配置失败 | 同上，多行粘贴被挤行 | 配置文件改为下载链接 + curl 获取 |
| scp 报 Could not resolve hostname c: | 把本地命令误在服务器上执行 | scp 在本地电脑执行；服务器之间传文件用 curl 下载链接 |
| tar 报文件不存在 | root 用户的 ~ 是 /root，而文件在 /home/leo | 一律使用绝对路径 |
| Windows 下载的文件找不到 | 下载工具自动给文件名加了 _ 前缀 | 用 `ls` 或资源管理器确认真实文件名 |
| /api/docs 报 "Unable to render this definition" | Swagger 从根路径取 /openapi.json，被前端 try_files 回退成 index.html | nginx 增加 `location = /openapi.json` 精确代理 |
| root 下 git 操作报 dubious ownership | 仓库目录属主与执行用户不一致 | `git config --global --add safe.directory <仓库路径>` |
| 重启后首个请求很慢 | RAG 模型冷加载 | 正常现象，15~30 秒后恢复 |
| 路由器 ssh 输错密码立即断开 | dropbear 的正常行为 | 正常现象，勿频繁重试 |

## 10. 常用运维命令速查

```
systemctl status patent-tutor
systemctl restart patent-tutor
journalctl -u patent-tutor -n 200 --no-pager
nginx -t && systemctl reload nginx
tail -n 50 /var/log/patent-tutor-sync.log
systemctl list-timers patent-tutor-sync.timer
```

SSH 隧道（外网转发失效时应急）：
```
ssh -p 2222 -L 8000:127.0.0.1:8000 leo@htc.goip.it
```
然后浏览器打开 http://127.0.0.1:8000/docs。

## 11. 安全提醒

- /api/docs 目前公网可见，接口结构对外暴露。如需收敛，可用 nginx 把 /api/docs、/openapi.json 限制为内网访问。
- .env 含数据库密码与模型路径，权限 600，勿提交进 git、勿外传。
- 路由器管理密码由管理员掌握，端口规则变更需联系管理员。
- 建议后续：HTTPS、登录口令强度策略、定期备份 MySQL。