# 阿里云 ECS 2 核 2G 生产部署优化执行交接手册 V1

> 项目：钟伟达个人网站生产部署
>
> 仓库：`luxiangyiz/tsss-portfolio-production`
>
> 目标环境：阿里云 ECS，2 vCPU、2 GiB、40 GiB ESSD Entry
>
> 推荐首发地域：中国香港（无需先完成 ICP 备案）
>
> 推荐系统：Ubuntu LTS 64 位
>
> 文档状态：部署前执行基线
>
> 更新时间：2026-07-20

---

## 1. 文档目的

本手册用于把当前生产仓库优化为适合 2 核 2G ECS 的低流量个人作品集，并指导交接人员完成服务器初始化、部署、域名、HTTPS、内容初始化、监控、备份、压测、上线和回滚。

本手册所说的“稳定运行”是指：

1. 在约定的访问量和并发范围内满足本手册的功能、性能和资源指标。
2. 任何关键故障都能够被检测，并能按既定步骤恢复或回滚。
3. 密钥、私有资料、数据库和管理端口不暴露到公网。
4. 部署版本、配置、数据备份和验收证据均可追溯。

单台 2 核 2G ECS 不具备高可用能力。云平台故障、香港至中国内地公网波动、第三方 LLM/Embedding API 故障不可能由单机部署完全消除。因此本方案通过资源约束、超时、限流、备份和回滚降低风险，但不承诺绝对零故障。

---

## 2. 系统范围

### 2.1 包含的服务

- Nginx：唯一公网入口、静态资源、反向代理、HTTPS、限流。
- WordPress PHP-FPM：个人网站页面和后台管理。
- MySQL：WordPress 数据库。
- FastAPI：公开 RAG 问答接口。
- Qdrant Local：以内嵌模式运行在 FastAPI 进程内，不再单独启动 Qdrant 容器。

### 2.2 不包含的能力

- 不在服务器上运行本地大模型。
- 不在服务器上运行本地 Embedding 模型。
- 不公开入库、内部搜索、内部问答或 API 文档接口。
- 不部署 private、internal 知识库。
- 不开放 MySQL、FastAPI、Qdrant 的公网端口。
- 不使用宝塔、LNMP 或额外预装的 WordPress。
- 首发阶段不承诺搜索引擎收录，默认保持 `noindex`，稳定观察后再单独放行。

---

## 3. 目标架构

```text
互联网访问者
     │
     ▼
阿里云安全组：仅开放 80/443，22 仅限管理员 IP
     │
     ▼
Nginx（64 MiB）
     ├── 静态资源 / WordPress PHP 请求
     │        ▼
     │   WordPress PHP-FPM（320 MiB）
     │        ▼
     │      MySQL（384 MiB）
     │
     └── /api/rag/*
              ▼
         FastAPI 单 Worker（512 MiB）
              ├── Qdrant Local 持久化目录
              ├── 9 份只读公开 Markdown
              ├── 远程 Embedding API
              └── 远程 LLM API
```

### 3.1 为什么移除独立 Qdrant 容器

当前公开知识库只有 9 份 Markdown，约 16.7 KB、242 行，预计约 40～70 个向量分块。独立 Qdrant 服务对这一规模没有必要。

当前代码在未设置 `QDRANT_URL` 时，已经能够通过 `QdrantClient(path=...)` 使用本地持久化模式。移除独立容器可以节省约 128～256 MiB，并减少一个健康检查和网络依赖。

### 3.2 内存预算

| 组件 | 硬上限/目标 | 说明 |
|---|---:|---|
| Nginx | 64 MiB | 低流量入口和静态资源 |
| WordPress PHP-FPM | 320 MiB | 限制 FPM 子进程 |
| MySQL | 384 MiB | 小型站点专用参数 |
| FastAPI + Qdrant Local | 512 MiB | 单 Worker，远程模型 |
| 系统、Docker、页缓存 | 约 700 MiB | 不设置为容器配额 |
| Swap | 2 GiB | 仅防止突发 OOM |

容器配额合计约 1.25 GiB，为系统和文件缓存保留约 0.75 GiB。

---

## 4. 容量边界与服务目标

### 4.1 允许的使用规模

| 指标 | 舒适范围 | 短时峰值 | 升级或限流触发值 |
|---|---:|---:|---:|
| 同时主动浏览人数 | 5 | 10 | 持续超过 15 |
| 缓存页面请求 | 3～5 次/秒 | 10 次/秒，30 秒内 | 持续超过 10 次/秒 |
| 未缓存动态请求 | 1～2 次/秒 | 3 次/秒 | 持续超过 3 次/秒 |
| 同时 RAG 请求 | 1 | 2 | 3 个及以上 |
| RAG 持续调用 | 2～3 次/分钟 | 5 次/分钟 | 持续超过 5 次/分钟 |
| WordPress 后台管理员 | 1 | 1 | 多人同时编辑 |
| 日页面浏览量 | 500～1500 PV | 3000 PV | 长期超过 3000 PV |
| 日 RAG 问答量 | 50～150 | 300 | 长期超过 300 |

### 4.2 性能目标

| 请求 | 验收目标 |
|---|---:|
| ECS 本机缓存页面 P95 | ≤ 500 ms |
| 外部访问缓存页面 P95 | ≤ 1.5 s |
| 未缓存 WordPress 页面 P95 | ≤ 1.5 s |
| WordPress 后台页面 P95 | ≤ 2 s |
| 本地向量检索 P95 | ≤ 200 ms，不含远程 Embedding |
| 完整 RAG 问答 P50 | ≤ 8 s |
| 完整 RAG 问答 P95 | ≤ 20 s |
| RAG 单次硬超时 | 45 s |
| 网站 HTTP 5xx 比例 | < 1% |
| RAG 超时和 5xx 合计 | < 5% |

### 4.3 可用性和恢复目标

- 月度可用性目标：99.5%，不含计划维护和第三方 API 故障。
- RPO：最长丢失 24 小时数据。
- RTO：一般故障 60 分钟内恢复。
- 代码回滚时间：15 分钟内。
- 备份恢复演练：首次上线前至少完成 1 次，以后每季度 1 次。

---

## 5. 当前仓库的 P0 阻断项

以下问题在修复前禁止直接执行 `deploy/scripts/deploy.sh`：

### P0-01：WordPress 上游协议错误

当前 Compose 使用 `wordpress:*-fpm-*` 镜像，但 Nginx 通过 `proxy_pass http://wordpress:80` 访问。PHP-FPM 不提供 HTTP 80 端口。

整改要求：

- Nginx 与 WordPress 通过 FastCGI 连接到 `wordpress:9000`。
- Nginx 只读挂载 `wordpress_data`，用于静态文件和 `SCRIPT_FILENAME`。
- PHP 请求使用 `fastcgi_pass`，静态资源由 Nginx 直接提供。

### P0-02：HTTPS 在无证书时强制启动

当前 Nginx 配置引用 `example.com` 证书，但 Compose 没有挂载证书目录，同时 80 端口强制跳转 HTTPS。

整改要求：

- 拆分 HTTP 引导配置和 HTTPS 正式配置。
- 首次启动只启用 HTTP 和 ACME Challenge。
- 证书签发成功后再启用 443 和 HTTP→HTTPS 跳转。
- `server_name` 和证书路径必须使用真实域名。

### P0-03：RAG 缺少公开资料挂载

RAG 配置的知识根目录是 `/app/public-content`，当前 Dockerfile 和 Compose 都没有提供该目录。

整改要求：

```yaml
volumes:
  - ../public-content:/app/public-content:ro
  - rag_data:/app/data/rag
```

### P0-04：生产运行模式会使容器退出

当前 Compose 设置 `RAG_RUNTIME_MODE=real_remote`，但 `validate_runtime_security()` 只接受 `offline_demo` 和 `real_local`。

整改要求：

- 增加明确的 `real_remote` 生产模式。
- 仅允许在 `APP_ENV=production`、`ALLOW_FAKE_MODE=false` 时使用。
- 生产模式允许服务绑定 `0.0.0.0`。
- 不得放宽 `offline_demo` 的本地监听限制。
- 为合法和非法组合补充自动测试。

### P0-05：独立 Qdrant 不符合 2G 优化目标

整改要求：

- 删除 Compose 中独立 `qdrant` 服务和相应 `depends_on`。
- 不设置 `QDRANT_URL`。
- 设置 `QDRANT_PATH=/app/data/rag/qdrant`。
- FastAPI 改为 1 个 Worker，避免两个进程同时锁定 Qdrant Local。

### P0-06：缺少生产公开索引命令

公开 API 刻意不挂载 `/ingest`，这是正确的安全设计，但当前生产仓库没有安全的离线索引入口。

整改要求：

- 新增受控 CLI，例如：

  ```bash
  python -m rag_app.cli index --scope public --mode full
  python -m rag_app.cli index --scope public --mode incremental
  ```

- CLI 固定只允许 `scope=public`。
- CLI 扫描结果必须是 9 个公开文档，拒绝项必须为 0。
- 索引时停止 FastAPI，避免 Qdrant Local 被两个进程并发打开：

  ```bash
  docker compose stop rag-api
  docker compose run --rm rag-index
  docker compose up -d rag-api
  ```

### P0-07：WordPress 初始化缺少 WP-CLI 执行面

插件提供了 `wp zwd seed` 和 `wp zwd verify`，但当前 Compose 没有 WP-CLI 服务，也没有把公开资料挂载到插件要求的目录。

整改要求：

- 增加仅在 `admin` profile 中启用的一次性 WP-CLI 服务。
- 挂载：

  ```text
  wordpress_data → /var/www/html
  public-content → /var/www/html/wp-content/zwd-public-sources（只读）
  主题和插件 → 对应 wp-content 路径（只读）
  ```

- 初始化顺序：

  ```bash
  wp plugin activate zwd-portfolio-core
  wp theme activate zwd-portfolio
  wp zwd seed
  wp zwd verify
  ```

### P0-08：备份脚本不适配当前仓库

已发现：

- 脚本直接引用未加载到 Shell 的 `MYSQL_ROOT_PASSWORD`。
- 脚本复制不存在的 `manifests/public-source-manifest.json`。
- Qdrant 备份仍按独立服务快照设计。

整改要求：

- 在脚本中安全读取 `deploy/.env.production`，禁止输出密钥。
- 清单文件改为实际存在的 `source-sync-manifest.json` 和 `repository-manifest.json`。
- Qdrant Local 备份必须在停止 `rag-api` 后复制数据目录，完成后立即恢复服务。
- 备份失败必须返回非零退出码。
- 新增备份完整性和恢复测试。

### P0-09：部署脚本没有保证切换到远程最新提交

当前 `git fetch origin` 后执行 `git checkout main`，不能保证本地 `main` 已快进到 `origin/main`。

整改要求：

- 默认部署明确的 Commit SHA 或 Tag。
- 首次部署可使用已核对的 `origin/main` Commit SHA。
- 部署前验证工作区干净。
- 禁止在服务器上修改受 Git 管理的文件。
- 部署记录必须包含 Commit SHA、时间和操作者。

---

## 6. 2G 生产配置整改要求

### 6.1 FastAPI

- Uvicorn Worker：`1`。
- 容器内存上限：512 MiB。
- `RAG_REQUEST_TIMEOUT=45`。
- 输入长度：最多 500 字符。
- 同时处理 RAG：最多 2 个。
- 超出并发时快速返回 429 或进入最大长度为 4 的短队列。
- 日志级别：`WARNING`。
- 禁止访问日志记录问题正文。
- 健康检查不得每次调用真实 LLM 和 Embedding；拆分为：
  - `/api/rag/public/health/live`：只检查进程存活。
  - `/api/rag/public/health/ready`：检查索引可读。
  - 第三方 API 深度检查由低频监控独立执行。

### 6.2 Qdrant Local

- 路径：`/app/data/rag/qdrant`。
- 使用命名卷 `rag_data`。
- 只建立 `kb_public` Collection。
- 禁止出现 `kb_private` 和 `kb_internal`。
- 单 FastAPI Worker。
- 索引任务和在线服务不得同时打开同一数据目录。

### 6.3 MySQL

建议参数：

```text
innodb_buffer_pool_size=96M
innodb_log_buffer_size=8M
max_connections=30
table_open_cache=256
tmp_table_size=16M
max_heap_table_size=16M
performance_schema=OFF
skip_name_resolve=ON
max_allowed_packet=32M
```

要求：

- 容器内存上限 384 MiB。
- 不暴露 3306。
- 数据保存到命名卷。
- 使用独立随机 root 密码和 WordPress 用户密码。

### 6.4 WordPress PHP-FPM

建议参数：

```text
pm=ondemand
pm.max_children=4
pm.process_idle_timeout=10s
pm.max_requests=300
memory_limit=128M
max_execution_time=30
upload_max_filesize=8M
post_max_size=10M
```

OPcache：

```text
opcache.enable=1
opcache.memory_consumption=64
opcache.interned_strings_buffer=8
opcache.max_accelerated_files=10000
opcache.validate_timestamps=0
```

要求：

- 容器内存上限 320 MiB。
- WordPress 后台只允许 1 名管理员低频使用。
- 禁止站内文件编辑和后台自动安装插件。
- WordPress Cron 改为系统定时任务，避免访问触发高峰。
- 只安装必要主题和 `zwd-portfolio-core` 插件。

### 6.5 Nginx

- 容器内存上限：64 MiB。
- Worker：`auto`，连接数无需超过 512。
- 开启 gzip 或 brotli 中已验证的一种，不同时引入未经验证模块。
- 静态资源缓存 30 天，带内容哈希的资源使用 immutable。
- HTML/FastCGI 微缓存 30～60 秒；登录用户、后台、预览和 Cookie 用户绕过缓存。
- RAG 问答接口禁止缓存。
- 请求体不超过 10 MiB。
- WordPress 登录路径单独限流。
- `/api/rag/` 每 IP 不超过 10 次/分钟，突发 2～5 次。
- 隐藏版本响应头。
- 日志单文件 5 MiB，最多保留 2～3 份。

---

## 7. 云资源选择

### 7.1 首发测试环境

```text
地域：中国香港
实例：2 vCPU / 2 GiB，经济型 e
系统盘：40 GiB ESSD Entry
系统：Ubuntu LTS 64 位
公网：分配 IPv4
应用镜像：不预装；若页面强制要求则只选 Docker
```

### 7.2 安全组

入方向：

| 端口 | 来源 | 用途 |
|---|---|---|
| 22/TCP | 管理员当前公网 IP `/32` | SSH |
| 80/TCP | `0.0.0.0/0` | HTTP 和证书验证 |
| 443/TCP | `0.0.0.0/0` | HTTPS |

禁止开放：

- 3306：MySQL。
- 8000：FastAPI。
- 6333/6334：Qdrant。
- Docker API 2375/2376。

### 7.3 域名

- 根域名和 `www` 使用 A 记录指向 ECS 公网 IP。
- DNS TTL 初次设置为 600 秒。
- HTTPS 验收完成后再将 TTL 调高。
- 香港服务器无需先完成 ICP 备案；如果迁移到中国内地服务器，必须先完成相应备案。

---

## 8. 服务器初始化

以下命令以 Ubuntu 为例。所有操作都要记录执行时间和结果。

### 8.1 账号和 SSH

1. 首次使用控制台或密钥登录。
2. 创建非 root 部署账号。
3. 使用 SSH 公钥登录。
4. 验证新账号能够使用 `sudo` 后，再禁用 root 密码登录。
5. 只在阿里云安全组允许管理员 IP 访问 22。
6. 不把私钥、服务器密码或 API Key粘贴到聊天、GitHub Issue 或文档。

### 8.2 系统更新

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo timedatectl set-timezone Asia/Shanghai
```

### 8.3 创建 2 GiB Swap

执行前先用 `swapon --show` 确认未创建同等 Swap。

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-zwd-memory.conf
echo 'vm.vfs_cache_pressure=50' | sudo tee -a /etc/sysctl.d/99-zwd-memory.conf
sudo sysctl --system
```

验收：

```bash
free -h
swapon --show
```

必须看到约 2 GiB Swap，权限必须为 `600`。

### 8.4 安装 Docker

按阿里云或 Docker 官方 Ubuntu 指南安装 Docker Engine、Buildx 和 Compose Plugin，不使用来源不明的一键脚本。

验收：

```bash
sudo docker version
sudo docker compose version
sudo systemctl is-enabled docker
sudo systemctl is-active docker
```

四项必须成功。

### 8.5 Docker 日志和磁盘保护

配置 Docker 日志轮转，单日志建议 5 MiB、最多 3 份。修改后重启 Docker，并确认没有业务容器时再执行。

磁盘规则：

- 使用率达到 70%：告警。
- 达到 80%：停止非必要构建和备份，立即清理。
- 达到 90%：阻止部署并进入故障处理。

---

## 9. GitHub 私有仓库接入

推荐使用只读 Deploy Key：

1. 在服务器部署账号下生成专用 ED25519 密钥。
2. 私钥只保存在服务器，权限 `600`。
3. 将公钥添加到 GitHub 仓库 Deploy keys。
4. 不勾选写权限。
5. 验证：

   ```bash
   ssh -T git@github.com
   ```

6. 克隆到固定目录，例如：

   ```bash
   sudo mkdir -p /opt/zwd
   sudo chown <DEPLOY_USER>:<DEPLOY_USER> /opt/zwd
   git clone git@github.com:luxiangyiz/tsss-portfolio-production.git /opt/zwd/portfolio
   cd /opt/zwd/portfolio
   git status
   ```

禁止使用：

- 把 GitHub Token 写入 remote URL。
- 把个人 SSH 私钥复制进仓库。
- 在服务器仓库中直接开发。

---

## 10. 生产环境变量

复制模板：

```bash
cd /opt/zwd/portfolio
cp deploy/production.env.example deploy/.env.production
chmod 600 deploy/.env.production
```

必须填写：

```text
WORDPRESS_SITE_URL
MYSQL_ROOT_PASSWORD
MYSQL_DB_PASSWORD
WORDPRESS_DB_PASSWORD
CORS_ORIGINS
EMBEDDING_PROVIDER
EMBEDDING_MODEL
EMBEDDING_BASE_URL
EMBEDDING_API_KEY
LLM_PROVIDER
LLM_MODEL
LLM_BASE_URL
LLM_API_KEY
QDRANT_PATH=/app/data/rag/qdrant
```

要求：

- MySQL root 密码和 WordPress 数据库密码不同。
- 每个密码至少 32 个随机字符。
- `.env.production` 不得被 Git 跟踪。
- `git status --short` 必须看不到环境文件。
- 不在日志中执行 `cat deploy/.env.production`。
- 不把真实环境文件复制回本地生产仓库。

---

## 11. 部署流程

### 11.1 发布前闸门

以下全部满足才能部署：

- GitHub Actions 全部通过。
- 指定 Commit SHA 已记录。
- 全新克隆验收通过。
- P0-01 至 P0-09 已修复并测试。
- `docker compose config` 通过。
- 环境文件权限为 `600`。
- 安全组没有开放内部端口。
- 备份和回滚命令已完成空环境演练。

### 11.2 HTTP 引导部署

首次只启动 HTTP：

1. 使用 HTTP Nginx 配置。
2. 启动 MySQL、WordPress、FastAPI 和 Nginx。
3. 检查容器：

   ```bash
   sudo docker compose \
     -f deploy/docker-compose.production.yml \
     --env-file deploy/.env.production \
     ps
   ```

4. 检查日志，不得打印密钥和问题正文。
5. 本机验证：

   ```bash
   curl -I http://127.0.0.1/
   curl -fsS http://127.0.0.1/api/rag/public/health/live
   ```

### 11.3 WordPress 初始化

在一次性 WP-CLI 容器中：

```bash
wp core is-installed
wp plugin activate zwd-portfolio-core
wp theme activate zwd-portfolio
wp zwd seed
wp zwd verify
```

验收：

- 5 个公开页面存在。
- 2 个项目存在。
- 无默认示例文章。
- 首页设置正确。
- 主题和插件已激活。
- 联系方式只出现在批准页面。
- 首发阶段 `blog_public=0`。

### 11.4 建立公开索引

```bash
sudo docker compose stop rag-api
sudo docker compose run --rm rag-index \
  python -m rag_app.cli index --scope public --mode full
sudo docker compose up -d rag-api
```

索引结果必须满足：

- 扫描文件：9。
- 纳入文件：9。
- 拒绝文件：0。
- Collection：只有 `kb_public`。
- Chunk 数：大于 0。
- 不存在 `kb_private`、`kb_internal`。
- 连续执行增量索引时 `written_chunks=0`。

### 11.5 域名和 HTTPS

1. DNS A 记录生效。
2. 使用 HTTP ACME Challenge 申请证书。
3. 确认证书包含根域名和实际使用的 `www` 域名。
4. 挂载证书目录。
5. 切换 HTTPS Nginx 配置。
6. 重新加载 Nginx。
7. 验证：

   ```bash
   curl -I http://<DOMAIN>
   curl -I https://<DOMAIN>
   ```

要求：

- HTTP 返回 301 到 HTTPS。
- HTTPS 返回 200。
- 证书域名、有效期和链完整。
- HSTS 只在确认 HTTPS 稳定后启用。
- 证书自动续期必须完成一次 dry-run。

---

## 12. 功能验收

### 12.1 网站页面

必须验证：

- 首页。
- 关于我。
- 项目列表。
- 两个项目详情。
- 简历。
- 联系方式。
- 404 页面。
- 手机端和桌面端导航。
- 静态资源无 404。
- 浏览器控制台无阻断级错误。

### 12.2 WordPress

- 后台只允许 HTTPS。
- 管理员密码为独立强密码。
- 后台文件编辑被禁用。
- 评论和 Pingback 关闭。
- XML-RPC 根据实际需求禁用。
- 未登录用户不能访问管理能力。
- WordPress Site Health 无严重错误。

### 12.3 RAG

至少准备 10 个固定问题：

- 6 个有明确公开证据的问题。
- 2 个证据不足、应拒答的问题。
- 2 个涉及 private/internal 信息、必须拒答的问题。

必须满足：

- 有证据问题返回公开引用。
- 引用只包含公开文档标题、章节和片段。
- 证据不足时明确拒答。
- private/internal 问题没有敏感引用。
- 公开 API 不存在 `/ingest`、内部 `/search`、内部 `/ask`。
- 输入超过 500 字符被拒绝。
- 同一 IP 超限返回 429。
- API 错误不返回堆栈、密钥或内部路径。

---

## 13. 负载和稳定性验收

压测必须从另一台机器发起，不在 2G ECS 本机制造负载。

### 13.1 预热

- 连续访问首页、关于、项目、简历各 5 次。
- 完成 2 次正常 RAG 问答。
- 等待 5 分钟，记录基线资源。

### 13.2 页面负载

阶段 A：

- 5 个虚拟用户。
- 持续 15 分钟。
- 浏览首页、关于、项目、简历。

阶段 B：

- 10 个虚拟用户。
- 持续 30 秒。
- 只访问缓存页面。

通过标准：

- 外部页面 P95 ≤ 1.5 秒。
- HTTP 5xx < 1%。
- 容器重启次数为 0。
- 无 OOM。

### 13.3 RAG 负载

- 30 分钟内完成 10 次固定问题测试。
- 正常阶段同时只发送 1 个问题。
- 另做 5 轮双并发短测。
- 不进行 3 并发以上测试，生产策略应在此前限流。

通过标准：

- P50 ≤ 8 秒。
- P95 ≤ 20 秒。
- 超时和 5xx合计 < 5%。
- 双并发时无容器重启。
- 回答隐私边界全部正确。

### 13.4 混合场景

连续 30 分钟：

- 5 名虚拟访客浏览页面。
- 每 3 分钟发起 1 次 RAG 问答。
- 期间由 1 名管理员登录后台，完成 1 次页面保存和预览。

通过标准：

- 页面 P95 ≤ 1.5 秒。
- 后台 P95 ≤ 2 秒。
- RAG P95 ≤ 20 秒。
- HTTP 5xx < 1%。
- 无 OOM、无容器重启、无磁盘异常。

---

## 14. 资源验收

### 14.1 空闲 15 分钟

- 内存使用建议 1.2～1.5 GiB。
- `MemAvailable` ≥ 300 MiB。
- Swap 使用建议接近 0，必须 ≤ 100 MiB。
- 1 分钟 Load Average < 0.7。
- 容器重启数为 0。

### 14.2 混合压测期间

- `MemAvailable` ≥ 150 MiB。
- Swap 持续使用 ≤ 256 MiB。
- 1 分钟 Load Average ≤ 1.5。
- CPU 持续 10 分钟不得超过 85%。
- I/O Wait 持续值 < 10%。
- 磁盘使用率 < 70%。
- 内核日志没有 OOM Kill。

检查命令：

```bash
free -h
vmstat 1 10
uptime
df -h
sudo docker stats --no-stream
sudo docker compose -f deploy/docker-compose.production.yml ps
sudo journalctl -k --since "1 hour ago" | grep -i -E "oom|out of memory|killed process"
```

---

## 15. 监控和告警

最低监控项：

- ECS CPU、内存、磁盘、带宽。
- 容器运行状态和重启次数。
- 首页 HTTPS 状态。
- RAG liveness 和 readiness。
- 证书剩余有效期。
- 最近一次备份时间和大小。
- 5xx、429 和 RAG 超时比例。

建议阈值：

| 指标 | 告警 |
|---|---|
| CPU | 连续 10 分钟 > 85% |
| MemAvailable | 连续 5 分钟 < 200 MiB |
| Swap | 连续 10 分钟 > 512 MiB |
| 磁盘 | > 70% 告警，> 80% 严重 |
| 首页 | 连续 3 次非 200/301 |
| RAG readiness | 连续 3 次失败 |
| 容器重启 | 1 小时内 ≥ 2 次 |
| 证书 | 剩余 < 21 天 |
| 备份 | 26 小时内无成功备份 |

深度调用 LLM 的监控频率不得过高，建议 30～60 分钟一次，避免额外费用和流量。

---

## 16. 备份策略

### 16.1 备份内容

- MySQL 全库。
- WordPress uploads。
- Qdrant Local 数据。
- Git Commit SHA。
- `source-sync-manifest.json`。
- `repository-manifest.json`。
- 脱敏后的配置结构，不包含真实密钥。

### 16.2 周期

- 每日一次，保留 7 份。
- 每周一份异机备份，保留 4 份。
- 每次生产部署前执行一次。
- 数据恢复前再执行一次现场备份。

### 16.3 备份要求

- 备份文件不得进入 Git。
- 备份目录权限仅部署账号可读。
- Qdrant Local 备份期间短暂停止 RAG，网站其他页面保持可用。
- 备份完成后验证文件非空、可解压、包含版本信息。
- 至少一份备份保存到 ECS 之外，例如阿里云 OSS。
- 40 GiB 系统盘的本地备份总占用不得超过 8 GiB。

---

## 17. 发布与回滚

### 17.1 发布

1. 记录目标 Commit SHA。
2. 运行部署前备份。
3. 验证工作区干净。
4. Fetch远程。
5. 检出明确 Commit。
6. 执行 Compose 配置检查。
7. 构建 RAG 镜像。
8. 依次更新服务。
9. 执行健康检查和冒烟测试。
10. 记录发布结果。

### 17.2 自动回滚触发条件

发布后 10 分钟内出现以下任一项，立即回滚：

- 首页连续 3 次 5xx。
- WordPress 无法连接数据库。
- RAG liveness 失败。
- 任一核心容器持续重启。
- 发生 OOM Kill。
- 公开接口暴露内部或入库路由。
- 发现密钥或 private/internal 内容泄露。

### 17.3 手动降级策略

如果只有第三方 LLM 或 Embedding 故障：

- 保持网站页面在线。
- 暂时关闭 RAG 表单或显示“问答服务维护中”。
- 不允许切换到 Fake 模型对外回答。

如果资源持续不足：

1. 暂停 RAG 在线问答。
2. 保留 WordPress 和静态页面。
3. 排查异常容器和请求。
4. 无法恢复时回滚。
5. 长期超过容量边界则升级到 4 GiB。

---

## 18. 最终验收标准

### 18.1 P0 上线阻断项

以下任何一项失败，都不得上线：

- [x] P0-01 至 P0-09 全部整改完成（2026-07-20，本地代码与容器链路验收通过）。
- [ ] GitHub Actions 全绿。
- [ ] 全新克隆验收通过。
- [ ] 服务器仅开放 22、80、443，22 已限制来源。
- [ ] 真实 `.env.production` 未进入 Git。
- [ ] 所有容器健康，无循环重启。
- [ ] HTTPS 证书正确且自动续期 dry-run 通过。
- [ ] WordPress `wp zwd verify` 通过。
- [ ] 公开索引只有 `kb_public`。
- [ ] 9 份公开资料全部入库，拒绝数为 0。
- [ ] 私有和内部问题测试全部拒答。
- [ ] 备份成功且完成一次恢复演练。
- [ ] 混合压测 30 分钟通过。
- [ ] 无 OOM Kill。

### 18.2 P1 稳定性指标

- [ ] 页面外部 P95 ≤ 1.5 秒。
- [ ] WordPress 后台 P95 ≤ 2 秒。
- [ ] RAG P50 ≤ 8 秒、P95 ≤ 20 秒。
- [ ] 网站 5xx < 1%。
- [ ] RAG 超时和 5xx < 5%。
- [ ] `MemAvailable` 压测期间 ≥ 150 MiB。
- [ ] Swap 压测期间持续使用 ≤ 256 MiB。
- [ ] 1 分钟 Load Average ≤ 1.5。
- [ ] 磁盘使用率 < 70%。
- [ ] 容器重启次数为 0。

### 18.3 放行结论

- P0 全部通过、P1 全部通过：允许上线。
- P0 全部通过、P1 有一项轻微偏差：不得直接放行，需复测或由项目负责人书面接受风险。
- 任一 P0 失败：禁止上线，必须整改。

---

## 19. 上线后观察期

首次上线后设置 7 天观察期：

- 第 1 天：每 2 小时检查一次。
- 第 2～3 天：每天检查 3 次。
- 第 4～7 天：每天检查 1 次。

每天记录：

- 页面可用性。
- RAG成功率和超时。
- CPU、内存、Swap、磁盘。
- 容器重启次数。
- 异常日志。
- 备份状态。
- 第三方 API 消耗。

观察期内保持搜索引擎 `noindex`。完成 7 天观察、隐私复核和备案策略确认后，再由项目负责人决定是否开放搜索引擎索引。

---

## 20. 升级到 4G 的明确条件

出现以下任一情况，应升级而不是继续压缩：

- 任意一次无法解释的 OOM Kill。
- `MemAvailable` 连续 5 分钟低于 200 MiB。
- Swap 连续 10 分钟超过 512 MiB。
- CPU连续 10 分钟超过85%。
- RAG经常出现2个以上同时请求。
- 页面P95连续超过2秒。
- 日页面浏览量长期超过3000 PV。
- 日RAG问答长期超过300次。
- 需要安装更多重量级插件或加入新后台服务。

---

## 21. 交接产物清单

交接人员必须提供：

- [ ] 最终部署 Commit SHA。
- [ ] 脱敏后的 Compose 配置。
- [ ] Nginx HTTP 和 HTTPS 配置。
- [ ] PHP-FPM 和 MySQL 2G 参数。
- [ ] RAG 公开索引命令及输出。
- [ ] WordPress 初始化和验收输出。
- [ ] 安全组截图或导出。
- [ ] HTTPS证书和续期验证结果。
- [ ] 30分钟混合压测报告。
- [ ] 资源监控截图。
- [ ] 备份文件清单和恢复演练记录。
- [ ] 上线验收表。
- [ ] 回滚演练结果。

真实密钥、数据库密码、SSH 私钥不得出现在交接文档和截图中。

---

## 22. 推荐实施顺序

1. [已完成，2026-07-20] 在本地完成 P0-01 至 P0-09 的代码整改。
2. 补充 2G Compose、PHP、MySQL、Nginx 和 CLI 测试。
3. 本地 Docker 完整启动并验收。
4. 提交 Git，等待 GitHub Actions 全绿。
5. 创建 2 核 2G 香港 ECS。
6. 完成服务器初始化、Swap、Docker和安全组。
7. 配置只读 Deploy Key 并克隆指定 Commit。
8. 创建生产环境变量。
9. 执行 HTTP 引导部署。
10. 初始化 WordPress 和公开索引。
11. 配置域名与 HTTPS。
12. 执行功能、安全、资源和混合压测。
13. 完成备份恢复和回滚演练。
14. P0/P1 全部通过后放行。
15. 进入 7 天观察期。

---

## 23. 官方参考

- 阿里云 ICP 备案流程：<https://help.aliyun.com/zh/icp-filing/basic-icp-service/user-guide/icp-filing-application-overview>
- 阿里云个人网站备案要求：<https://help.aliyun.com/zh/icp-filing/basic-icp-service/getting-started/quick-start-for-icp-filing-for-personal-websites>
- 阿里云 ECS 安装 Docker：<https://help.aliyun.com/en/ecs/user-guide/install-and-use-docker>
- 阿里云地域选择说明：<https://help.aliyun.com/zh/ecs/user-guide/regions-and-zones>
