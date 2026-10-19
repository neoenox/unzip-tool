<#
.SYNOPSIS
    公開済みの GitHub Release を、実際の資産を使って確認する。

.DESCRIPTION
    CI では確認できない「公開された資産そのもの」と「実 exe の起動時の挙動」を確認する。
    版数は version.py から読む（この文書やこのファイルに直書きしない）。

    確認する内容:
    - リリース資産のサイズと SHA256 が GitHub 上のダイジェストと一致すること
    - ダウンロードした exe を直接起動し、保存した位置にウィンドウが戻ること
    - 画面外の座標は画面内に置き直されること
    - 終了時にウィンドウ位置が設定へ保存されること
    - 更新確認が公開済みの版数を最新として返すこと

    インストーラーのインストール/アンインストール/ショートカット/登録の検証は
    scripts/test-installer.ps1 が担当する。既にインストール済みの端末では実行できないため、
    その場合だけ自動で飛ばす（CI では毎回実行される）。

    ディスプレイが必要なため CI では動かさない。

.EXAMPLE
    pwsh -File scripts/verify-release.ps1

.EXAMPLE
    pwsh -File scripts/verify-release.ps1 -Archive "$env:USERPROFILE\kk-qa\archives\plain.zip" -KeepWorkDir
#>
param(
    [string]$Version,
    [string]$Tag,
    [string]$WorkDir,
    [string]$Archive,
    [switch]$KeepWorkDir,
    [switch]$SkipInstallerTest
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

if (-not $Version) {
    # 版数の出所は version.py の1行だけ。直書きするとリリース時に取り残される。
    $versionFile = Join-Path $projectRoot 'version.py'
    $match = [regex]::Match((Get-Content -LiteralPath $versionFile -Raw), "VERSION\s*=\s*'([^']+)'")
    if (-not $match.Success) { throw "Could not read VERSION from $versionFile." }
    $Version = $match.Groups[1].Value
}
if (-not $Tag) { $Tag = "v$Version" }
if (-not $WorkDir) { $WorkDir = Join-Path ([IO.Path]::GetTempPath()) ('kantan-verify-' + [guid]::NewGuid().ToString('N')) }
if (-not $Archive) {
    $candidate = Join-Path $env:USERPROFILE 'kk-qa\archives\plain.zip'
    if (Test-Path -LiteralPath $candidate) { $Archive = $candidate }
}

$script:checks = 0
$script:failures = New-Object System.Collections.Generic.List[string]

function Assert-True([bool]$Condition, [string]$Message) {
    $script:checks++
    if ($Condition) {
        Write-Output "PASS $Message"
    } else {
        $script:failures.Add($Message)
        Write-Output "FAIL $Message"
    }
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

# 対象ウィンドウの矩形と、対象プロセスへの WM_CLOSE 送信だけを行う。
# デスクトップ全体の画像取得はしない。
Add-Type -Namespace Kantan -Name Native -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
[DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
[DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr insertAfter, int x, int y, int cx, int cy, uint flags);
[DllImport("user32.dll")] public static extern int GetSystemMetrics(int index);
public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
'@

$WM_CLOSE = 0x0010
# SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE: 位置だけを変える（利用者のドラッグを模す）
$SWP_MOVE_ONLY = 0x0015
# SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN
$screenX = [Kantan.Native]::GetSystemMetrics(76)
$screenY = [Kantan.Native]::GetSystemMetrics(77)
$screenW = [Kantan.Native]::GetSystemMetrics(78)
$screenH = [Kantan.Native]::GetSystemMetrics(79)

function New-SettingsFile([string]$Directory, [string]$Geometry, [string]$LastDest) {
    New-Item -ItemType Directory -Force -Path $Directory | Out-Null
    $payload = [ordered]@{ version = 1; geometry = $Geometry; last_dest = $LastDest } | ConvertTo-Json
    $path = Join-Path $Directory 'settings.json'
    # BOM 付きで書くと json が読めず既定値にフォールバックするため、BOM なしで書く。
    [IO.File]::WriteAllText($path, $payload + "`n", (New-Object Text.UTF8Encoding($false)))
    return $path
}

function Stop-OwnProcess($Process, [string]$ExePath) {
    if ($Process -and -not $Process.HasExited) {
        try { $Process.Kill() } catch { }
    }
    # onefile の exe は親を終了させると子が残ることがある。自分が起動した複製だけを片付ける。
    Get-Process -Name 'KantanKaiko' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $ExePath } |
        ForEach-Object { try { $_.Kill() } catch { } }
}

function Start-AppWindow([string]$ExePath, [string]$SettingsDir, [string]$ArchivePath) {
    $previous = $env:KANTAN_SETTINGS_DIR
    $env:KANTAN_SETTINGS_DIR = $SettingsDir
    try {
        if ($ArchivePath) { $process = Start-Process -FilePath $ExePath -ArgumentList @($ArchivePath) -PassThru }
        else { $process = Start-Process -FilePath $ExePath -PassThru }
    } finally {
        $env:KANTAN_SETTINGS_DIR = $previous
    }
    $deadline = (Get-Date).AddSeconds(45)
    $handle = [IntPtr]::Zero
    $title = ''
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        if ($process.HasExited) { break }
        # onefile の exe は起動元（親）ではなく子プロセスがウィンドウを持つ。
        # 同じ実行ファイルから動いているプロセスのうち、ウィンドウを持つものを探す。
        $window = Get-Process -Name 'KantanKaiko' -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -eq $ExePath -and $_.MainWindowHandle.ToInt64() -ne 0 } |
            Select-Object -First 1
        if ($window) {
            $handle = $window.MainWindowHandle
            $title = $window.MainWindowTitle
            break
        }
    }
    Start-Sleep -Milliseconds 500
    return [pscustomobject]@{ Process = $process; Handle = $handle; Title = $title }
}

function Get-WindowRect([IntPtr]$Handle) {
    $rect = New-Object 'Kantan.Native+RECT'
    if (-not [Kantan.Native]::GetWindowRect($Handle, [ref]$rect)) { throw 'GetWindowRect failed.' }
    return $rect
}

function Close-AppWindow([IntPtr]$Handle, $Process) {
    [void][Kantan.Native]::PostMessage($Handle, $WM_CLOSE, [IntPtr]::Zero, [IntPtr]::Zero)
    $exited = $Process.WaitForExit(20000)
    if (-not $exited) { return -1 }
    return $Process.ExitCode
}

# 1. リリースの資産（サイズとダイジェスト）
Write-Output "Verifying release $Tag (version $Version)."
$release = & gh release view $Tag --json isDraft,isPrerelease,assets | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw "gh release view failed for $Tag." }
Assert-True (-not $release.isDraft) "release $Tag is published (not a draft)"
Assert-True (-not $release.isPrerelease) "release $Tag is a normal release (not a pre-release)"

$expected = @{
    'KantanKaiko.exe'                  = $release.assets | Where-Object { $_.name -eq 'KantanKaiko.exe' }
    "KantanKaiko-Setup-$Version.exe"   = $release.assets | Where-Object { $_.name -eq "KantanKaiko-Setup-$Version.exe" }
}
foreach ($name in $expected.Keys) {
    Assert-True ($null -ne $expected[$name]) "release has the asset $name"
}

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
foreach ($name in $expected.Keys) {
    & gh release download $Tag --dir $WorkDir --pattern $name --clobber | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "gh release download failed for $name." }
}
foreach ($name in $expected.Keys) {
    $asset = $expected[$name]
    if ($null -eq $asset) { continue }
    $path = Join-Path $WorkDir $name
    $digest = ($asset.digest -replace '^sha256:', '')
    Assert-True ((Get-Item -LiteralPath $path).Length -eq $asset.size) "$name size matches the release ($($asset.size) bytes)"
    Assert-True ((Get-Sha256 $path) -eq $digest) "$name SHA256 matches the release digest"
}

$releaseExe = Join-Path $WorkDir 'KantanKaiko.exe'
$releaseInstaller = Join-Path $WorkDir "KantanKaiko-Setup-$Version.exe"

# 2. 実 exe の起動時の挙動（設定の復元・画面外の拒否・終了時の保存）
$settingsRoot = Join-Path $WorkDir 'settings'
$savedX = 300
$savedY = 200
$savedGeometry = "900x700+$savedX+$savedY"
$destDir = Join-Path $WorkDir 'out'
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
$previousSettings = $env:KANTAN_SETTINGS_DIR
try {
    Write-Output 'Checking window placement with a saved position.'
    $settingsDir = Join-Path $settingsRoot 'placed'
    $settingsFile = New-SettingsFile $settingsDir $savedGeometry $destDir
    $app = Start-AppWindow $releaseExe $settingsDir $Archive
    try {
        Assert-True ($app.Handle -ne [IntPtr]::Zero) 'the released exe shows a window'
        if ($app.Handle -ne [IntPtr]::Zero) {
            $rect = Get-WindowRect $app.Handle
            Assert-True ($rect.Left -eq $savedX -and $rect.Top -eq $savedY) "window returns to the saved position ($savedX,$savedY), got $($rect.Left),$($rect.Top)"
            Assert-True (($rect.Right - $rect.Left) -ge 900 -and ($rect.Bottom - $rect.Top) -ge 700) 'window keeps at least the saved size'
            if ($Archive) {
                Assert-True ($app.Title -like 'かんたん解凍*') 'window title starts with the application name'
            }
            # 位置を変えてから閉じ、閉じたときの位置が保存されることを見る。
            $movedX = 500
            $movedY = 400
            [void][Kantan.Native]::SetWindowPos($app.Handle, [IntPtr]::Zero, $movedX, $movedY, 0, 0, $SWP_MOVE_ONLY)
            Start-Sleep -Milliseconds 800
            $movedRect = Get-WindowRect $app.Handle
            Assert-True ($movedRect.Left -eq $movedX -and $movedRect.Top -eq $movedY) "window can be moved for the check, got $($movedRect.Left),$($movedRect.Top)"
            $exitCode = Close-AppWindow $app.Handle $app.Process
            Assert-True ($exitCode -eq 0) "closing the window exits with code 0, got $exitCode"
            $saved = Get-Content -LiteralPath $settingsFile -Raw | ConvertFrom-Json
            Assert-True ($saved.last_dest -eq $destDir) 'the last destination survives the restart'
            $parsed = [regex]::Match($saved.geometry, '^(\d{2,5})x(\d{2,5})\+(-?\d{1,5})\+(-?\d{1,5})$')
            Assert-True ($parsed.Success) "a window position is saved ($($saved.geometry))"
            if ($parsed.Success) {
                Assert-True ([int]$parsed.Groups[3].Value -eq $movedRect.Left -and [int]$parsed.Groups[4].Value -eq $movedRect.Top) "the saved position is the one the window was closed at ($($saved.geometry))"
            }
        }
    } finally {
        Stop-OwnProcess $app.Process $releaseExe
    }

    Write-Output 'Checking that an off-screen position is brought back on screen.'
    $settingsDir = Join-Path $settingsRoot 'offscreen'
    $settingsFile = New-SettingsFile $settingsDir '900x700+9000+9000' ''
    $app = Start-AppWindow $releaseExe $settingsDir ''
    try {
        Assert-True ($app.Handle -ne [IntPtr]::Zero) 'the released exe starts with an off-screen setting'
        if ($app.Handle -ne [IntPtr]::Zero) {
            $rect = Get-WindowRect $app.Handle
            $overlapX = [Math]::Min($rect.Right, $screenX + $screenW) - [Math]::Max($rect.Left, $screenX)
            $overlapY = [Math]::Min($rect.Bottom, $screenY + $screenH) - [Math]::Max($rect.Top, $screenY)
            Assert-True ($overlapX -ge 80 -and $overlapY -ge 40) "off-screen position is placed on screen (overlap ${overlapX}x${overlapY})"
            $exitCode = Close-AppWindow $app.Handle $app.Process
            Assert-True ($exitCode -eq 0) "closing the window exits with code 0, got $exitCode"
            $saved = Get-Content -LiteralPath $settingsFile -Raw | ConvertFrom-Json
            Assert-True ($saved.geometry -notmatch '\+9000\+9000') "the off-screen position is replaced in the settings ($($saved.geometry))"
        }
    } finally {
        Stop-OwnProcess $app.Process $releaseExe
    }
} finally {
    $env:KANTAN_SETTINGS_DIR = $previousSettings
}

# 3. 更新確認（公開 API）
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    Write-Output 'Checking the update feed.'
    Push-Location $projectRoot
    try {
        $raw = & $python.Source -c "import json, updates; print(json.dumps(updates.check_latest(), ensure_ascii=True))" 2>&1
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    Assert-True ($code -eq 0) "the update check reaches the release feed"
    if ($code -eq 0) {
        $latest = $raw | ConvertFrom-Json
        Assert-True ($latest.version -eq $Version) "the published version is offered as the latest ($($latest.version))"
        Assert-True (-not $latest.newer) 'the published version is not reported as newer than itself'
    }
} else {
    Write-Warning 'python was not found; skipping the update check.'
}

# 4. インストーラーの検証（未インストールの端末のみ。CI は毎回実行している）
$installKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{8C259DA6-E5C1-4EF9-8E4D-965A268316A2}_is1'
if ($SkipInstallerTest) {
    Write-Output 'Skipping the installer test (-SkipInstallerTest).'
} elseif (Test-Path -LiteralPath $installKey) {
    Write-Warning 'An installation already exists for this user; scripts/test-installer.ps1 cannot run here (CI covers it).'
} else {
    Write-Output 'Running scripts/test-installer.ps1 against the released installer.'
    & (Join-Path $PSScriptRoot 'test-installer.ps1') -InstallerPath $releaseInstaller -ExecutablePath $releaseExe -Version $Version
    Assert-True ($LASTEXITCODE -eq 0) 'the released installer installs, registers, and uninstalls cleanly'
}

# まとめ
Write-Output ''
Write-Output ("Checked {0} item(s); {1} failed." -f $script:checks, $script:failures.Count)
if ($script:failures.Count -gt 0) {
    $script:failures | ForEach-Object { Write-Output "FAILED: $_" }
}
if (-not $KeepWorkDir) {
    Remove-Item -LiteralPath $WorkDir -Recurse -Force -ErrorAction SilentlyContinue
} else {
    Write-Output "Kept working directory: $WorkDir"
}
if ($script:failures.Count -gt 0) { exit 1 }
Write-Output "PASS verify-release $Tag"
