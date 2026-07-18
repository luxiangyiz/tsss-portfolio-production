# 阶段 J/K — GitHub 移交说明

- 对应方案：`docs/GitHub仓库脱敏整改执行方案-V2.md` 阶段 J（全新克隆复验）和阶段 K（创建 GitHub Private 仓库）
- 前置条件：阶段 A-I 已全部完成，本地验收 11/11 通过
- 执行方式：**需用户 GitHub 账号操作**，以下为逐步说明

## 阶段 K：创建 GitHub Private 仓库

### K.1 准备工作

1. 确认 GitHub 账号已完成双因素认证（2FA）
2. 确认仓库名称（建议：`zwd-portfolio-production`）
3. 确认初始可见性为 **Private**

### K.2 创建仓库

在 GitHub 网页上：

1. 点击右上角 `+` → `New repository`
2. Repository name: `zwd-portfolio-production`
3. Visibility: **Private**（必须）
4. **不要勾选**：
   - ❌ Add a README file
   - ❌ Add .gitignore
   - ❌ Choose a license
   
   （避免与本地已有历史冲突）
5. 点击 `Create repository`

### K.3 添加 Remote 并首次推送

在本地 `project-016-zwd-portfolio-production` 目录下执行：

```bash
# 添加 remote（替换 YOUR_USERNAME）
git remote add origin git@github.com:YOUR_USERNAME/zwd-portfolio-production.git

# 首次推送前再次运行本地验收
./tools/verify-repository.ps1
# 确认 EXIT=0

# 推送
git push -u origin main
```

### K.4 验证仓库可见性

1. 在 GitHub 仓库页面确认显示 `Private` 标识
2. 执行验证：
   ```bash
   git remote -v
   git ls-remote origin
   ```

### K.5 权限设置

- 仓库保持 **Private**
- Settings → Actions → General → Workflow permissions: **Read and write**（或 Read-only，按需）
- **禁止**把 GitHub Personal Access Token 写进仓库
- 发布流程需要人工批准时使用 GitHub Environment

### K.6 分支保护

Settings → Branches → Add branch protection rule for `main`：

- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging
  - 选择全部 5 个 Job：`repository-boundary` / `secret-scan` / `public-content-gate` / `manifest-check` / `sync-policy-test`
  - ✅ Require branches to be up to date before merging
- ✅ Do not allow bypassing the above settings
- ✅ Restrict who can push to matching branches（单人项目可只允许自己）
- ❌ 不勾选 "Allow force pushes"
- ❌ 不勾选 "Allow deletions"

---

## 阶段 J：全新克隆复验

### J.1 执行步骤

在 GitHub 仓库创建并推送成功后，执行全新克隆复验：

```bash
# 1. 在项目目录外创建临时验收目录
mkdir -p /tmp/project-016-clone-verify
cd /tmp/project-016-clone-verify

# 2. 从 GitHub 克隆（替换 YOUR_USERNAME）
git clone git@github.com:YOUR_USERNAME/zwd-portfolio-production.git
cd zwd-portfolio-production

# 3. 不复制本地任何隐藏文件

# 4. 执行验证脚本
./tools/verify-repository.ps1
python tools/verify-manifest.py
```

### J.2 检查必要文件存在

确认以下文件在全新克隆中存在：

```
rag-api/.env.example
rag-api/.env.demo.example
rag-api/configs/rag_config.public.yaml
wordpress/themes/zwd-portfolio/assets/src/data/navigation-items.js
public-content/ 中 9 份 Markdown
.github/workflows/verify.yml
.gitleaks.toml
manifests/source-sync-manifest.json
manifests/repository-manifest.json
```

### J.3 通过标准

- 全新克隆无需源项目即可完成仓库脱敏验证
- `verify-repository.ps1` 退出码 0（11/11 通过）
- `verify-manifest.py` 退出码 0（10/10 通过）
- 必要文件缺失数为 0
- Manifest 哈希不一致数为 0
- Git 工作区保持干净

### J.4 验收后清理

```bash
cd /tmp
rm -rf project-016-clone-verify
```

---

## 阶段 K 后：GitHub CI 验证

### CI 首次执行

推送后 GitHub Actions 会自动触发。在仓库 `Actions` 页面确认：

1. `repository-boundary` Job 绿色通过
2. `secret-scan` Job 绿色通过（Gitleaks + 自定义扫描）
3. `public-content-gate` Job 绿色通过
4. `manifest-check` Job 绿色通过
5. `sync-policy-test` Job 绿色通过

### 负向测试（可选但建议）

为验证 CI 闸门有效，可临时创建分支测试：

```bash
# 测试 1：放入测试密钥应失败
git checkout -b test/secret-negative
# 在 rag-api/.env.example 末尾追加一个 sk- 开头的 20+ 位字母数字测试密钥
echo "LLM_API_KEY=<在此处放入一个 sk- 开头的测试密钥>" >> rag-api/.env.example
git add -A && git commit -m "test: negative secret"
git push origin test/secret-negative
# 创建 PR，确认 secret-scan Job 失败
# 测试后删除分支

# 测试 2：删除公开字段应失败
git checkout -b test/field-negative
# 编辑 public-content/个人介绍/个人介绍.md，删除 privacy_level 行
git add -A && git commit -m "test: negative field"
git push origin test/field-negative
# 创建 PR，确认 public-content-gate Job 失败
# 测试后删除分支
```

---

## 最终放行检查清单

以下条件**全部满足**后，仓库脱敏阶段才算完成，可进入下一阶段（生产容器部署）：

- [x] 本地验证全部通过（verify-repository.ps1 EXIT=0）
- [x] Git 历史扫描通过
- [x] Manifest 零差异
- [x] 公开内容四字段全部通过
- [ ] GitHub 仓库为 Private（阶段 K）
- [ ] GitHub CI 全绿（阶段 K 后）
- [ ] 全新克隆复验通过（阶段 J）
- [ ] 工作区干净

完成后才允许编写并执行下一阶段：

```
生产容器、RAG 运行、阿里云 ECS 与正式上线整改执行方案
```

---

## 附录：常用命令速查

```bash
# 本地总验收
./tools/verify-repository.ps1

# 仅验证 Manifest
python tools/verify-manifest.py

# 仅验证公开内容
python tools/verify-public-content.py

# 安全扫描（工作区 + 历史）
python tools/scan-secrets.py --history

# 重新同步源项目（需在 project-015 存在时）
./tools/sync-public-source.ps1

# 重新生成 repository-manifest
python tools/gen-repository-manifest.py

# 运行扫描器测试
python -m pytest tests/security/test_scan_secrets.py --noconftest -v
```
