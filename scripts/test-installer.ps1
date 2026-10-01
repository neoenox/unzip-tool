param(
    [Parameter(Mandatory = $true)][string]$InstallerPath,
    [string]$ExecutablePath,
    [string]$Version = '1.0.0'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$installer = (Get-Item -LiteralPath $InstallerPath -ErrorAction Stop).FullName
if (-not $ExecutablePath) { $ExecutablePath = Join-Path $projectRoot 'dist\KantanKaiko.exe' }
$expectedHash = (Get-FileHash -LiteralPath $ExecutablePath -Algorithm SHA256).Hash
$registryKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{8C259DA6-E5C1-4EF9-8E4D-965A268316A2}_is1'
if (Test-Path -LiteralPath $registryKey) {
    throw 'An installation already exists for this user; smoke testing will not modify it.'
}
$testName = 'KantanKaiko-Test-' + [guid]::NewGuid().ToString('N')
$target = Join-Path ([IO.Path]::GetTempPath()) $testName
$groupDirectory = Join-Path ([Environment]::GetFolderPath('Programs')) $testName
$shortcut = Join-Path $groupDirectory 'かんたん解凍.lnk'
$installedExe = Join-Path $target 'KantanKaiko.exe'
$uninstaller = Join-Path $target 'unins000.exe'
$userFile = Join-Path $target 'keep-user-file.txt'
$arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=`"$target`"", "/GROUP=`"$testName`"")
function Run-Setup([string]$FilePath, [string[]]$SetupArguments) {
    $process = Start-Process -FilePath $FilePath -ArgumentList $SetupArguments -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(60000)) {
        Stop-Process -Id $process.Id -Force
        throw 'Installer timed out.'
    }
    if ($process.ExitCode -ne 0) { throw "Installer exited with code $($process.ExitCode)." }
}
try {
    Run-Setup $installer $arguments
    if ((Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash -ne $expectedHash) {
        throw 'Installed executable differs from the build artifact.'
    }
    $registration = Get-ItemProperty -LiteralPath $registryKey
    if ($registration.DisplayVersion -ne $Version) { throw 'Incorrect registered version.' }
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($shortcut)
    if (-not (Test-Path -LiteralPath $shortcut) -or $link.TargetPath -ne $installedExe) {
        throw 'Start menu shortcut is missing or points to the wrong executable.'
    }
    [IO.File]::WriteAllText($userFile, 'preserve me')
    Run-Setup $installer $arguments
    if ([IO.File]::ReadAllText($userFile) -ne 'preserve me') { throw 'Reinstall changed user data.' }
    Run-Setup $uninstaller @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
    if ((Test-Path -LiteralPath $installedExe) -or (Test-Path -LiteralPath $shortcut) -or (Test-Path -LiteralPath $registryKey)) {
        throw 'Uninstall left application files, its shortcut, or registration.'
    }
    if ([IO.File]::ReadAllText($userFile) -ne 'preserve me') { throw 'Uninstall deleted user data.' }
    Write-Output 'PASS install, shortcut, version, reinstall, uninstall, and preservation of user files'
} finally {
    if (Test-Path -LiteralPath $uninstaller) {
        Run-Setup $uninstaller @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
    }
    # Only remove our named fixture; never recursively delete an install directory.
    if (Test-Path -LiteralPath $userFile) { Remove-Item -LiteralPath $userFile }
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target }
}
