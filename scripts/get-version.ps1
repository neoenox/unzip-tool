param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

# version.py is the only source of the release number; parse it in one place.
$versionFile = Join-Path $ProjectRoot 'version.py'
$match = [regex]::Match((Get-Content -LiteralPath $versionFile -Raw), "VERSION\s*=\s*'([^']+)'")
if (-not $match.Success) { throw "Could not read VERSION from $versionFile." }
$match.Groups[1].Value
