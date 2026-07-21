<#
.SYNOPSIS
    白名单同步脚本 — 从 project-015 单向同步已批准的公开内容到 project-016。

.DESCRIPTION
    职责（严格按脱敏方案 V2 阶段 D）：
      1. 从批准的源路径复制业务源码和公开内容。
      2. 排除缓存、运行数据和不允许的文件类型（路径段级判断）。
      3. 删除目标中已从源项目撤回的同步文件（基于上一版 source-sync-manifest）。
      4. 验证公开 Markdown 四字段（缺失/空值/错误值均失败）。
      5. 生成 source-sync-manifest.json（幂等，无每次变化的时间戳）。
      6. 在写入 Git 前执行目标目录安全扫描（不排除 md/yaml/json/ps1）。

    同步脚本不负责覆盖：生产 Docker 配置、GitHub Actions、生产 RAG 配置、README/文档/运维脚本。

.NOTES
    版本: 2.0
    对应方案: GitHub仓库脱敏整改执行方案-V2.md 阶段 D
#>

param(
    [string]$SourceRoot = "E:\AI\codex_workspace\project-015-personal-knowledge-assistant",
    [string]$TargetRoot = "E:\AI\codex_workspace\project-016-zwd-portfolio-production",
    [switch]$SkipSecurityScan
)

$ErrorActionPreference = "Stop"
$ExitCode = 0

# ============================================================
# 白名单映射 — 源相对路径 → 目标相对路径
# 注意：已移除 configs/（生产配置由 project-016 独立维护）
# ============================================================
$PathMappings = [ordered]@{
    "src/wordpress/themes/zwd-portfolio"            = "wordpress/themes/zwd-portfolio"
    "src/wordpress/plugins/zwd-portfolio-core"      = "wordpress/plugins/zwd-portfolio-core"
    "src/rag_app"                                   = "rag-api/rag_app"
    "requirements.txt"                              = "rag-api/requirements.txt"
    "ai-job-knowledge-base/12-网站公开候选"          = "public-content"
    "tests"                                         = "tests"
}

# ============================================================
# 排除文件名（精确匹配）
# ============================================================
$ExcludeFileNames = @(
    ".gitkeep",
    ".DS_Store",
    "Thumbs.db"
)

# ============================================================
# 排除/拒绝目录段（路径中任一段命中即排除并报错）
# 路径段级判断，避免误伤同名子目录
# ============================================================
$DenyPathSegments = @(
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".venv",
    "venv",
    ".wp-env-runtime",
    "logs",
    "backups",
    "private",
    "internal",
    "ai-job-knowledge-base"
)
# 注意：data 不在段级拒绝列表中，避免误伤 wordpress/themes/.../assets/src/data/
# 根级 /data/ 运行数据由 .gitignore 和 verify-repository 根目录检查覆盖

# 拒绝文件扩展名（数据库/备份/压缩包）
$DenyExtensions = @(
    ".pyc", ".pyo", ".sqlite", ".db", ".dump", ".bak",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".pem", ".key", ".pfx", ".crt", ".keystore"
)

# 拒绝文件名（精确）
$DenyFileNames = @(
    ".env", "id_rsa", "id_ed25519", "credentials.json"
)

# ============================================================
# 公开 Markdown 四字段强制门槛
# ============================================================
$PublicRequiredFields = @{
    "privacy_level"       = "public"
    "publish_status"      = "published"
    "review_status"       = "approved"
    "verification_status" = "verified"
}

Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   公开内容白名单同步 v2 — project-015 → project-016    ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "源项目: $SourceRoot"
Write-Host "目标项目: $TargetRoot"
Write-Host ""

# ============================================================
# 函数：计算 SHA-256
# ============================================================
function Get-FileSha256 {
    param([string]$FilePath)
    if (-not (Test-Path $FilePath)) { return $null }

    # 文本文件统一将 CRLF 规范化为 LF，避免跨平台检出后哈希失效；
    # PNG 等二进制资产必须按原始字节计算，不能改写其中偶然出现的 0D0A。
    $bytes = [System.IO.File]::ReadAllBytes($FilePath)
    $binaryExtensions = @('.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.woff', '.woff2')
    if ($binaryExtensions -contains [System.IO.Path]::GetExtension($FilePath).ToLowerInvariant()) {
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $hashBytes = $sha256.ComputeHash($bytes)
            return ([System.BitConverter]::ToString($hashBytes) -replace '-', '').ToLower()
        } finally {
            $sha256.Dispose()
        }
    }

    $normalized = New-Object System.Collections.Generic.List[byte]
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        if (
            $bytes[$index] -eq 13 -and
            ($index + 1) -lt $bytes.Length -and
            $bytes[$index + 1] -eq 10
        ) {
            $normalized.Add(10)
            $index++
        } else {
            $normalized.Add($bytes[$index])
        }
    }

    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hashBytes = $sha256.ComputeHash($normalized.ToArray())
        return ([System.BitConverter]::ToString($hashBytes) -replace '-', '').ToLower()
    } finally {
        $sha256.Dispose()
    }
}

# ============================================================
# 函数：路径段级拒绝检查
# 返回 $true 表示路径命中拒绝段（应排除/报错）
# ============================================================
function Test-PathDenied {
    param([string]$RelativePath)

    $normalized = ($RelativePath -replace '\\', '/').TrimStart('/')
    $segments = $normalized -split '/'

    foreach ($seg in $segments) {
        if ($null -eq $seg -or $seg -eq "") { continue }
        if ($DenyPathSegments -contains $seg) {
            return $true
        }
    }
    return $false
}

# ============================================================
# 函数：判断文件是否应被排除（不复制）
# ============================================================
function Test-FileExcluded {
    param(
        [string]$RelativePath,
        [string]$FileName
    )

    # 拒绝路径段
    if (Test-PathDenied -RelativePath $RelativePath) { return $true }

    # 拒绝文件名
    if ($DenyFileNames -contains $FileName) { return $true }

    # 排除文件名
    if ($ExcludeFileNames -contains $FileName) { return $true }

    # 拒绝扩展名
    $ext = [System.IO.Path]::GetExtension($FileName).ToLower()
    if ($DenyExtensions -contains $ext) { return $true }

    # .env 系列（除 .env.example/.env.demo.example 由生产单独维护，不同步）
    if ($FileName -like "*.env*") { return $true }

    return $false
}

# ============================================================
# 函数：解析 YAML Front Matter 四字段
# 严格校验：缺失/空值/错误值均返回 $false
# ============================================================
function Test-PublicMarkdownFourFields {
    param([string]$FilePath)

    $fileName = Split-Path $FilePath -Leaf
    # PS 5.1 默认按 ANSI 读取无 BOM 的 UTF-8 文件，中文会乱码破坏正则，必须显式 UTF-8
    $content = Get-Content -Path $FilePath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if (-not $content) {
        Write-Host "  [FAIL] $fileName — 文件为空或无法读取" -ForegroundColor Red
        return $false
    }

    # 提取 Front Matter
    if ($content -notmatch '(?s)^---\s*\r?\n(.*?)\r?\n---\s*(\r?\n|$)') {
        Write-Host "  [FAIL] $fileName — 缺少 YAML Front Matter（--- ... ---）" -ForegroundColor Red
        return $false
    }
    $frontMatter = $matches[1]

    $allOk = $true
    foreach ($kv in $PublicRequiredFields.GetEnumerator()) {
        $field = $kv.Key
        $expected = $kv.Value

        # 精确匹配字段值（支持引号和无引号两种写法）
        $pattern = "(?m)^\s*$field\s*:\s*[""']?$expected[""']?\s*$"
        if ($frontMatter -match $pattern) {
            # 正确值
            continue
        }

        # 字段存在但值错误，或值为空
        $existsPattern = "(?m)^\s*$field\s*:\s*(.*)$"
        if ($frontMatter -match $existsPattern) {
            $val = $matches[1].Trim().Trim('"').Trim("'")
            if ($val -eq "") {
                Write-Host "  [FAIL] $fileName — $field 值为空（应为 $expected）" -ForegroundColor Red
            } else {
                Write-Host "  [FAIL] $fileName — $field 值为 '$val'（应为 $expected）" -ForegroundColor Red
            }
        } else {
            Write-Host "  [FAIL] $fileName — 缺少字段 $field（应为 $expected）" -ForegroundColor Red
        }
        $allOk = $false
    }

    return $allOk
}

# ============================================================
# 函数：安全扫描（不排除任何文本文件类型）
# ============================================================
function Invoke-SecurityScan {
    param([string]$ScanRoot)

    Write-Host ""
    Write-Host "--- 目标目录安全扫描 ---" -ForegroundColor Cyan

    $found = $false

    # 第一层：密钥形态（不排除 md/yaml/json/ps1/sh）
    $keyPatterns = @(
        @{ Name = "OpenAI/API Key";      Pattern = 'sk-[a-zA-Z0-9]{20,}' },
        @{ Name = "AWS Access Key";       Pattern = 'AKIA[0-9A-Z]{16}' },
        @{ Name = "GitHub PAT";           Pattern = 'ghp_[a-zA-Z0-9]{36}' },
        @{ Name = "GitHub OAuth";         Pattern = 'gho_[a-zA-Z0-9]{36}' },
        @{ Name = "Slack Token";          Pattern = 'xox[baprs]-[a-zA-Z0-9-]+' },
        @{ Name = "Google API Key";       Pattern = 'AIza[0-9A-Za-z\-_]{35}' },
        @{ Name = "JWT";                  Pattern = 'eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+' },
        @{ Name = "Aliyun AccessKey";     Pattern = 'LTAI[0-9A-Za-z]{12,18}' },
        @{ Name = "PEM Private Key";      Pattern = '-----BEGIN (RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----' }
    )
    # 注意：不在此处扫描"通用 password=xxx 赋值"，因为 env 模板和 compose 文件
    # 合法包含 change-me-* / replace-with-* 占位符，会产生大量误报。
    # 密码类检测交给阶段 F 的 .gitleaks.toml 配置（带精确 allowlist）。

    # 扫描所有文本文件（不排除类型）
    $textFiles = Get-ChildItem -Path $ScanRoot -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $rel = ($_.FullName.Substring($ScanRoot.Length) -replace '\\', '/').TrimStart('/')
            # 跳过 .git
            -not ($rel -like '*/.git/*' -or $rel -like '.git/*')
        }

    foreach ($kp in $keyPatterns) {
        foreach ($f in $textFiles) {
            $matches = Select-String -Path $f.FullName -Pattern $kp.Pattern -ErrorAction SilentlyContinue
            foreach ($m in $matches) {
                # 不打印密钥原文，只输出规则/路径/行号
                Write-Host "  [FAIL] 密钥扫描: $($kp.Name) | $($m.RelativePath($ScanRoot)):$($m.LineNumber)" -ForegroundColor Red
                $found = $true
            }
        }
    }

    # 第二层：中国身份证号
    $idPattern = '[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    foreach ($f in $textFiles) {
        $matches = Select-String -Path $f.FullName -Pattern $idPattern -ErrorAction SilentlyContinue
        foreach ($m in $matches) {
            Write-Host "  [FAIL] 身份证号: $($m.RelativePath($ScanRoot)):$($m.LineNumber)" -ForegroundColor Red
            $found = $true
        }
    }

    # 第三层：拒绝目录/文件名扫描（在目标中）
    foreach ($f in $textFiles) {
        $rel = ($f.FullName.Substring($ScanRoot.Length) -replace '\\', '/').TrimStart('/')
        if (Test-PathDenied -RelativePath $rel) {
            Write-Host "  [FAIL] 拒绝路径: $rel" -ForegroundColor Red
            $found = $true
        }
        if ($DenyFileNames -contains $f.Name) {
            Write-Host "  [FAIL] 拒绝文件名: $rel" -ForegroundColor Red
            $found = $true
        }
        $ext = $f.Extension.ToLower()
        if ($DenyExtensions -contains $ext) {
            Write-Host "  [FAIL] 拒绝扩展名: $rel" -ForegroundColor Red
            $found = $true
        }
    }

    if (-not $found) {
        Write-Host "  [PASS] 安全扫描通过 — 未发现密钥、拒绝目录或敏感信息" -ForegroundColor Green
    }
    return $found
}

# ============================================================
# 读取上一版 source-sync-manifest（用于残留删除）
# ============================================================
$previousManifestPath = Join-Path $TargetRoot "manifests\source-sync-manifest.json"
$previousTargetPaths = @{}
if (Test-Path $previousManifestPath) {
    try {
        $prev = Get-Content $previousManifestPath -Raw | ConvertFrom-Json
        foreach ($entry in $prev.files) {
            $previousTargetPaths[$entry.target_path] = $true
        }
        Write-Host "读取上一版 Manifest: $($previousTargetPaths.Count) 个文件" -ForegroundColor Gray
    } catch {
        Write-Host "  [WARN] 上一版 Manifest 解析失败，残留删除将跳过: $_" -ForegroundColor Yellow
    }
}

# ============================================================
# 主同步逻辑
# ============================================================
Write-Host ""
Write-Host "--- 开始白名单同步 ---" -ForegroundColor Cyan

$allRecords = @()
$newTargetPaths = @{}
$syncErrors = @()

foreach ($mapping in $PathMappings.GetEnumerator()) {
    $sourceRel = $mapping.Key
    $targetRel = $mapping.Value
    $sourcePath = Join-Path $SourceRoot $sourceRel
    $targetPath = Join-Path $TargetRoot $targetRel

    Write-Host ""
    Write-Host "  同步: $sourceRel → $targetRel" -ForegroundColor White

    if (-not (Test-Path $sourcePath)) {
        Write-Host "    [!] 源路径不存在，跳过: $sourcePath" -ForegroundColor Yellow
        continue
    }

    if (Test-Path $sourcePath -PathType Container) {
        # 目录同步
        if (-not (Test-Path $targetPath)) {
            New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
        }

        $sourceFiles = Get-ChildItem -Path $sourcePath -Recurse -File -ErrorAction SilentlyContinue
        foreach ($srcFile in $sourceFiles) {
            $relativeInSource = $srcFile.FullName.Substring($sourcePath.Length).TrimStart([char[]]'/\')
            $normalizedRel = ($relativeInSource -replace '\\', '/').TrimStart('/')

            # 路径段级拒绝检查
            if (Test-FileExcluded -RelativePath $normalizedRel -FileName $srcFile.Name) {
                Write-Host "    [skip] $normalizedRel （排除/拒绝）" -ForegroundColor Gray
                continue
            }

            $targetFile = Join-Path $targetPath $relativeInSource
            $targetDir = Split-Path $targetFile -Parent
            if (-not (Test-Path $targetDir)) {
                New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            }

            $sourceHash = Get-FileSha256 $srcFile.FullName
            $targetHash = Get-FileSha256 $targetFile

            if ($sourceHash -and $targetHash -and ($sourceHash -eq $targetHash)) {
                Write-Host "    =  $normalizedRel (unchanged)" -ForegroundColor Gray
            } else {
                Copy-Item -Path $srcFile.FullName -Destination $targetFile -Force
                $targetHash = Get-FileSha256 $targetFile
                Write-Host "    +  $normalizedRel" -ForegroundColor Green
            }

            # 计算仓库相对路径（正斜杠）
            $repoRel = ($targetFile.Substring($TargetRoot.Length).TrimStart([char[]]'/\') -replace '\\', '/')
            $newTargetPaths[$repoRel] = $true

            $allRecords += [ordered]@{
                source_path = ($sourceRel -replace '\\', '/') + '/' + $normalizedRel
                target_path = $repoRel
                sha256      = $targetHash
            }
        }
    } else {
        # 单文件同步
        if (Test-FileExcluded -RelativePath $sourceRel -FileName (Split-Path $sourcePath -Leaf)) {
            Write-Host "    [skip] $sourceRel （排除/拒绝）" -ForegroundColor Gray
            continue
        }

        $targetDir = Split-Path $targetPath -Parent
        if (-not (Test-Path $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        }

        $sourceHash = Get-FileSha256 $sourcePath
        $targetHash = Get-FileSha256 $targetPath

        if ($sourceHash -and $targetHash -and ($sourceHash -eq $targetHash)) {
            Write-Host "    =  $targetRel (unchanged)" -ForegroundColor Gray
        } else {
            Copy-Item -Path $sourcePath -Destination $targetPath -Force
            $targetHash = Get-FileSha256 $targetPath
            Write-Host "    +  $targetRel" -ForegroundColor Green
        }

        $repoRel = ($targetPath.Substring($TargetRoot.Length).TrimStart([char[]]'/\') -replace '\\', '/')
        $newTargetPaths[$repoRel] = $true

        $allRecords += [ordered]@{
            source_path = ($sourceRel -replace '\\', '/')
            target_path = $repoRel
            sha256      = $targetHash
        }
    }
}

# ============================================================
# 公开 Markdown 四字段校验
# ============================================================
Write-Host ""
Write-Host "--- 公开内容四字段校验 ---" -ForegroundColor Cyan
$publicContentDir = Join-Path $TargetRoot "public-content"
if (Test-Path $publicContentDir) {
    $mdFiles = Get-ChildItem -Path $publicContentDir -Recurse -Filter "*.md" -ErrorAction SilentlyContinue
    $mdCount = 0
    $mdPass = 0
    foreach ($mdFile in $mdFiles) {
        $mdCount++
        $result = Test-PublicMarkdownFourFields -FilePath $mdFile.FullName
        if ($result) {
            $mdPass++
            Write-Host "  [PASS] $($mdFile.Name)" -ForegroundColor Green
        } else {
            $syncErrors += "public-content/$($mdFile.Name): 四字段校验失败"
        }
    }
    Write-Host ""
    Write-Host "  公开 Markdown: $mdPass/$mdCount 通过" -ForegroundColor $(if ($mdPass -eq $mdCount) { 'Green' } else { 'Red' })
    if ($mdPass -ne $mdCount) {
        $ExitCode = 1
    }
} else {
    Write-Host "  [WARN] public-content 目录不存在" -ForegroundColor Yellow
}

# ============================================================
# 删除上一版存在但本次不存在的同步文件（残留删除）
# 仅删除曾在 source-sync-manifest 中的文件，保护生产自有文件
# ============================================================
Write-Host ""
Write-Host "--- 残留同步文件清理 ---" -ForegroundColor Cyan
$removedCount = 0
foreach ($prevPath in $previousTargetPaths.Keys) {
    if (-not $newTargetPaths.ContainsKey($prevPath)) {
        $fullPath = Join-Path $TargetRoot $prevPath
        if (Test-Path $fullPath) {
            Remove-Item -Path $fullPath -Force
            Write-Host "  -  $prevPath (源已撤回)" -ForegroundColor Yellow
            $removedCount++
        }
    }
}
if ($removedCount -eq 0) {
    Write-Host "  无残留文件需要清理" -ForegroundColor Gray
}

# 清理空目录（只清理同步目标子树，不动 deploy/docs/.github）
$syncTargetRoots = @("wordpress", "rag-api/rag_app", "public-content", "tests")
foreach ($syncRoot in $syncTargetRoots) {
    $fullSyncRoot = Join-Path $TargetRoot $syncRoot
    if (Test-Path $fullSyncRoot) {
        $emptyDirs = Get-ChildItem -Path $fullSyncRoot -Recurse -Directory -ErrorAction SilentlyContinue |
            Where-Object { @(Get-ChildItem -Path $_.FullName -Force -ErrorAction SilentlyContinue).Count -eq 0 }
        foreach ($d in $emptyDirs) {
            Remove-Item -Path $d.FullName -Force -ErrorAction SilentlyContinue
        }
    }
}

# ============================================================
# 生成 source-sync-manifest.json（幂等：无每次变化的时间戳）
# ============================================================
# 按 target_path 排序，保证输出稳定
$sortedRecords = $allRecords | Sort-Object { $_.target_path }

$manifest = [ordered]@{
    version         = "2.0"
    source_project  = "project-015-personal-knowledge-assistant"
    target_project  = "project-016-zwd-portfolio-production"
    total_files     = $sortedRecords.Count
    files           = $sortedRecords
}

$manifestJson = $manifest | ConvertTo-Json -Depth 5
$manifestPath = Join-Path $TargetRoot "manifests\source-sync-manifest.json"
$manifestDir = Split-Path $manifestPath -Parent
if (-not (Test-Path $manifestDir)) {
    New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null
}
# 使用 .NET 写入无 BOM 的 UTF-8（PS 5.1 的 Set-Content -Encoding UTF8 会加 BOM，
# 导致 Linux 上 json.load 失败和 Git diff 噪音）
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($manifestPath, $manifestJson, $utf8NoBom)

Write-Host ""
Write-Host "--- Manifest 已生成 ---" -ForegroundColor Cyan
Write-Host "  文件数: $($sortedRecords.Count)"
Write-Host "  位置: manifests/source-sync-manifest.json"
Write-Host ""

# ============================================================
# 安全扫描
# ============================================================
if (-not $SkipSecurityScan) {
    $scanFailed = Invoke-SecurityScan -ScanRoot $TargetRoot
    if ($scanFailed) {
        $ExitCode = 1
    }
}

# ============================================================
# 结果汇总
# ============================================================
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
if ($ExitCode -eq 0) {
    Write-Host "║  同步完成 — 状态: 通过                                 ║" -ForegroundColor Green
} else {
    Write-Host "║  同步完成 — 状态: 存在失败项                           ║" -ForegroundColor Red
}
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

exit $ExitCode
