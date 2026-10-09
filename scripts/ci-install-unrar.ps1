# GitHub-hosted runners use Chocolatey to provision UnRAR for RAR3/5
# distribution tests. The community feed can intermittently return HTTP 503.
# Check the actual executable rather than trusting Chocolatey's exit code alone.
$ErrorActionPreference = 'Stop'
$maxAttempts = 3

function Find-Unrar {
    $detected = python -c "from unzipper import find_unrar_tool; print(find_unrar_tool() or '')"
    if ($LASTEXITCODE -ne 0) { return '' }
    return [string]$detected
}

$found = Find-Unrar
if ($found) {
    Write-Host "UnRAR already available: $found"
    exit 0
}

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    Write-Host "Installing UnRAR (attempt $attempt/$maxAttempts)..."
    choco install unrar -y --no-progress
    $chocoExit = $LASTEXITCODE
    $found = Find-Unrar
    if ($found) {
        Write-Host "UnRAR available: $found"
        exit 0
    }
    if ($attempt -eq $maxAttempts) {
        throw "UnRAR unavailable after $maxAttempts Chocolatey attempts (last exit code: $chocoExit). RAR distribution tests cannot run."
    }
    $delay = 10 * $attempt
    Write-Warning "Chocolatey did not provision UnRAR (exit $chocoExit); retrying in $delay seconds."
    Start-Sleep -Seconds $delay
}
