<#
.SYNOPSIS
    白名单同步脚本 — 从 project-015 单向同步已批准的公开内容到 project-016。
.DESCRIPTION
    只同步经过明确列举的路径，对每个文件记录 SHA-256 和时间戳。
    检查拒绝目录、密钥泄露和个人敏感信息。
    源文件被删除时同步删除目标文件。
    连续执行两次应无 Git 差异（幂等）。
.NOTES
    版本: 1.0
    创建日期: 2026-07-18
#>

param(
    [string]$SourceRoot = "E:\AI\codex_workspace\project-015-personal-knowledge-assistant",
    [string]$TargetRoot = "E:\AI\codex_workspace\project-016-zwd-portfolio-production",
    [switch]$SkipSecurityScan = $false
)

$ErrorActionPreference = "Stop"
$ExitCode = 0
$SyncTime = Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz"

# ============================================================
# 白名单 — 允许同步的路径（相对于源项目根目录）
# ============================================================
$WhitelistPaths = @(
    "src\wordpress\themes\zwd-portfolio",
    "src\wordpress\plugins\zwd-portfolio-core",
    "src\rag_app",
    "requirements.txt",
    "configs\rag_config.yaml",
    "configs\.env.example",
    "configs\.env.demo.example",
    "ai-job-knowledge-base\12-网站公开候选",
    "tests"
)

# ============================================================
# 拒绝目录 — 绝对不得出现在目标项目中的路径（相对目标项目根目录）
# ============================================================
$DenyPatterns = @(
    ".env",
    "*.env.local",
    "ai-job-knowledge-base\0*",
    "ai-job-knowledge-base\9*",
    "ai-job-knowledge-base\01-个人基础档案",
    "ai-job-knowledge-base\02-教育与工作经历",
    "ai-job-knowledge-base\03-项目与作品集",
    "ai-job-knowledge-base\04-技能与能力证据",
    "ai-job-knowledge-base\05-目标岗位与JD",
    "ai-job-knowledge-base\06-公司与行业情报",
    "ai-job-knowledge-base\07-面试题库",
    "ai-job-knowledge-base\08-求职材料",
    "ai-job-knowledge-base\09-求职进度",
    "ai-job-knowledge-base\10-面试与求职复盘",
    "ai-job-knowledge-base\11-AI学习与行业知识",
    "data\rag",
    "logs",
    "backups",
    ".wp-env-runtime",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__"
)

# ============================================================
# 目标映射 — 源路径到目标路径的转换
# ============================================================
$PathMappings = @{
    "src\wordpress\themes\zwd-portfolio"      = "wordpress\themes\zwd-portfolio"
    "src\wordpress\plugins\zwd-portfolio-core" = "wordpress\plugins\zwd-portfolio-core"
    "src\rag_app"                              = "rag-api\rag_app"
    "requirements.txt"                         = "rag-api\requirements.txt"
    "configs\rag_config.yaml"                  = "rag-api\rag_config.yaml"
    "configs\.env.example"                     = "rag-api\.env.example"
    "configs\.env.demo.example"                = "rag-api\.env.demo.example"
    "ai-job-knowledge-base\12-网站公开候选"      = "public-content"
    "tests"                                    = "tests"
}

Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   公开内容白名单同步 — project-015 → project-016       ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "源项目: $SourceRoot"
Write-Host "目标项目: $TargetRoot"
Write-Host "同步时间: $SyncTime"
Write-Host ""

# ============================================================
# 函数定义
# ============================================================

function Get-FileHash-SHA256 {
    param([string]$FilePath)
    if (Test-Path $FilePath) {
        $hash = (Get-FileHash -Path $FilePath -Algorithm SHA256).Hash
        return $hash.ToLower()
    }
    return $null
}

function Sync-Directory {
    param(
        [string]$SourceDir,
        [string]$TargetDir
    )

    if (-not (Test-Path $SourceDir)) {
        Write-Host "  [!] 源目录不存在: $SourceDir" -ForegroundColor Yellow
        return @()
    }

    if (-not (Test-Path $TargetDir)) {
        New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    }

    $records = @()
    $syncedFiles = @()

    # 复制所有源文件
    $sourceFiles = Get-ChildItem -Path $SourceDir -Recurse -File
    foreach ($srcFile in $sourceFiles) {
        $relativePath = $srcFile.FullName.Substring($SourceDir.Length).TrimStart('\')
        $targetFile = Join-Path $TargetDir $relativePath

        $targetDir = Split-Path $targetFile -Parent
        if (-not (Test-Path $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        }

        $sourceHash = Get-FileHash-SHA256 $srcFile.FullName
        $targetHash = Get-FileHash-SHA256 $targetFile

        $needsUpdate = $true
        if ($sourceHash -and $targetHash -and ($sourceHash -eq $targetHash)) {
            $needsUpdate = $false
            Write-Host "  =  $relativePath (unchanged)" -ForegroundColor Gray
        }

        if ($needsUpdate) {
            Copy-Item -Path $srcFile.FullName -Destination $targetFile -Force
            $targetHash = Get-FileHash-SHA256 $targetFile
            Write-Host "  +  $relativePath" -ForegroundColor Green
        }

        $normalizedPath = ($targetFile.Substring($TargetRoot.Length).TrimStart('\') -replace '\\', '/')
        $syncedFiles += $normalizedPath

        $records += @{
            source_path = $srcFile.FullName
            target_path = $normalizedPath
            sha256 = $targetHash
            synced_at = $SyncTime
        }
    }

    # 删除目标中存在但源中已删除的文件
    $targetFiles = Get-ChildItem -Path $TargetDir -Recurse -File -ErrorAction SilentlyContinue
    if ($targetFiles) {
        foreach ($tgtFile in $targetFiles) {
            $relativePath = $tgtFile.FullName.Substring($TargetDir.Length).TrimStart('\')
            $srcFile = Join-Path $SourceDir $relativePath
            if (-not (Test-Path $srcFile)) {
                Remove-Item -Path $tgtFile.FullName -Force
                Write-Host "  -  $relativePath (removed from source)" -ForegroundColor Yellow
            }
        }
    }

    return $records
}

function Sync-File {
    param(
        [string]$SourceFile,
        [string]$TargetFile
    )

    if (-not (Test-Path $SourceFile)) {
        Write-Host "  [!] 源文件不存在: $SourceFile" -ForegroundColor Yellow
        return $null
    }

    $targetDir = Split-Path $TargetFile -Parent
    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    $sourceHash = Get-FileHash-SHA256 $SourceFile
    $targetHash = Get-FileHash-SHA256 $TargetFile

    $needsUpdate = $true
    if ($sourceHash -and $targetHash -and ($sourceHash -eq $targetHash)) {
        $needsUpdate = $false
        $relativePath = $TargetFile.Substring($TargetRoot.Length).TrimStart('\')
        Write-Host "  =  $relativePath (unchanged)" -ForegroundColor Gray
    }

    if ($needsUpdate) {
        Copy-Item -Path $SourceFile -Destination $TargetFile -Force
        $targetHash = Get-FileHash-SHA256 $TargetFile
        $relativePath = $TargetFile.Substring($TargetRoot.Length).TrimStart('\')
        Write-Host "  +  $relativePath" -ForegroundColor Green
    }

    $normalizedPath = ($TargetFile.Substring($TargetRoot.Length).TrimStart('\') -replace '\\', '/')

    return @{
        source_path = $SourceFile
        target_path = $normalizedPath
        sha256 = $targetHash
        synced_at = $SyncTime
    }
}

# ============================================================
# 安全扫描函数
# ============================================================

function Invoke-SecurityScan {
    param([string]$ScanRoot)

    Write-Host ""
    Write-Host "--- 安全扫描 ---" -ForegroundColor Cyan

    $found = $false

    # 1. 密钥扫描 — 常见密钥模式
    $keyPatterns = @(
        'sk-[a-zA-Z0-9]{20,}',           # OpenAI/API keys
        'AKIA[0-9A-Z]{16}',               # AWS Access Key
        'ghp_[a-zA-Z0-9]{36}',            # GitHub Personal Access Token
        'gho_[a-zA-Z0-9]{36}',
        'ghu_[a-zA-Z0-9]{36}',
        'ghs_[a-zA-Z0-9]{36}',
        'ghr_[a-zA-Z0-9]{36}',
        'xox[baprs]-[a-zA-Z0-9-]+',       # Slack tokens
        'AIza[0-9A-Za-z\-_]{35}',         # Google API
        'ya29\.[0-9A-Za-z\-_]+',          # Google OAuth
        'eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'  # JWT tokens
    )

    foreach ($pattern in $keyPatterns) {
        $matches = Get-ChildItem -Path $ScanRoot -Recurse -File -Exclude "*.ps1","*.json","*.md","*.yaml","*.yml" |
            Select-String -Pattern $pattern -ErrorAction SilentlyContinue
        if ($matches) {
            Write-Host "  [FAIL] 检测到疑似密钥: $($matches[0].Path):$($matches[0].LineNumber)" -ForegroundColor Red
            $found = $true
        }
    }

    # 2. 拒绝目录扫描
    foreach ($pattern in $DenyPatterns) {
        $denyPath = Join-Path $ScanRoot $pattern
        if (Test-Path $denyPath) {
            Write-Host "  [FAIL] 拒绝目录/文件存在: $denyPath" -ForegroundColor Red
            $found = $true
        }
    }

    # 3. 个人信息扫描 — 中国身份证号
    $idPattern = '[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    $matches = Get-ChildItem -Path $ScanRoot -Recurse -File |
        Select-String -Pattern $idPattern -ErrorAction SilentlyContinue
    if ($matches) {
        Write-Host "  [FAIL] 检测到疑似身份证号: $($matches[0].Path):$($matches[0].LineNumber)" -ForegroundColor Red
        $found = $true
    }

    if (-not $found) {
        Write-Host "  [PASS] 安全扫描通过 — 未发现密钥、拒绝目录或敏感信息" -ForegroundColor Green
    }

    return $found
}

# ============================================================
# Markdown 元数据校验
# ============================================================

function Test-PublicMarkdown {
    param([string]$FilePath)

    $content = Get-Content -Path $FilePath -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return $true }

    # 检查 Front Matter 中的隐私级别
    if ($content -match 'privacy_level:\s*(private|internal)') {
        Write-Host "  [WARN] $FilePath — 隐私级别非 public: $($matches[1])" -ForegroundColor Yellow
        return $false
    }

    # 检查发布状态
    if ($content -match 'publish_status:\s*(draft|review)') {
        Write-Host "  [WARN] $FilePath — 发布状态非 published: $($matches[1])" -ForegroundColor Yellow
        return $false
    }

    return $true
}

# ============================================================
# 主同步逻辑
# ============================================================

Write-Host "--- 开始白名单同步 ---" -ForegroundColor Cyan

$allRecords = @()

foreach ($whitelistPath in $WhitelistPaths) {
    $sourcePath = Join-Path $SourceRoot $whitelistPath

    if (-not (Test-Path $sourcePath)) {
        Write-Host "  [!] 跳过不存在的路径: $sourcePath" -ForegroundColor Yellow
        continue
    }

    $mappedPath = $null
    foreach ($key in $PathMappings.Keys) {
        if ($whitelistPath -eq $key) {
            $mappedPath = $PathMappings[$key]
            break
        }
    }

    if (-not $mappedPath) {
        Write-Host "  [!] 无目标映射: $whitelistPath" -ForegroundColor Yellow
        continue
    }

    $targetPath = Join-Path $TargetRoot $mappedPath
    Write-Host ""
    Write-Host "  同步: $whitelistPath → $mappedPath" -ForegroundColor White

    if (Test-Path $sourcePath -PathType Container) {
        # 目录同步
        $records = Sync-Directory -SourceDir $sourcePath -TargetDir $targetPath
        $allRecords += $records

        # 对公开 Markdown 内容进行元数据校验
        if ($whitelistPath -like "*12-网站公开候选*") {
            Write-Host "  --- 公开内容隐私校验 ---" -ForegroundColor Cyan
            $mdFiles = Get-ChildItem -Path $targetPath -Recurse -Filter "*.md" -ErrorAction SilentlyContinue
            foreach ($mdFile in $mdFiles) {
                $result = Test-PublicMarkdown -FilePath $mdFile.FullName
                if (-not $result) {
                    $global:ExitCode = 1
                }
            }
        }
    } else {
        # 单文件同步
        $record = Sync-File -SourceFile $sourcePath -TargetFile $targetPath
        if ($record) {
            $allRecords += $record
        }
    }
}

# ============================================================
# 生成 Manifest
# ============================================================
$manifestPath = Join-Path $TargetRoot "manifests\public-source-manifest.json"
$manifest = @{
    version = "1.0"
    generated_at = $SyncTime
    source_project = "project-015-personal-knowledge-assistant"
    target_project = "project-016-zwd-portfolio-production"
    total_files = $allRecords.Count
    files = $allRecords
}

$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path $manifestPath -Encoding UTF8
Write-Host ""
Write-Host "--- Manifest 已生成 ---" -ForegroundColor Cyan
Write-Host "  文件数: $($allRecords.Count)"
Write-Host "  位置: manifests/public-source-manifest.json"
Write-Host ""

# ============================================================
# 安全扫描
# ============================================================
if (-not $SkipSecurityScan) {
    $scanFailed = Invoke-SecurityScan -ScanRoot $TargetRoot
    if ($scanFailed) {
        $global:ExitCode = 1
    }
}

# ============================================================
# 清理目标中的空目录
# ============================================================
Write-Host ""
Write-Host "--- 清理空目录 ---" -ForegroundColor Cyan
$emptyDirs = Get-ChildItem -Path $TargetRoot -Recurse -Directory |
    Where-Object {
        $dir = $_.FullName
        # 跳过 .git 目录
        if ($dir -like "*\.git*") { return $false }
        # 跳过部署配置目录（保留骨架）
        $relativeToTarget = $dir.Substring($TargetRoot.Length).TrimStart('\')
        if ($relativeToTarget -eq "deploy" -or
            $relativeToTarget -eq "deploy\nginx" -or
            $relativeToTarget -eq "deploy\scripts" -or
            $relativeToTarget -eq ".github" -or
            $relativeToTarget -eq ".github\workflows") {
            return $false
        }
        @(Get-ChildItem -Path $dir -Force).Count -eq 0
    } |
    Sort-Object { $_.FullName.Length } -Descending

foreach ($dir in $emptyDirs) {
    Remove-Item -Path $dir.FullName -Force -ErrorAction SilentlyContinue
    Write-Host "  已清理空目录: $($dir.FullName)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
if ($ExitCode -eq 0) {
    Write-Host "║  同步完成 — 状态: 通过                               ║" -ForegroundColor Green
} else {
    Write-Host "║  同步完成 — 状态: 有警告或失败项                     ║" -ForegroundColor Red
}
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

exit $ExitCode
