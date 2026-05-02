# Idempotent-ish Fly.io deploy script for SchoolTodo.
#
# Prerequisites you must satisfy yourself ONCE:
#   1. flyctl auth login                   (opens browser; persists token in ~/.fly)
#   2. Get a Resend API key from resend.com Dashboard → API Keys
#
# Run: .\scripts\deploy-fly.ps1
#   Optional first arg: app name (must be globally unique on Fly).
#
# The script:
#   - Generates APP_SECRET_KEY with secrets.token_urlsafe(48) and never prints it.
#   - Prompts for the Resend API key (input is hidden) and sends it straight to flyctl secrets.
#   - Creates the app + Postgres cluster + attaches it (DATABASE_URL set automatically).
#   - Sets the rest of the prod secrets, deploys, runs a health check.

param(
    [string]$AppName = "schooltodo-mvp",
    [string]$Region = "fra"
)

$ErrorActionPreference = "Stop"

# Resolve flyctl whether or not it's been added to PATH yet.
$flyctl = if (Get-Command flyctl -ErrorAction SilentlyContinue) {
    "flyctl"
} else {
    "$env:USERPROFILE\.fly\bin\flyctl.exe"
}

if (-not (Test-Path $flyctl)) {
    if ($flyctl -ne "flyctl") {
        Write-Error "flyctl not found. Install it with: iwr https://fly.io/install.ps1 -useb | iex"
        exit 1
    }
}

# Verify we're logged in.
$whoami = & $flyctl auth whoami 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "You are not logged into Fly. Run: flyctl auth login"
    exit 1
}
Write-Host "Logged in as: $whoami"
Write-Host "Target app:   $AppName"
Write-Host "Region:       $Region"
Write-Host ""

# Resend API key — hidden input.
$resendSecure = Read-Host -Prompt "Paste your Resend API key (input hidden)" -AsSecureString
if (-not $resendSecure -or $resendSecure.Length -eq 0) {
    Write-Error "Resend API key is required."
    exit 1
}
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($resendSecure)
$resendKey = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

# Generate the session secret locally; never print or persist it.
$appSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($appSecret)) {
    Write-Error "Failed to generate APP_SECRET_KEY via python."
    exit 1
}

# 1. Create the app if it doesn't exist.
$appExists = (& $flyctl apps list --json | ConvertFrom-Json) | Where-Object { $_.Name -eq $AppName }
if (-not $appExists) {
    Write-Host "==> Creating app $AppName..."
    & $flyctl launch --no-deploy --copy-config --name $AppName --region $Region --org personal --yes
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "==> App $AppName already exists, skipping launch."
}

# 2. Create Postgres cluster if it doesn't exist.
$dbName = "$AppName-db"
$dbExists = (& $flyctl apps list --json | ConvertFrom-Json) | Where-Object { $_.Name -eq $dbName }
if (-not $dbExists) {
    Write-Host "==> Creating Postgres cluster $dbName..."
    & $flyctl postgres create `
        --name $dbName `
        --region $Region `
        --initial-cluster-size 1 `
        --vm-size shared-cpu-1x `
        --volume-size 1
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "==> Postgres $dbName already exists, skipping create."
}

# 3. Attach Postgres (sets DATABASE_URL secret on the app).
Write-Host "==> Attaching Postgres to app..."
& $flyctl postgres attach $dbName --app $AppName 2>&1 | Out-Host

# 4. Set the rest of the secrets.
Write-Host "==> Setting application secrets..."
& $flyctl secrets set --app $AppName `
    APP_BASE_URL="https://$AppName.fly.dev" `
    APP_SECRET_KEY="$appSecret" `
    SMTP_HOST="smtp.resend.com" `
    SMTP_PORT=587 `
    SMTP_USERNAME="resend" `
    SMTP_PASSWORD="$resendKey" `
    SMTP_START_TLS=true `
    SMTP_FROM="onboarding@resend.dev"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Clear secrets from PowerShell memory.
$resendKey = $null
$appSecret = $null
[GC]::Collect()

# 5. Deploy.
Write-Host "==> Deploying..."
& $flyctl deploy --app $AppName
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 6. Health check.
Write-Host ""
Write-Host "==> Health check:"
Start-Sleep -Seconds 3
curl.exe -i "https://$AppName.fly.dev/health"

Write-Host ""
Write-Host "Done. Open: https://$AppName.fly.dev/"
