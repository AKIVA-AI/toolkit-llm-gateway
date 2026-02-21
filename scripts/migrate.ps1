# Database migration helper script for Toolkit LLM Gateway (PowerShell)

param(
    [Parameter(Position=0)]
    [string]$Command = "help",
    
    [Parameter(Position=1)]
    [string]$Argument = ""
)

# Change to src directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcPath = Join-Path (Split-Path -Parent $scriptPath) "src"
Set-Location $srcPath

# Check if DATABASE_URL is set
if (-not $env:DATABASE_URL) {
    Write-Host "ERROR: DATABASE_URL environment variable is not set" -ForegroundColor Red
    Write-Host "Please set DATABASE_URL before running migrations"
    Write-Host "Example: `$env:DATABASE_URL='postgresql://user:pass@localhost:5432/dbname'"
    exit 1
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

switch ($Command) {
    "init" {
        Write-Info "Initializing Alembic..."
        alembic init alembic
        Write-Info "Alembic initialized successfully"
    }
    
    "create" {
        if (-not $Argument) {
            Write-Error "Migration message required"
            Write-Host "Usage: .\migrate.ps1 create <message>"
            exit 1
        }
        Write-Info "Creating new migration: $Argument"
        alembic revision --autogenerate -m $Argument
        Write-Info "Migration created successfully"
    }
    
    "upgrade" {
        $target = if ($Argument) { $Argument } else { "head" }
        Write-Info "Upgrading database to: $target"
        alembic upgrade $target
        Write-Info "Database upgraded successfully"
    }
    
    "downgrade" {
        $target = if ($Argument) { $Argument } else { "-1" }
        Write-Warning "Downgrading database to: $target"
        $response = Read-Host "Are you sure? (y/N)"
        if ($response -eq "y" -or $response -eq "Y") {
            alembic downgrade $target
            Write-Info "Database downgraded successfully"
        } else {
            Write-Info "Downgrade cancelled"
        }
    }
    
    "current" {
        Write-Info "Current database version:"
        alembic current
    }
    
    "history" {
        Write-Info "Migration history:"
        alembic history
    }
    
    "heads" {
        Write-Info "Current heads:"
        alembic heads
    }
    
    "stamp" {
        if (-not $Argument) {
            Write-Error "Revision required"
            Write-Host "Usage: .\migrate.ps1 stamp <revision>"
            exit 1
        }
        Write-Info "Stamping database with revision: $Argument"
        alembic stamp $Argument
        Write-Info "Database stamped successfully"
    }
    
    default {
        Write-Host "Toolkit LLM Gateway - Database Migration Helper"
        Write-Host ""
        Write-Host "Usage: .\migrate.ps1 <command> [options]"
        Write-Host ""
        Write-Host "Commands:"
        Write-Host "  init              Initialize Alembic (first time only)"
        Write-Host "  create <message>  Create a new migration"
        Write-Host "  upgrade [target]  Upgrade database (default: head)"
        Write-Host "  downgrade [target] Downgrade database (default: -1)"
        Write-Host "  current           Show current database version"
        Write-Host "  history           Show migration history"
        Write-Host "  heads             Show current heads"
        Write-Host "  stamp <revision>  Stamp database with specific revision"
        Write-Host "  help              Show this help message"
        Write-Host ""
        Write-Host "Examples:"
        Write-Host "  .\migrate.ps1 create 'add user table'"
        Write-Host "  .\migrate.ps1 upgrade"
        Write-Host "  .\migrate.ps1 upgrade +1"
        Write-Host "  .\migrate.ps1 downgrade -1"
        Write-Host "  .\migrate.ps1 current"
        Write-Host ""
        Write-Host "Environment Variables:"
        Write-Host "  DATABASE_URL      PostgreSQL connection string (required)"
        Write-Host ""
    }
}

