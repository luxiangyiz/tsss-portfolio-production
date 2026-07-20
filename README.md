# 钟伟达个人网站 — 生产部署仓库

基于 `project-015-personal-knowledge-assistant` 中已批准的公开内容，构建可部署的个人网站生产环境。

## 技术栈

- **网站**: WordPress（区块主题 + 自定义插件）
- **RAG API**: Python FastAPI + LangChain + 内嵌 Qdrant Local
- **部署**: Docker Compose + Nginx
- **目标环境**: 阿里云 ECS 2 核 2G（首发建议中国香港）

## 快速开始

```bash
# 1. 从源项目同步公开内容
./tools/sync-public-source.ps1

# 2. 检查同步结果
git status

# 3. 构建并启动 HTTP 引导环境（本地验证）
cp deploy/production.env.example deploy/.env.production
# 编辑 deploy/.env.production 填入必要密钥
docker compose \
  -f deploy/docker-compose.production.yml \
  --env-file deploy/.env.production \
  up -d
```

## 目录结构

```
├── wordpress/          # WordPress 主题和插件
├── rag-api/            # 公开 RAG API
├── public-content/     # 已批准的公开知识库内容
├── deploy/             # 部署配置和脚本
├── tests/              # 测试
├── tools/              # 开发工具（同步脚本等）
├── manifests/          # 同步清单
└── .github/            # CI/CD 工作流
```

## 安全说明

- 此仓库不包含任何密钥、私有数据或内部知识
- 所有公开内容均经过审批清单确认
- CI 流程自动检查密钥泄露和拒绝目录

## 部署

生产运行服务固定为 Nginx、WordPress PHP-FPM、MySQL 和 FastAPI 四个容器。
Qdrant 以内嵌模式保存在 `zwd_rag_data` 卷中，FastAPI 固定单 Worker。

执行顺序：

```bash
# 部署指定 Commit（默认 origin/main）
./deploy/scripts/deploy.sh <COMMIT_SHA>

# 初始化 WordPress
./deploy/scripts/init-wordpress.sh

# 首次建立公开索引
./deploy/scripts/index-public.sh full

# 后续增量更新
./deploy/scripts/index-public.sh incremental

# 域名解析完成后申请证书
./deploy/scripts/issue-certificate.sh

# 证书自动续期任务调用
./deploy/scripts/renew-certificate.sh

# WordPress 定时任务调用
./deploy/scripts/run-wordpress-cron.sh
```

服务器建议通过 `crontab -e` 添加：

```cron
*/5 * * * * cd /opt/zwd-portfolio-production && ./deploy/scripts/run-wordpress-cron.sh >> logs/wp-cron.log 2>&1
17 3 * * * cd /opt/zwd-portfolio-production && ./deploy/scripts/renew-certificate.sh >> logs/cert-renew.log 2>&1
```

完整步骤和验收标准参见：

`docs/阿里云ECS-2核2G生产部署优化执行交接手册-V1.md`
