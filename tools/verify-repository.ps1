<#
.SYNOPSIS
    本地脱敏总验收脚本 — 只读执行 12 项检查。

.DESCRIPTION
    对应方案 V2 阶段 H。退出码：
      0 = 全部通过
      1 = 存在阻塞项
      2 = 验证环境错误
    输出 reports/repository-verification.json（机器可读，不含密钥原文）。

.NOTES
    版本: 1.0
    对应方案: GitHub仓库脱敏整改执行方案-V2.md 阶段 H
#>

param(
    [string]$TargetRoot = "E:\AI\codex_workspace\project-016-zwd-portfolio-production"
)

$ErrorActionPreference = "Stop"
$PythonExe = "python"
# 工具绝对路径（避免 CWD 不在 project-016 时相对路径解析错误）
$ToolScanSecrets = Join-Path $TargetRoot "tools\scan-secrets.py"
$ToolVerifyPublic = Join-Path $TargetRoot "tools\verify-public-content.py"
$ToolVerifyManifest = Join-Path $TargetRoot "tools\verify-manifest.py"

# 切换到目标目录，确保 git 命令和相对路径都在 project-016 下执行
Push-Location $TargetRoot
# PS 5.1 默认按 ANSI 解码原生命令输出，中文路径会乱码，设为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
try {

# ============================================================
# 结果收集
# ============================================================
$results = [ordered]@{
    script        = "verify-repository.ps1"
    version       = "1.0"
    timestamp     = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
    target_root   = $TargetRoot
    checks        = @()
    summary       = [ordered]@{ total = 0; passed = 0; failed = 0; warnings = 0 }
    exit_code     = 0
}

function Add-Check {
    param(
        [string]$Id,
        [string]$Name,
        [string]$Status,   # pass / fail / warn / error
        [string]$Detail,
        [object]$Items = $null
    )
    $entry = [ordered]@{
        id     = $Id
        name   = $Name
        status = $Status
        detail = $Detail
    }
    if ($Items) { $entry.items = $Items }
    $script:results.checks += $entry
    $script:results.summary.total++
    switch ($Status) {
        "pass"  { $script:results.summary.passed++ }
        "fail"  { $script:results.summary.failed++ }
        "warn"  { $script:results.summary.warnings++ }
        "error" { $script:results.summary.failed++ }
    }
}

# ============================================================
# 检查 1: 确认运行目录是 project-016
# ============================================================
$marker = Join-Path $TargetRoot ".gitleaks.toml"
if (-not (Test-Path $marker)) {
    Add-Check "VR-01" "运行目录确认" "error" "未找到 .gitleaks.toml 标记文件，可能不在 project-016"
    $results.exit_code = 2
} else {
    Add-Check "VR-01" "运行目录确认" "pass" "目标目录为 project-016"
}

# ============================================================
# 检查 2: 工作区是否干净
# ============================================================
$status = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    Add-Check "VR-02" "工作区状态" "error" "git status 失败"
    $results.exit_code = 2
} elseif ($status) {
    Add-Check "VR-02" "工作区状态" "fail" "工作区不干净: $($status -join '; ')"
} else {
    Add-Check "VR-02" "工作区状态" "pass" "工作区干净"
}

# ============================================================
# 检查 3: 当前分支
# ============================================================
$branch = git rev-parse --abbrev-ref HEAD
if ($branch -eq "main") {
    Add-Check "VR-03" "当前分支" "pass" "分支: main"
} else {
    Add-Check "VR-03" "当前分支" "fail" "当前分支为 $branch，应为 main"
}

# ============================================================
# 检查 4: 必要文件是否被 Git 跟踪
# ============================================================
$requiredFiles = @(
    "rag-api/.env.example",
    "rag-api/.env.demo.example",
    "rag-api/configs/rag_config.public.yaml",
    "wordpress/themes/zwd-portfolio/assets/src/data/navigation-items.js",
    ".github/workflows/verify.yml",
    ".gitleaks.toml",
    "manifests/source-sync-manifest.json",
    "manifests/repository-manifest.json",
    "tools/sync-public-source.ps1",
    "tools/verify-manifest.py",
    "tools/scan-secrets.py",
    "tools/verify-public-content.py"
)
# 一次性获取跟踪文件集合，避免 --error-unmatch 触发终止错误
$allTrackedSet = @{}
foreach ($tf in (git -c core.quotepath=false ls-files)) {
    $allTrackedSet[$tf.Trim()] = $true
}
$missingTracked = @()
foreach ($f in $requiredFiles) {
    if (-not $allTrackedSet.ContainsKey($f)) {
        $missingTracked += $f
    }
}
if ($missingTracked.Count -eq 0) {
    Add-Check "VR-04" "必要文件跟踪" "pass" "$($requiredFiles.Count) 个必要文件全部被 Git 跟踪"
} else {
    Add-Check "VR-04" "必要文件跟踪" "fail" "$($missingTracked.Count) 个必要文件未被跟踪" $missingTracked
}

# ============================================================
# 检查 5: 拒绝目录和敏感文件名
# ============================================================
$denyRootDirs = @("private", "internal", "ai-job-knowledge-base", "data/rag", "logs", "backups", ".wp-env-runtime", "node_modules", "__pycache__")
$denyFound = @()
foreach ($d in $denyRootDirs) {
    $fullPath = Join-Path $TargetRoot $d
    if (Test-Path $fullPath) {
        $denyFound += $d
    }
}
# 敏感文件名扫描（条件必须用 -and 连接，否则会匹配所有文件）
$sensitiveFiles = Get-ChildItem -Path $TargetRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $rel = $_.FullName.Substring($TargetRoot.Length).TrimStart('\') -replace '\\', '/'
        (-not ($rel -like '.git/*' -or $rel -like 'reports/*' -or $rel -like '.pytest_cache/*')) -and
        ($_.Name -match '^(id_rsa|id_ed25519|credentials|secret)' -or
         $_.Extension -in '.pem', '.key', '.pfx', '.sqlite', '.db', '.dump', '.bak')
    }
$sensitiveFound = $sensitiveFiles | ForEach-Object { $_.FullName.Substring($TargetRoot.Length).TrimStart('\') -replace '\\', '/' }

if ($denyFound.Count -eq 0 -and $sensitiveFound.Count -eq 0) {
    Add-Check "VR-05" "拒绝目录和敏感文件" "pass" "未发现拒绝目录或敏感文件"
} else {
    Add-Check "VR-05" "拒绝目录和敏感文件" "fail" "发现 $($denyFound.Count) 个拒绝目录, $($sensitiveFound.Count) 个敏感文件" (@{deny_dirs=$denyFound; sensitive_files=$sensitiveFound})
}

# ============================================================
# 检查 6: 工作区密钥扫描
# ============================================================
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$scanOutput = & $PythonExe $ToolScanSecrets --json 2>&1 | Out-String
$scanExit = $LASTEXITCODE
$ErrorActionPreference = $prevEAP
if ($scanExit -eq 0) {
    Add-Check "VR-06" "工作区密钥扫描" "pass" "未发现有效密钥"
} else {
    Add-Check "VR-06" "工作区密钥扫描" "fail" "发现密钥或敏感信息（退出码 $scanExit）"
}

# ============================================================
# 检查 7: Git 历史密钥扫描
# ============================================================
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$histOutput = & $PythonExe $ToolScanSecrets --history --json 2>&1 | Out-String
$histExit = $LASTEXITCODE
$ErrorActionPreference = $prevEAP
if ($histExit -eq 0) {
    Add-Check "VR-07" "Git 历史密钥扫描" "pass" "全历史无有效密钥"
} else {
    Add-Check "VR-07" "Git 历史密钥扫描" "fail" "历史中发现密钥或敏感信息（退出码 $histExit）"
}

# ============================================================
# 检查 8: 公开 Markdown 四字段校验
# ============================================================
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pubOutput = & $PythonExe $ToolVerifyPublic 2>&1 | Out-String
$pubExit = $LASTEXITCODE
$ErrorActionPreference = $prevEAP
if ($pubExit -eq 0) {
    Add-Check "VR-08" "公开内容四字段" "pass" "所有公开 Markdown 四字段通过"
} else {
    Add-Check "VR-08" "公开内容四字段" "fail" "存在四字段校验失败（退出码 $pubExit）"
}

# ============================================================
# 检查 9: Manifest 验证
# ============================================================
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$manOutput = & $PythonExe $ToolVerifyManifest 2>&1 | Out-String
$manExit = $LASTEXITCODE
$ErrorActionPreference = $prevEAP
if ($manExit -eq 0) {
    Add-Check "VR-09" "Manifest 验证" "pass" "source-sync + repository manifest 全部通过"
} else {
    Add-Check "VR-09" "Manifest 验证" "fail" "Manifest 验证失败（退出码 $manExit）"
}

# ============================================================
# 检查 10: 所有 Git 跟踪文件能在磁盘找到
# ============================================================
$trackedFiles = git -c core.quotepath=false ls-files
$missingOnDisk = @()
foreach ($f in $trackedFiles) {
    $fullPath = Join-Path $TargetRoot ($f -replace '/', '\')
    if (-not (Test-Path $fullPath)) {
        $missingOnDisk += $f
    }
}
if ($missingOnDisk.Count -eq 0) {
    Add-Check "VR-10" "跟踪文件完整性" "pass" "$($trackedFiles.Count) 个跟踪文件全部存在于磁盘"
} else {
    Add-Check "VR-10" "跟踪文件完整性" "fail" "$($missingOnDisk.Count) 个跟踪文件磁盘不存在" $missingOnDisk
}

# ============================================================
# 检查 11: 没有必要文件处于 ignored 状态
# ============================================================
# 用 try/catch 避免 git check-ignore 非零退出码触发终止错误
$ignoredNecessary = @()
foreach ($f in $requiredFiles) {
    try {
        $ignored = git check-ignore $f 2>&1
        if ($LASTEXITCODE -eq 0) {
            $ignoredNecessary += $f
        }
    } catch {
        # git check-ignore 返回非零表示文件未被忽略，属正常
    }
}
if ($ignoredNecessary.Count -eq 0) {
    Add-Check "VR-11" "必要文件未忽略" "pass" "无必要文件被 .gitignore 忽略"
} else {
    Add-Check "VR-11" "必要文件未忽略" "fail" "$($ignoredNecessary.Count) 个必要文件被忽略" $ignoredNecessary
}

# ============================================================
# 检查 12: 输出 JSON 报告
# ============================================================
$reportDir = Join-Path $TargetRoot "reports"
if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}
$reportPath = Join-Path $reportDir "repository-verification.json"

# 先把 VR-12 纳入结果，再序列化，确保 JSON 与控制台都统计 12 项。
Add-Check "VR-12" "验证报告输出" "pass" "报告已写入 reports/repository-verification.json"

# 确定退出码
if ($results.summary.failed -gt 0) {
    $results.exit_code = 1
} elseif ($results.exit_code -ne 2) {
    $results.exit_code = 0
}

# 写入 JSON（无 BOM UTF-8）
$reportJson = $results | ConvertTo-Json -Depth 6
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($reportPath, $reportJson, $utf8NoBom)

# ============================================================
# 汇总输出
# ============================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "仓库脱敏总验收 — 结果汇总" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
foreach ($c in $results.checks) {
    $icon = switch ($c.status) {
        "pass"  { "[PASS] " }
        "fail"  { "[FAIL] " }
        "warn"  { "[WARN] " }
        "error" { "[ERR]  " }
    }
    $color = switch ($c.status) {
        "pass"  { "Green" }
        "fail"  { "Red" }
        "warn"  { "Yellow" }
        "error" { "Red" }
    }
    Write-Host "$icon$($c.id) $($c.name) — $($c.detail)" -ForegroundColor $color
}
Write-Host ""
Write-Host "总计: $($results.summary.total) 项, 通过 $($results.summary.passed), 失败 $($results.summary.failed)" -ForegroundColor $(if ($results.summary.failed -gt 0) { 'Red' } else { 'Green' })
Write-Host "报告: $reportPath" -ForegroundColor Gray
Write-Host "退出码: $($results.exit_code)" -ForegroundColor $(if ($results.exit_code -eq 0) { 'Green' } else { 'Red' })

$finalExit = $results.exit_code
} finally {
    Pop-Location
}

exit $finalExit
