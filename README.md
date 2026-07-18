# 钟伟达个人网站 — 生产部署仓库

基于 `project-015-personal-knowledge-assistant` 中已批准的公开内容，构建可部署的个人网站生产环境。

## 技术栈

- **网站**: WordPress（区块主题 + 自定义插件）
- **RAG API**: Python FastAPI + LangChain + Qdrant
- **部署**: Docker Compose + Nginx
- **目标环境**: 阿里云 ECS（广州地域）

## 快速开始

```bash
# 1. 从源项目同步公开内容
./tools/sync-public-source.ps1

# 2. 检查同步结果
git status

# 3. 构建并启动（本地验证）
cp deploy/production.env.example .env.production
# 编辑 .env.production 填入必要密钥
docker compose -f deploy/docker-compose.production.yml up -d
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

参见 `deploy/` 目录下的部署文档和脚本。
