# ─────────────────────────────────────────────────────────────────────────────
# MST Buddy — Render.com Deployment Script
# Usage: .\scripts\render-deploy.ps1
#
# What this does:
#   1. Reads your secrets from .env
#   2. Opens Render Blueprint deploy in browser (creates services)
#   3. After you confirm services are created, sets all env vars via Render API
#   4. Triggers a redeploy
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"
$RENDER_API = "https://api.render.com/v1"
$RENDER_EXE = "$env:USERPROFILE\AppData\Local\Programs\render.exe"

# Windows: Render CLI requires $HOME
$env:HOME = $env:USERPROFILE

function Invoke-RenderApi {
    param([string]$Method, [string]$Path, [object]$Body = $null)
    $headers = @{
        "Authorization" = "Bearer $script:RenderApiKey"
        "Content-Type"  = "application/json"
        "Accept"        = "application/json"
    }
    $uri = "$RENDER_API$Path"
    if ($Body) {
        $json = $Body | ConvertTo-Json -Depth 10 -Compress
        return Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers -Body $json
    }
    return Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers
}

function Read-Env {
    $envFile = Join-Path $PSScriptRoot "..\\.env"
    $vars = @{}
    Get-Content $envFile | Where-Object { $_ -match "^[A-Z_]+=." } | ForEach-Object {
        $parts = $_ -split "=", 2
        if ($parts.Count -eq 2) { $vars[$parts[0].Trim()] = $parts[1].Trim() }
    }
    return $vars
}

# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   MST Buddy  →  Render.com Deployment        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Step 0: Read secrets from .env ───────────────────────────────────────────
$env = Read-Env
Write-Host "Secrets loaded from .env:" -ForegroundColor Gray
foreach ($key in @("OPENROUTER_API_KEY","JINA_API_KEY","QDRANT_URL","QDRANT_API_KEY","CHATBOT_API_KEY")) {
    $val = $env[$key]
    if ($val) { Write-Host "  ✓ $key" -ForegroundColor Green }
    else       { Write-Host "  ✗ $key  (missing — set in .env first)" -ForegroundColor Yellow }
}

# ── Step 1: Get Render API key ────────────────────────────────────────────────
Write-Host ""
$script:RenderApiKey = $env["RENDER_API_KEY"]
if (-not $script:RenderApiKey) { $script:RenderApiKey = $env:RENDERCLI_APIKEY }
if (-not $script:RenderApiKey) {
    Write-Host "RENDER_API_KEY is not set in .env" -ForegroundColor Yellow
    Write-Host "  Get one at: https://dashboard.render.com/u/settings  → API Keys → Create" -ForegroundColor White
    Write-Host ""
    $script:RenderApiKey = Read-Host "Paste your Render API key"
    if (-not $script:RenderApiKey) { Write-Error "Render API key is required."; exit 1 }
}
$env:RENDERCLI_APIKEY = $script:RenderApiKey

# Verify key
Write-Host "Verifying Render API key..." -ForegroundColor Cyan
try {
    $owners = Invoke-RenderApi -Method GET -Path "/owners?limit=1"
    $owner = $owners[0].owner
    Write-Host "  Logged in: $($owner.name) <$($owner.email)>" -ForegroundColor Green
    $ownerId = $owner.id
} catch {
    Write-Error "Authentication failed. Double-check your Render API key.`n$_"
    exit 1
}

# ── Step 2: Check for existing services ──────────────────────────────────────
Write-Host ""
Write-Host "Looking for existing services..." -ForegroundColor Cyan
$services = Invoke-RenderApi -Method GET -Path "/services?limit=50&ownerId=$ownerId"
$backendSvc  = $services | Where-Object { $_.service.name -eq "mst-buddy-api" } | Select-Object -First 1
$frontendSvc = $services | Where-Object { $_.service.name -eq "mst-buddy-ui"  } | Select-Object -First 1

if (-not $backendSvc) {
    # ── Step 3: Launch blueprint to create services ───────────────────────────
    Write-Host ""
    Write-Host "No services found. Opening Render Blueprint deploy..." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "In the browser:" -ForegroundColor Yellow
    Write-Host "  1. Connect your GitHub repo"
    Write-Host "  2. Click 'Apply' (creates mst-buddy-api + mst-buddy-ui)"
    Write-Host "  3. Wait for the FIRST build to finish (even if it fails — that's OK)"
    Write-Host "  4. Come back here and press Enter"
    Write-Host ""

    $env:RENDERCLI_APIKEY = $script:RenderApiKey
    & $RENDER_EXE blueprint launch 2>&1 | Select-Object -First 5

    Read-Host "Press Enter once both services appear in the Render dashboard"

    $services    = Invoke-RenderApi -Method GET -Path "/services?limit=50&ownerId=$ownerId"
    $backendSvc  = $services | Where-Object { $_.service.name -eq "mst-buddy-api" } | Select-Object -First 1
    $frontendSvc = $services | Where-Object { $_.service.name -eq "mst-buddy-ui"  } | Select-Object -First 1

    if (-not $backendSvc) {
        Write-Error "Backend 'mst-buddy-api' still not found. Check the Render dashboard and try again."
        exit 1
    }
}

$backendId  = $backendSvc.service.id
$frontendId = $frontendSvc?.service.id
Write-Host "  Backend  ID: $backendId" -ForegroundColor Green
if ($frontendId) { Write-Host "  Frontend ID: $frontendId" -ForegroundColor Green }

# ── Step 4: Build env var list for backend ────────────────────────────────────
Write-Host ""
Write-Host "Setting backend environment variables..." -ForegroundColor Cyan

$backendEnv = @(
    @{ key = "LLM_PROVIDER";            value = "openrouter" }
    @{ key = "LLM_MODEL";               value = "deepseek/deepseek-chat-v3-0324:free" }
    @{ key = "ROUTER_MODEL";            value = "deepseek/deepseek-chat-v3-0324:free" }
    @{ key = "EMBEDDING_PROVIDER";      value = "jina" }
    @{ key = "EMBED_MODEL";             value = "jina-embeddings-v2-base-en" }
    @{ key = "QDRANT_COLLECTION";       value = "mst_docs" }
    @{ key = "TOP_K";                   value = "6" }
    @{ key = "REDIS_URL";               value = "" }
    @{ key = "CRAWL_ON_STARTUP";        value = "true" }
    @{ key = "CRAWL_MAX_PAGES";         value = "60" }
    @{ key = "CRAWL_DEPTH";             value = "3" }
    @{ key = "MST_WEBSITE_URLS";        value = "https://mstblockchain.com,https://docs.mstblockchain.com" }
    @{ key = "ALLOWED_CRAWL_DOMAINS";   value = "mstblockchain.com,docs.mstblockchain.com" }
    @{ key = "WEB_SEARCH_MAX_RESULTS";  value = "4" }
    @{ key = "WEB_SEARCH_FETCH_CONTENT"; value = "true" }
    @{ key = "RERANK_ENABLED";          value = "false" }
    @{ key = "MAX_HISTORY_TURNS";       value = "10" }
)

# Inject secrets from .env
foreach ($key in @("OPENROUTER_API_KEY","JINA_API_KEY","QDRANT_URL","QDRANT_API_KEY","CHATBOT_API_KEY")) {
    $val = $env[$key]
    if ($val) {
        $backendEnv += @{ key = $key; value = $val }
    }
}

# Set CORS to allow frontend
$frontendUrl = if ($frontendId) { "https://mst-buddy-ui.onrender.com" } else { "http://localhost:3001" }
$backendEnv += @{ key = "CORS_ORIGINS"; value = $frontendUrl }

Invoke-RenderApi -Method PUT -Path "/services/$backendId/env-vars" -Body @{ envVars = $backendEnv } | Out-Null
Write-Host "  Backend env vars set ($($backendEnv.Count) vars)." -ForegroundColor Green

# ── Step 5: Set frontend env vars ────────────────────────────────────────────
if ($frontendId) {
    Write-Host "Setting frontend environment variables..." -ForegroundColor Cyan

    # Get backend service URL
    $bSvc = Invoke-RenderApi -Method GET -Path "/services/$backendId"
    $backendUrl = $bSvc.service.serviceDetails.url ?? "mst-buddy-api.onrender.com"
    $backendFullUrl = if ($backendUrl -like "https://*") { $backendUrl } else { "https://$backendUrl" }

    $frontendEnv = @(
        @{ key = "VITE_API_URL"; value = $backendFullUrl }
        @{ key = "VITE_API_KEY"; value = ($env["CHATBOT_API_KEY"] ?? "") }
    )
    Invoke-RenderApi -Method PUT -Path "/services/$frontendId/env-vars" -Body @{ envVars = $frontendEnv } | Out-Null
    Write-Host "  Frontend env vars set." -ForegroundColor Green
    Write-Host "    VITE_API_URL = $backendFullUrl" -ForegroundColor Gray
}

# ── Step 6: Trigger redeploy ──────────────────────────────────────────────────
Write-Host ""
Write-Host "Triggering redeploy..." -ForegroundColor Cyan
try {
    Invoke-RenderApi -Method POST -Path "/services/$backendId/deploys" -Body @{ clearCache = "do_not_clear" } | Out-Null
    Write-Host "  Backend redeploy triggered." -ForegroundColor Green
} catch {
    Write-Host "  Could not trigger redeploy — use 'Manual Deploy' in the dashboard." -ForegroundColor Yellow
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   Deployment configured successfully!        ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend:  https://mst-buddy-api.onrender.com"
Write-Host "  Frontend: https://mst-buddy-ui.onrender.com"
Write-Host "  Logs:     render services tail  (after auth)"
Write-Host ""
Write-Host "  Free tier cold start: ~30 seconds after 15 min idle." -ForegroundColor Gray
Write-Host ""

# Save API key for Render CLI
$env:RENDERCLI_APIKEY = $script:RenderApiKey
Write-Host "  Tip: To use Render CLI in this session, run:" -ForegroundColor Gray
Write-Host "       `$env:RENDERCLI_APIKEY = '$($script:RenderApiKey.Substring(0,8))...'" -ForegroundColor Gray
Write-Host ""
