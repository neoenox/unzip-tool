param(
    [string]$Version = '1.1.0',
    [string]$ExecutablePath,
    [string]$CompilerPath
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if ($Version -notmatch '^(\d+)\.(\d+)\.(\d+)(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$') {
    throw 'Version must be a semantic version such as 1.1.0 or 1.1.0-beta.1.'
}
$numericVersion = "$($Matches[1]).$($Matches[2]).$($Matches[3])"
if (-not $ExecutablePath) {
    $ExecutablePath = Join-Path $projectRoot 'dist\KantanKaiko.exe'
}
$executable = Get-Item -LiteralPath $ExecutablePath -ErrorAction Stop
if ($executable.PSIsContainer -or $executable.Length -eq 0) {
    throw 'Build KantanKaiko.exe before creating its installer.'
}
if (-not $CompilerPath) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) {
        $CompilerPath = $command.Source
    } else {
        $candidates = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
        )
        $CompilerPath = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    }
}
if (-not $CompilerPath -or -not (Test-Path -LiteralPath $CompilerPath -PathType Leaf)) {
    throw 'Inno Setup 6 is required. Set -CompilerPath to its ISCC.exe.'
}
$outputDirectory = Join-Path $projectRoot 'dist'
$script = Join-Path $projectRoot 'installer\KantanKaiko.iss'
& $CompilerPath "/DAppVersion=$Version" "/DNumericVersion=$numericVersion" "/DSourceExe=$($executable.FullName)" "/DOutputDirectory=$outputDirectory" $script
if ($LASTEXITCODE -ne 0) { throw "Installer compiler failed: $LASTEXITCODE" }
$installer = Get-Item -LiteralPath (Join-Path $outputDirectory "KantanKaiko-Setup-$Version.exe") -ErrorAction Stop
if ($installer.Length -eq 0) { throw 'Installer is empty.' }
Write-Output "Installer: $($installer.FullName)"
