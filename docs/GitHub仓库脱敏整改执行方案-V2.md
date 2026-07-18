# GitHub 仓库脱敏整改执行方案 V2

- 项目：`project-016-zwd-portfolio-production`
- 源项目：`project-015-personal-knowledge-assistant`
- 文档版本：V2
- 编制日期：2026-07-18
- 当前状态：待执行
- 本版范围：仓库隔离、白名单同步、配置脱敏、敏感信息扫描、Manifest、Git 历史、GitHub Private 仓库和安全 CI
- 暂不包含：Docker 运行整改、阿里云 ECS、ICP备案、HTTPS、生产备份和正式上线

## 1. 方案目标

本方案用于把当前生产仓库整改为一个满足以下要求的 GitHub Private 仓库：

1. 仓库中只包含个人网站生产所需的公开源码、公开内容、测试和部署配置。
2. 私有知识、内部求职资料、密钥、本地索引、日志、备份和运行数据不进入仓库及 Git 历史。
3. 所有从 `project-015` 同步的文件都能够追溯到批准的源路径和内容哈希。
4. 白名单同步可以重复执行，源文件不变时不会产生业务文件差异。
5. GitHub CI 能够独立复核拒绝目录、敏感文件、真实密钥、公开内容元数据和 Manifest。
6. 从 GitHub 全新克隆后，仓库内容与本地批准状态一致，不依赖被 `.gitignore` 隐藏的必要文件。
7. 只有全部仓库脱敏验收通过后，才允许进入生产容器和服务器部署整改。

## 2. 当前验收基线

### 2.1 已通过部分

- `project-016` 与 `project-015` 为同级独立项目。
- `project-016` 已初始化 Git，当前分支为 `main`。
- Git 历史中没有发现私有知识目录、数据库、备份、Python 缓存或 WordPress 本地运行目录。
- 当前 9 份公开 Markdown 全部满足：
  - `privacy_level: public`
  - `publish_status: published`
  - `review_status: approved`
  - `verification_status: verified`
- 公开内容没有命中身份证、银行卡和私钥形态。
- 当前没有发现真实生产 API Key。

### 2.2 当前阻塞问题

| 编号 | 问题 | 风险 | 当前结论 |
|---|---|---|---|
| BASE-01 | GitHub Remote 尚未创建 | 无法验证 Private 权限和 CI | 未完成 |
| BASE-02 | `docs/` 尚未提交 | 工作区不是干净状态 | 未通过 |
| BASE-03 | Manifest 声明 125 个文件，Git 实际跟踪 133 个 | 清单不能代表实际仓库 | 未通过 |
| BASE-04 | Manifest 中有 2 个文件没有被 Git 跟踪 | 全新克隆会缺文件 | 未通过 |
| BASE-05 | 有 10 个生产文件未被 Manifest 覆盖 | 清单用途和边界不明确 | 未通过 |
| BASE-06 | Manifest 自身和同步脚本哈希不一致 | 完整性校验失败 | 未通过 |
| BASE-07 | Manifest 把自身纳入哈希 | 存在不可稳定的自引用哈希 | 设计错误 |
| BASE-08 | `.gitignore` 中 `data/` 规则误伤主题源码目录 | `navigation-items.js` 未进入 Git | 未通过 |
| BASE-09 | `.env.demo.example` 被忽略 | Manifest 与 Git 不一致 | 未通过 |
| BASE-10 | 当前 `rag_config.yaml` 包含源项目绝对路径和 private/internal 目录 | 生产仓库边界不纯 | 未通过 |
| BASE-11 | 同步脚本密钥扫描排除了 Markdown、YAML、JSON、PowerShell 等文件 | 存在明显扫描盲区 | 未通过 |
| BASE-12 | 公开 Markdown 校验只拒绝部分错误值，缺失字段也可能通过 | 未形成四字段强制门槛 | 未通过 |
| BASE-13 | CI 引用了不存在的 `.gitleaks.toml` | GitHub CI 无法可靠执行 | 未通过 |
| BASE-14 | 环境示例中存在 `sk-...` 令牌形态占位符 | 可能触发 Gitleaks，污染扫描结果 | 待整改 |
| BASE-15 | 当前没有经过全新克隆复验 | 无法证明仓库自包含 | 未完成 |

## 3. 脱敏边界

### 3.1 允许同步的源文件

只能从以下白名单路径同步：

```text
src/wordpress/themes/zwd-portfolio/
src/wordpress/plugins/zwd-portfolio-core/
src/rag_app/
requirements.txt
ai-job-knowledge-base/12-网站公开候选/
与生产公开能力直接相关的测试
```

配置文件不得继续原样同步。配置采用“生产仓库单独维护”的方式：

```text
project-016/rag-api/configs/rag_config.public.yaml
project-016/rag-api/.env.example
project-016/deploy/production.env.example
```

其中：

- `rag_config.public.yaml` 只能描述公开知识目录和公开 Collection。
- `.env.example` 只能包含变量名、安全默认值和无令牌形态占位符。
- 生产真实 `.env` 永远不进入源项目同步范围。

### 3.2 允许保留在生产仓库的自有文件

以下文件不是从源项目同步，而是在 `project-016` 单独维护：

```text
.github/
.gitattributes
.gitignore
.dockerignore
.gitleaks.toml
README.md
CHANGELOG.md
docs/
deploy/
rag-api/Dockerfile
tools/
manifests/
```

这些文件应进入“生产仓库文件清单”，但不应伪装成源项目同步文件。

### 3.3 绝对禁止进入仓库的内容

```text
.env
.env.production
*.env.local
真实 API Key、AccessKey、密码和令牌
SSH 私钥、TLS 私钥和 PFX 文件
ai-job-knowledge-base 中除 12-网站公开候选外的目录
data/rag/
Qdrant 本地存储
MySQL 数据和导出文件
logs/
backups/
WordPress uploads/
.wp-env-runtime/
node_modules/
__pycache__/
*.pyc
.venv/
venv/
数据库文件
压缩备份
开发机器用户目录和不必要的绝对路径
未批准公开的求职资料、薪资信息、证件信息和内部复盘
```

即使 GitHub 仓库为 Private，也必须按将来可能公开的标准脱敏。

## 4. 总体执行流程

```text
冻结当前仓库
→ 修正仓库边界和忽略规则
→ 拆分源同步文件与生产自有文件
→ 重写公开生产配置
→ 重构白名单同步脚本
→ 重构 Manifest
→ 执行工作区安全扫描
→ 清理并扫描 Git 历史
→ 建立本地验证脚本
→ 修复 GitHub CI
→ 全新克隆复验
→ 创建 GitHub Private 仓库
→ 启用分支保护
→ 最终脱敏验收
```

## 5. 阶段 A：冻结与备份当前状态

### 5.1 执行内容

1. 记录当前分支、Commit SHA 和工作区状态。
2. 导出当前 Git 提交列表。
3. 对当前仓库目录做一次本地临时备份，但备份不得放入 Git 工作区。
4. 在整改期间禁止创建 GitHub Public 仓库。
5. 在最终验收前不执行 `git push`。

### 5.2 证据

保存以下只读结果：

```powershell
git status --short --branch
git log --oneline --decorate --all
git ls-files
git remote -v
```

### 5.3 通过标准

- 能确定整改起点 Commit SHA。
- 临时备份位于项目目录外。
- 当前 GitHub Remote 为空或确认未发生推送。

## 6. 阶段 B：修正 `.gitignore` 与必要文件跟踪

### 6.1 修正规则

将过宽规则：

```gitignore
data/
```

改为只匹配仓库根目录运行数据：

```gitignore
/data/
```

避免误伤：

```text
wordpress/themes/zwd-portfolio/assets/src/data/
```

环境模板采用明确例外：

```gitignore
.env
.env.*
!.env.example
!.env.demo.example
!production.env.example
```

根据实际目录层级进一步写成：

```gitignore
/rag-api/.env
/rag-api/.env.*
!/rag-api/.env.example
!/rag-api/.env.demo.example

/deploy/.env.production
/deploy/.env.*
!/deploy/production.env.example
```

### 6.2 必须跟踪的缺失文件

整改后确认以下文件进入 Git：

```text
rag-api/.env.demo.example
wordpress/themes/zwd-portfolio/assets/src/data/navigation-items.js
docs/GitHub仓库脱敏整改执行方案-V2.md
```

### 6.3 验证命令

```powershell
git check-ignore -v rag-api/.env.demo.example
git check-ignore -v wordpress/themes/zwd-portfolio/assets/src/data/navigation-items.js
git ls-files --error-unmatch rag-api/.env.demo.example
git ls-files --error-unmatch wordpress/themes/zwd-portfolio/assets/src/data/navigation-items.js
```

### 6.4 通过标准

- 两个必要文件均被 Git 跟踪。
- 根目录运行数据仍被忽略。
- 真实 `.env` 仍无法被普通 `git add .` 添加。
- `git status --ignored` 中不存在被误忽略的必要源码。

## 7. 阶段 C：配置脱敏与生产公开边界

### 7.1 停止同步开发配置

从同步白名单中删除：

```text
configs/rag_config.yaml
configs/.env.example
configs/.env.demo.example
```

原因：

- 开发配置包含本机绝对路径。
- 开发配置包含 private/internal 知识目录。
- 开发默认范围不是 production public-only。
- 生产仓库需要独立配置生命周期。

### 7.2 新建公开生产配置

生产 RAG 配置至少包含：

```yaml
knowledge_base:
  root: "/app/public-content"
  include_dirs:
    - "."
  include_extensions:
    - ".md"
  exclude_patterns:
    - "README.md"

privacy:
  public_index_requirements:
    privacy_level: "public"
    publish_status: "published"
    review_status: "approved"
    verification_status: "verified"

collections:
  public: "kb_public"

rag:
  default_scope: "public"
  include_disputed: false
  top_k: 5
  chunk_size: 500
  chunk_overlap: 75
  relevance_threshold: 0.3
```

生产配置中禁止出现：

```text
kb_private
kb_internal
default_scope: internal
01-个人基础档案
02-教育与工作经历
……
11-AI学习与行业知识
E:\AI\codex_workspace
C:\Users
localhost 密钥服务地址
```

### 7.3 环境模板规则

错误示例：

```dotenv
LLM_API_KEY=sk-your-llm-key
```

正确示例：

```dotenv
LLM_API_KEY=replace-with-secret-at-deploy-time
```

或：

```dotenv
LLM_API_KEY=
```

环境模板不得使用任何真实令牌常见前缀。

### 7.4 验证命令

```powershell
rg -n "E:\\|C:\\Users|kb_private|kb_internal|default_scope.*internal" rag-api deploy
rg -n "sk-|ghp_|AKIA|LTAI|xox[baprs]-" .
```

### 7.5 通过标准

- 生产配置只包含公开目录和 `kb_public`。
- 不含开发电脑绝对路径。
- 不含 private/internal Collection。
- 环境模板中不存在真实密钥和令牌形态占位符。
- 配置文件全部被 Git 跟踪。

## 8. 阶段 D：重构白名单同步脚本

### 8.1 同步脚本职责

`tools/sync-public-source.ps1` 只负责：

1. 从批准的源路径复制业务源码和公开内容。
2. 排除缓存、运行数据和不允许的文件类型。
3. 删除目标中已从源项目撤回的同步文件。
4. 验证公开 Markdown 四字段。
5. 生成“源同步 Manifest”。
6. 在写入 Git 前执行目标目录安全扫描。

同步脚本不负责覆盖：

- 生产 Docker 配置。
- GitHub Actions。
- 生产 RAG 配置。
- README、文档和运维脚本。

### 8.2 白名单映射

```text
源：
src/wordpress/themes/zwd-portfolio/
目标：
wordpress/themes/zwd-portfolio/

源：
src/wordpress/plugins/zwd-portfolio-core/
目标：
wordpress/plugins/zwd-portfolio-core/

源：
src/rag_app/
目标：
rag-api/rag_app/

源：
requirements.txt
目标：
rag-api/requirements.txt

源：
ai-job-knowledge-base/12-网站公开候选/
目标：
public-content/

源：
批准的公开测试集合
目标：
tests/
```

### 8.3 复制排除规则

同步时必须排除：

```text
.gitkeep
__pycache__/
*.pyc
.pytest_cache/
node_modules/
.env
*.env.local
data/
logs/
backups/
数据库和压缩包
```

不得仅通过文件名字符串判断目录。应对每个源文件计算相对路径，并逐段判断是否包含拒绝目录。

### 8.4 删除同步残留

为防止删除生产仓库自有文件，同步脚本只能删除上一版“源同步 Manifest”中存在、但新一轮源文件清单中不存在的目标文件。

禁止直接遍历整个目标目录并删除“源项目中不存在”的文件。

### 8.5 四字段公开门槛

每份 `public-content/**/*.md` 必须明确包含：

```yaml
privacy_level: public
publish_status: published
review_status: approved
verification_status: verified
```

以下情况都必须失败：

- 字段缺失。
- 值为空。
- 值为 private/internal。
- 值为 draft/review/archived。
- review 状态不是 approved。
- verification 状态不是 verified。
- Front Matter 无法解析。

不得采用“只要没有写 private 就算 public”的反向判断。

### 8.6 幂等要求

Manifest 中不记录每次都会变化的全局同步时间到文件条目，或将时间与内容哈希分离。

源文件不变时连续执行两次：

```powershell
.\tools\sync-public-source.ps1
git diff --exit-code
.\tools\sync-public-source.ps1
git diff --exit-code
```

第二次不得产生任何业务文件或 Manifest 差异。

### 8.7 通过标准

- 白名单以外源路径无法进入目标项目。
- 缺少任一公开字段时脚本退出码非零。
- 源文件撤回后对应目标文件被安全删除。
- 生产自有文件不会被同步脚本删除。
- 连续执行两次完全幂等。

## 9. 阶段 E：重构 Manifest

### 9.1 清单分层

使用两个不同清单：

```text
manifests/source-sync-manifest.json
manifests/repository-manifest.json
```

#### `source-sync-manifest.json`

记录从 `project-015` 同步的文件：

```json
{
  "version": "2.0",
  "source_project": "project-015-personal-knowledge-assistant",
  "target_project": "project-016-zwd-portfolio-production",
  "files": [
    {
      "source_path": "src/rag_app/public_main.py",
      "target_path": "rag-api/rag_app/public_main.py",
      "sha256": "..."
    }
  ]
}
```

要求：

- `source_path` 必须为相对路径，不记录开发电脑绝对路径。
- `target_path` 必须为仓库相对路径。
- 哈希为目标文件 SHA-256。
- 文件数组按 `target_path` 排序。
- 不把 Manifest 自身纳入清单。

#### `repository-manifest.json`

记录当前 Git 跟踪文件及哈希，用于发布前完整性校验。

要求：

- 通过 `git ls-files` 获取跟踪文件。
- 排除 `repository-manifest.json` 自身。
- 可排除明确不需要完整性追踪的临时报告，但必须写入排除规则。
- 不扫描被忽略但未跟踪的文件作为正式仓库内容。

### 9.2 解决自引用哈希

Manifest 不能记录自己的哈希。否则每次生成 Manifest 都会改变自身内容，导致下一次哈希永远不一致。

采用以下任一方案：

1. 推荐：Manifest 明确排除自身。
2. 或由 Git Commit SHA 作为外部完整性锚点。

不得继续将 Manifest 自身作为普通条目记录。

### 9.3 Manifest 验证器

新增只读验证命令：

```text
tools/verify-manifest.py
```

验证器必须检查：

1. JSON 可以解析。
2. 必需字段存在。
3. `total_files` 与数组数量一致。
4. 每个目标文件真实存在。
5. 每个 SHA-256 与文件内容一致。
6. 不存在重复目标路径。
7. 不存在绝对源路径。
8. `source-sync-manifest` 中的目标文件全部被 Git 跟踪。
9. `repository-manifest` 与 `git ls-files` 一致。
10. Manifest 没有包含自身。

### 9.4 通过标准

- Manifest 验证器退出码为 0。
- 缺失文件数为 0。
- 哈希不一致数为 0。
- Manifest 未跟踪文件数为 0。
- Git 跟踪但未纳入仓库清单的文件数为 0。

## 10. 阶段 F：重构敏感信息扫描

### 10.1 扫描范围

扫描必须覆盖所有 Git 跟踪文本文件，包括：

```text
*.py
*.php
*.js
*.css
*.json
*.yaml
*.yml
*.md
*.txt
*.html
*.conf
*.sh
*.ps1
*.toml
*.env.example
```

不得再排除 Markdown、YAML、JSON、PowerShell 和 Shell。

### 10.2 扫描层次

#### 第一层：敏感文件名

```text
.env
*.pem
*.key
*.pfx
id_rsa
id_ed25519
credentials*
secret*
*.sqlite
*.db
*.dump
*.bak
```

#### 第二层：常见密钥形态

至少覆盖：

- OpenAI 及兼容 API Key。
- GitHub Token。
- 阿里云 AccessKey。
- AWS Access Key。
- Google API Key。
- Slack Token。
- JWT。
- SSH/TLS 私钥头。
- Basic Auth URL。
- 数据库连接串。
- 通用 `password/token/secret/api_key/access_key` 赋值。

#### 第三层：个人敏感信息

至少检查：

- 中国居民身份证号。
- 银行卡形态。
- 不在公开授权清单中的手机号。
- 精确家庭住址。
- 证件号和账号密码。

当前允许公开：

```text
微信号：Tsss9318
手机号：15059779318
邮箱：15059779318@163.com
```

允许项必须进入显式 allowlist，并限定：

- 允许出现的准确值。
- 允许出现的文件路径。
- 允许出现的用途。

不得使用“忽略所有手机号”这种宽泛规则。

#### 第四层：拒绝目录和路径

递归检查：

```text
private/
internal/
data/rag/
logs/
backups/
.wp-env-runtime/
node_modules/
__pycache__/
ai-job-knowledge-base/
```

生产仓库使用 `public-content/`，不应出现 `ai-job-knowledge-base/`。

### 10.3 Gitleaks 配置

二选一：

1. 使用 Gitleaks 官方默认规则，不传不存在的配置文件。
2. 新增经过测试的 `.gitleaks.toml`。

如果新增配置：

- 只能为已确认的示例值和已授权公开信息设置精确 allowlist。
- 禁止忽略整个文件类型。
- 禁止忽略 `deploy/`、`configs/` 或 `*.yaml`。
- CI 必须扫描完整 Git 历史。

### 10.4 扫描输出

安全扫描日志不得打印完整密钥值，只输出：

```text
规则编号
文件路径
行号
风险类型
```

### 10.5 通过标准

- 工作区扫描无有效密钥。
- Git 全历史扫描无有效密钥。
- 拒绝目录命中数为 0。
- 未授权个人敏感信息命中数为 0。
- 允许公开联系信息只出现在批准文件中。
- 扫描器自身测试包含正例和反例。

## 11. 阶段 G：Git 历史验收与必要清理

### 11.1 先扫描，不直接重写

执行：

```powershell
git log --all --name-only --pretty=format:
gitleaks git .
```

检查全部提交中的：

- 密钥。
- `.env`。
- 私有知识目录。
- 数据库和备份。
- 已删除但仍存在于历史中的敏感文件。

### 11.2 历史清理触发条件

只有出现以下情况才需要重写历史：

- 真实密钥曾经提交。
- 私有文件曾经提交。
- 数据库或备份曾经提交。
- 用户明确要求移除某项历史内容。

### 11.3 历史清理规则

若必须清理：

1. 先备份当前 `.git` 到项目外。
2. 使用 `git filter-repo`，不使用手工逐提交删除。
3. 清理后重新扫描全部 refs。
4. 如果真实密钥曾提交，必须同时撤销并轮换密钥。
5. GitHub 已存在时，历史重写和强制推送必须单独获得用户确认。

### 11.4 当前预期

根据本次只读验收，当前 3 个提交未发现真实密钥和拒绝目录，预计不需要重写历史。

但环境模板中的 `sk-...` 占位符应改为不带令牌前缀的值，并重新执行扫描。

### 11.5 通过标准

- 所有 Git refs 扫描通过。
- 不存在曾提交的 `.env` 和私有目录。
- 若发生密钥泄露，密钥已撤销并轮换。
- 清理后 Commit 历史和工作区均可正常读取。

## 12. 阶段 H：本地脱敏总验收脚本

新增：

```text
tools/verify-repository.ps1
```

该脚本只读执行以下检查：

1. 确认运行目录是 `project-016`。
2. 检查工作区是否干净。
3. 检查当前分支。
4. 检查必要文件是否被 Git 跟踪。
5. 检查拒绝目录和敏感文件名。
6. 执行工作区密钥扫描。
7. 执行 Git 历史密钥扫描。
8. 执行公开 Markdown 四字段校验。
9. 执行 Manifest 验证。
10. 检查所有 Git 跟踪文件能在磁盘找到。
11. 检查没有必要文件处于 ignored 状态。
12. 输出机器可读 JSON 报告。

建议输出：

```text
reports/repository-verification.json
```

该报告可以进入 Git，但不得包含密钥原文和开发电脑敏感绝对路径。

脚本退出规则：

```text
0 = 全部通过
1 = 存在阻塞项
2 = 验证环境错误
```

## 13. 阶段 I：修复 GitHub CI 安全闸门

### 13.1 CI 触发条件

```yaml
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  workflow_dispatch:
```

### 13.2 必须阻塞的 Job

#### `repository-boundary`

- 拒绝目录检查。
- 敏感文件名检查。
- 必要文件跟踪检查。

#### `secret-scan`

- Gitleaks 全历史扫描。
- 自定义个人信息扫描。

#### `public-content-gate`

- 公开 Markdown Front Matter 解析。
- 四字段强制检查。
- 联系信息 allowlist 路径检查。

#### `manifest-check`

- 执行 `tools/verify-manifest.py`。
- 校验哈希、路径、Git 跟踪状态和文件数量。

#### `sync-policy-test`

- 在临时目录模拟白名单同步。
- 检查拒绝文件不会进入目标。
- 检查字段缺失时同步失败。
- 检查连续同步两次无差异。

### 13.3 CI 禁止行为

- 禁止使用 `continue-on-error: true` 跳过安全失败。
- 禁止用 `||` 回退到更小测试集掩盖原命令失败。
- 禁止仅输出 warning 而继续发布。
- 禁止在 CI 日志打印 Secret。
- 禁止从源项目读取本机绝对路径。

### 13.4 通过标准

- 所有安全 Job 在 GitHub 上真实执行一次。
- 故意放入测试密钥时 CI 能失败。
- 删除公开字段时 CI 能失败。
- 修改文件但不更新 Manifest 时 CI 能失败。
- 恢复正常内容后 CI 全绿。

## 14. 阶段 J：全新克隆复验

### 14.1 目的

本地工作区可能包含被 Git 忽略但实际存在的文件，因此必须用全新克隆验证 GitHub 仓库是否自包含。

### 14.2 执行步骤

1. 在项目目录外创建临时验收目录。
2. 从 GitHub Private 仓库克隆 `main`。
3. 不复制本地任何隐藏文件。
4. 执行：

```powershell
.\tools\verify-repository.ps1
python tools/verify-manifest.py
```

5. 检查以下文件存在：

```text
rag-api/.env.example
rag-api/.env.demo.example
wordpress/themes/zwd-portfolio/assets/src/data/navigation-items.js
public-content 中 9 份 Markdown
.github/workflows/verify.yml
.gitleaks.toml 或明确使用默认配置
```

6. 验收后删除临时克隆目录。

### 14.3 通过标准

- 全新克隆无需源项目即可完成仓库脱敏验证。
- 必要文件缺失数为 0。
- Manifest 哈希不一致数为 0。
- Git 工作区保持干净。
- GitHub CI 与本地验证结果一致。

## 15. 阶段 K：创建 GitHub Private 仓库

### 15.1 用户准备

- GitHub 账号已完成双因素认证。
- 明确仓库名称。
- 确认仓库初始可见性为 Private。

建议名称：

```text
zwd-portfolio-production
```

### 15.2 创建规则

- 不勾选自动生成 README、License 或 `.gitignore`，避免与本地历史冲突。
- 添加本地 Remote 前再次运行完整本地验收。
- 首次 Push 后立即检查仓库可见性。
- 不创建 Public Fork。

### 15.3 Remote 验证

```powershell
git remote -v
git ls-remote origin
```

### 15.4 权限设置

- 仓库保持 Private。
- 仅授予必要协作者权限。
- Actions 采用只读默认权限。
- 发布流程需要人工批准时使用 GitHub Environment。
- 禁止把 GitHub Personal Access Token 写进仓库。

### 15.5 分支保护

对 `main` 配置：

- 必须通过 Pull Request。
- 必须通过全部安全检查。
- 禁止直接 Force Push。
- 禁止删除受保护分支。
- 至少保留线性或可追溯历史。

个人单人项目可以暂不强制他人 Review，但安全 CI 必须强制通过。

## 16. 仓库脱敏验收标准

以下均为硬性验收。任一项失败，不得进入部署阶段。

### 16.1 仓库隔离

| 编号 | 验收项 | 通过标准 |
|---|---|---|
| REP-01 | 项目位置 | `project-016` 与 `project-015` 同级，互不嵌套 |
| REP-02 | Git 仓库 | `project-016` 有独立 `.git` |
| REP-03 | GitHub 权限 | Remote 对应 Private 仓库 |
| REP-04 | 工作区状态 | 最终 `git status --porcelain` 为空 |
| REP-05 | 分支保护 | `main` 禁止绕过安全检查直接发布 |

### 16.2 白名单同步

| 编号 | 验收项 | 通过标准 |
|---|---|---|
| SYNC-01 | 路径白名单 | 只同步批准映射 |
| SYNC-02 | 拒绝目录 | private/internal/runtime 目录命中数为 0 |
| SYNC-03 | Python 缓存 | `__pycache__` 和 `*.pyc` 命中数为 0 |
| SYNC-04 | 撤回同步 | 源文件删除后目标同步文件可安全删除 |
| SYNC-05 | 自有文件保护 | 同步不会删除 deploy/docs/CI 等生产自有文件 |
| SYNC-06 | 幂等性 | 连续同步两次 Git 差异为 0 |
| SYNC-07 | 失败退出 | 任一安全校验失败时脚本退出码非零 |

### 16.3 公开内容

| 编号 | 验收项 | 通过标准 |
|---|---|---|
| PUB-01 | 公开等级 | 所有文档均为 `privacy_level: public` |
| PUB-02 | 发布状态 | 所有文档均为 `publish_status: published` |
| PUB-03 | 审核状态 | 所有文档均为 `review_status: approved` |
| PUB-04 | 验证状态 | 所有文档均为 `verification_status: verified` |
| PUB-05 | 缺失字段 | 任一必需字段缺失时 CI 必须失败 |
| PUB-06 | 联系信息 | 只允许批准值出现在批准文件 |
| PUB-07 | 未授权个人信息 | 命中数为 0 |

### 16.4 配置脱敏

| 编号 | 验收项 | 通过标准 |
|---|---|---|
| CFG-01 | 绝对路径 | 不含开发电脑绝对路径 |
| CFG-02 | 知识边界 | 不含 private/internal 目录 |
| CFG-03 | Collection | 只定义生产所需 `kb_public` |
| CFG-04 | 默认范围 | 默认检索范围为 public |
| CFG-05 | 环境模板 | 不含真实密钥和令牌形态占位符 |
| CFG-06 | 真实环境文件 | `.env` 和 `.env.production` 均未被跟踪 |

### 16.5 Manifest

| 编号 | 验收项 | 通过标准 |
|---|---|---|
| MAN-01 | JSON 结构 | 可以解析，必需字段完整 |
| MAN-02 | 文件数量 | 声明数量与数组数量一致 |
| MAN-03 | 文件存在 | 缺失数为 0 |
| MAN-04 | 哈希一致 | SHA-256 不一致数为 0 |
| MAN-05 | Git 跟踪 | 同步目标未跟踪数为 0 |
| MAN-06 | 绝对路径 | Manifest 不记录本机绝对路径 |
| MAN-07 | 自引用 | Manifest 不包含自身哈希 |
| MAN-08 | 重复路径 | 重复目标路径数为 0 |

### 16.6 密钥与敏感文件

| 编号 | 验收项 | 通过标准 |
|---|---|---|
| SEC-01 | 工作区密钥 | 有效密钥命中数为 0 |
| SEC-02 | Git 历史密钥 | 所有 refs 有效密钥命中数为 0 |
| SEC-03 | 私钥文件 | PEM、KEY、PFX 和 SSH 私钥命中数为 0 |
| SEC-04 | 数据文件 | DB、dump、backup、Qdrant 数据命中数为 0 |
| SEC-05 | 运行目录 | logs、uploads、node_modules、runtime 命中数为 0 |
| SEC-06 | 扫描覆盖 | Markdown、YAML、JSON、PS1、SH 全部纳入扫描 |
| SEC-07 | 日志脱敏 | 扫描报告不输出密钥原文 |

### 16.7 GitHub 与全新克隆

| 编号 | 验收项 | 通过标准 |
|---|---|---|
| GH-01 | 仓库可见性 | Private |
| GH-02 | CI 执行 | 全部安全 Job 至少真实成功一次 |
| GH-03 | 负向测试 | 测试密钥、字段缺失、Manifest 失配均能阻塞 CI |
| GH-04 | 全新克隆 | 必要文件完整，验证脚本通过 |
| GH-05 | 本地隐藏依赖 | 不依赖原工作区 ignored 文件 |
| GH-06 | 主分支保护 | 安全检查未通过时不能合并 |

## 17. 上线停止条件

出现以下任一情况，仓库不得进入 Docker 和服务器部署：

1. GitHub 仓库不是 Private。
2. 工作区或 Git 历史发现有效密钥。
3. 发现 private/internal 内容或目录。
4. 公开 Markdown 任一四字段不通过。
5. Manifest 存在缺失文件、哈希错误或未跟踪文件。
6. 必要源码被 `.gitignore` 误伤。
7. 全新克隆缺少必要文件。
8. Gitleaks 配置不存在或扫描未真实执行。
9. CI 使用 warning、fallback 或 `continue-on-error` 掩盖安全失败。
10. 当前 Git 工作区不干净且无法说明差异。

## 18. 建议提交顺序

为便于审计，建议拆分提交：

```text
1. fix: 修正忽略规则与必要文件跟踪
2. fix: 建立公开生产配置并移除开发配置
3. refactor: 重构白名单同步与四字段门槛
4. refactor: 拆分并验证 source/repository manifest
5. security: 完善敏感信息与 Git 历史扫描
6. ci: 建立仓库脱敏阻塞工作流
7. docs: 更新脱敏说明与验收报告
```

每个提交完成后运行本地验证，不得把所有整改混成一个不可审计的大提交。

## 19. 最终交付物

仓库脱敏阶段完成后必须交付：

1. 修正后的 `.gitignore` 和 `.dockerignore`。
2. 可运行的 `.gitleaks.toml`，或明确采用 Gitleaks 默认配置。
3. public-only RAG 配置。
4. 无真实密钥的环境模板。
5. 重构后的白名单同步脚本。
6. `source-sync-manifest.json`。
7. `repository-manifest.json`。
8. `verify-manifest.py`。
9. `verify-repository.ps1`。
10. 同步脚本、安全扫描器和 Manifest 验证器测试。
11. GitHub Private 仓库。
12. 已实际通过的 GitHub Actions 记录。
13. 全新克隆验收记录。
14. 最终仓库脱敏验收报告。

## 20. 最终放行规则

仓库脱敏阶段只有以下条件同时满足才算完成：

```text
本地验证全部通过
+ Git 历史扫描通过
+ Manifest 零差异
+ 公开内容四字段全部通过
+ GitHub 仓库为 Private
+ GitHub CI 全绿
+ 全新克隆复验通过
+ 工作区干净
```

完成后才允许编写并执行下一阶段：

```text
生产容器、RAG 运行、阿里云 ECS 与正式上线整改执行方案
```
