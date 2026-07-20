# CHANGELOG

## [0.2.0] - 2026-07-20

### Changed

- 将生产运行架构从独立 Qdrant 五容器调整为内嵌 Qdrant 四容器。
- 修正 Nginx 与 WordPress PHP-FPM 的 FastCGI 连接。
- 拆分 HTTP 引导配置与 HTTPS 正式配置。

### Added

- 增加公开索引 CLI、WordPress 初始化、证书申请、备份恢复和回滚脚本。
- 增加生产运行模式、并发限制、轻量健康检查和资源配额。
- 增加 2 核 2G 部署自动门禁与完整交接手册。

## [0.1.0] - 2026-07-18

### Added
- 项目初始化：独立生产仓库 `project-016-zwd-portfolio-production`
- 目录骨架：wordpress、rag-api、public-content、deploy、tests、tools、manifests
- 白名单同步脚本 `tools/sync-public-source.ps1`
- 安全配置：`.gitignore`、`.dockerignore`
- 部署配置目录：`deploy/docker-compose.production.yml`、`deploy/nginx/`、`deploy/scripts/`
- GitHub Actions CI 工作流目录
- 公开内容清单 `manifests/source-sync-manifest.json`
