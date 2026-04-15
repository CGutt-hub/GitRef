# Install GitRef from GitHub releases (Windows)
# Usage: irm https://raw.githubusercontent.com/CGutt-hub/gitref/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$repo = "CGutt-hub/gitref"
$installDir = "$env:LOCALAPPDATA\GitRef"

Write-Host "Installing GitRef..." -ForegroundColor Cyan

# Get latest release
try {
    $release = Invoke-RestMethod "https://api.github.com/repos/$repo/releases/latest"
    $asset = $release.assets | Where-Object { $_.name -eq "gitref.exe" } | Select-Object -First 1
} catch {
    $asset = $null
}

if ($asset) {
    # Download binary
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    $dest = Join-Path $installDir "gitref.exe"
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $dest
    Write-Host "Downloaded to $dest" -ForegroundColor Green

    # Add to PATH if not already present
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$installDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$installDir;$userPath", "User")
        $env:Path = "$installDir;$env:Path"
        Write-Host "Added $installDir to PATH" -ForegroundColor Green
    }

    Write-Host "GitRef installed. Run: gitref" -ForegroundColor Cyan
} else {
    Write-Host "No binary release found. Installing via pip..." -ForegroundColor Yellow
    pip install "git+https://github.com/$repo.git"
    Write-Host "Installed via pip. Run: gitref" -ForegroundColor Cyan
}
