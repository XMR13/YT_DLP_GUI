Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  $here = $PSScriptRoot
  if (-not $here) {
    $here = (Get-Location).Path
  }
  return (Resolve-Path (Join-Path $here "..")).Path
}

function Read-ProjectVersion([string]$repoRoot) {
  $pyproject = Join-Path $repoRoot "pyproject.toml"
  $content = Get-Content -LiteralPath $pyproject -Raw
  $m = [regex]::Match($content, '^\s*version\s*=\s*\"([^\"]+)\"', "Multiline")
  if (-not $m.Success) { return "0.0.0" }
  return $m.Groups[1].Value
}

function Get-UvCommand() {
  $uv = Get-Command uv -ErrorAction SilentlyContinue
  if ($uv) {
    return $uv.Source
  }
  return $null
}

function Ensure-Venv([string]$repoRoot) {
  $venvDir = Join-Path $repoRoot ".venv"
  $venvPython = Join-Path $venvDir "Scripts\python.exe"
  if (Test-Path -LiteralPath $venvPython) {
    return $venvPython
  }
  $uv = Get-UvCommand
  if ($uv) {
    Invoke-Checked -file $uv -arguments @("venv", $venvDir)
  }
  $py = (Get-Command py -ErrorAction SilentlyContinue)
  $python = (Get-Command python -ErrorAction SilentlyContinue)
  if (-not (Test-Path -LiteralPath $venvDir)) {
    if ($py) {
      & py -3 -m venv $venvDir
    } elseif ($python) {
      & python -m venv $venvDir
    } else {
      throw "Python not found. Install Python 3.10+."
    }
  }
  if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Missing venv python at $venvPython"
  }
  return $venvPython
}

function Read-BinariesLock([string]$repoRoot) {
  $path = Join-Path $repoRoot "packaging\binaries.lock.json"
  return (Get-Content -LiteralPath $path -Raw | ConvertFrom-Json)
}

function Invoke-Checked([string]$file, [string[]]$arguments) {
  & $file @arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed ($LASTEXITCODE): $file $($arguments -join ' ')"
  }
}

function Ensure-Pip([string]$pythonExe) {
  & $pythonExe -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('pip') else 1)" *> $null
  if ($LASTEXITCODE -ne 0) {
    Invoke-Checked -file $pythonExe -arguments @("-m", "ensurepip", "--upgrade")
    & $pythonExe -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('pip') else 1)" *> $null
    if ($LASTEXITCODE -ne 0) {
      throw "pip is unavailable in $pythonExe after ensurepip."
    }
  }
}

function Install-BuildDeps([string]$venvPython) {
  $uv = Get-UvCommand
  if ($uv) {
    Invoke-Checked -file $uv -arguments @("sync", "--extra", "dev", "--extra", "packaging")
    return
  }
  Ensure-Pip $venvPython
  Invoke-Checked -file $venvPython -arguments @("-m", "pip", "install", "-U", "pip")
  Invoke-Checked -file $venvPython -arguments @("-m", "pip", "install", "-e", ".[dev,packaging]")
}

function Download-Verified([string]$url, [string]$expectedSha256, [string]$outFile) {
  Invoke-WebRequest -Uri $url -OutFile $outFile
  $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $outFile).Hash.ToLowerInvariant()
  if ($actual -ne $expectedSha256.ToLowerInvariant()) {
    throw "SHA256 mismatch for $url`nExpected: $expectedSha256`nActual:   $actual"
  }
}

function Remove-IfExists([string]$path) {
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Recurse -Force
  }
}

$repoRoot = Get-RepoRoot
Push-Location $repoRoot
try {
  $version = Read-ProjectVersion $repoRoot
  $lock = Read-BinariesLock $repoRoot

  $venvPython = Ensure-Venv $repoRoot
  Install-BuildDeps $venvPython

  Remove-IfExists (Join-Path $repoRoot "build")
  Remove-IfExists (Join-Path $repoRoot "dist")

  Invoke-Checked -file $venvPython -arguments @(
    "-m",
    "PyInstaller",
    (Join-Path $repoRoot "packaging\yt_dlp_gui.spec"),
    "--noconfirm",
    "--clean"
  )

  $builtDir = Join-Path $repoRoot "dist\yt-dlp-gui"
  if (-not (Test-Path -LiteralPath $builtDir)) {
    throw "PyInstaller output not found at $builtDir"
  }

  $tmpDir = Join-Path $repoRoot "build\downloads"
  New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

  $ytdlpTmp = Join-Path $tmpDir $lock.yt_dlp.filename
  Download-Verified $lock.yt_dlp.url $lock.yt_dlp.sha256 $ytdlpTmp

  $releaseLiteRoot = Join-Path $repoRoot "dist\release-lite"
  $releaseFullRoot = Join-Path $repoRoot "dist\release-full"
  Remove-IfExists $releaseLiteRoot
  Remove-IfExists $releaseFullRoot
  New-Item -ItemType Directory -Path $releaseLiteRoot -Force | Out-Null
  New-Item -ItemType Directory -Path $releaseFullRoot -Force | Out-Null

  $liteApp = Join-Path $releaseLiteRoot "yt-dlp-gui"
  $fullApp = Join-Path $releaseFullRoot "yt-dlp-gui"
  Copy-Item -LiteralPath $builtDir -Destination $liteApp -Recurse
  Copy-Item -LiteralPath $builtDir -Destination $fullApp -Recurse

  Copy-Item -LiteralPath $ytdlpTmp -Destination (Join-Path $liteApp "yt-dlp.exe") -Force
  Copy-Item -LiteralPath $ytdlpTmp -Destination (Join-Path $fullApp "yt-dlp.exe") -Force

  $ffmpegTmp = Join-Path $tmpDir $lock.ffmpeg.archive_filename
  Download-Verified $lock.ffmpeg.url $lock.ffmpeg.sha256 $ffmpegTmp

  $ffmpegExtract = Join-Path $tmpDir "ffmpeg-extract"
  Remove-IfExists $ffmpegExtract
  Expand-Archive -LiteralPath $ffmpegTmp -DestinationPath $ffmpegExtract

  $ffmpegSrc = Join-Path $ffmpegExtract $lock.ffmpeg.ffmpeg_relpath
  $ffprobeSrc = Join-Path $ffmpegExtract $lock.ffmpeg.ffprobe_relpath
  if (-not (Test-Path -LiteralPath $ffmpegSrc)) { throw "Missing ffmpeg at $ffmpegSrc" }
  if (-not (Test-Path -LiteralPath $ffprobeSrc)) { throw "Missing ffprobe at $ffprobeSrc" }
  Copy-Item -LiteralPath $ffmpegSrc -Destination (Join-Path $fullApp "ffmpeg.exe") -Force
  Copy-Item -LiteralPath $ffprobeSrc -Destination (Join-Path $fullApp "ffprobe.exe") -Force

  $liteZip = Join-Path $repoRoot ("dist\yt-dlp-gui-" + $version + "-win-x64-lite.zip")
  $fullZip = Join-Path $repoRoot ("dist\yt-dlp-gui-" + $version + "-win-x64-full.zip")
  Remove-IfExists $liteZip
  Remove-IfExists $fullZip
  Compress-Archive -LiteralPath $liteApp -DestinationPath $liteZip
  Compress-Archive -LiteralPath $fullApp -DestinationPath $fullZip

  Write-Host "Built:"
  Write-Host "  $liteZip"
  Write-Host "  $fullZip"
} finally {
  Pop-Location
}
