#!/bin/bash
# Database migration helper script for Toolkit LLM Gateway

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to src directory
cd "$(dirname "$0")/../src" || exit 1

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}ERROR: DATABASE_URL environment variable is not set${NC}"
    echo "Please set DATABASE_URL before running migrations"
    echo "Example: export DATABASE_URL=postgresql://user:pass@localhost:5432/dbname"
    exit 1
fi

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse command
COMMAND=${1:-help}

case $COMMAND in
    init)
        print_info "Initializing Alembic..."
        alembic init alembic
        print_info "Alembic initialized successfully"
        ;;
    
    create)
        if [ -z "$2" ]; then
            print_error "Migration message required"
            echo "Usage: $0 create <message>"
            exit 1
        fi
        print_info "Creating new migration: $2"
        alembic revision --autogenerate -m "$2"
        print_info "Migration created successfully"
        ;;
    
    upgrade)
        TARGET=${2:-head}
        print_info "Upgrading database to: $TARGET"
        alembic upgrade "$TARGET"
        print_info "Database upgraded successfully"
        ;;
    
    downgrade)
        TARGET=${2:--1}
        print_warning "Downgrading database to: $TARGET"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            alembic downgrade "$TARGET"
            print_info "Database downgraded successfully"
        else
            print_info "Downgrade cancelled"
        fi
        ;;
    
    current)
        print_info "Current database version:"
        alembic current
        ;;
    
    history)
        print_info "Migration history:"
        alembic history
        ;;
    
    heads)
        print_info "Current heads:"
        alembic heads
        ;;
    
    stamp)
        if [ -z "$2" ]; then
            print_error "Revision required"
            echo "Usage: $0 stamp <revision>"
            exit 1
        fi
        print_info "Stamping database with revision: $2"
        alembic stamp "$2"
        print_info "Database stamped successfully"
        ;;
    
    help|*)
        echo "Toolkit LLM Gateway - Database Migration Helper"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  init              Initialize Alembic (first time only)"
        echo "  create <message>  Create a new migration"
        echo "  upgrade [target]  Upgrade database (default: head)"
        echo "  downgrade [target] Downgrade database (default: -1)"
        echo "  current           Show current database version"
        echo "  history           Show migration history"
        echo "  heads             Show current heads"
        echo "  stamp <revision>  Stamp database with specific revision"
        echo "  help              Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 create 'add user table'"
        echo "  $0 upgrade"
        echo "  $0 upgrade +1"
        echo "  $0 downgrade -1"
        echo "  $0 current"
        echo ""
        echo "Environment Variables:"
        echo "  DATABASE_URL      PostgreSQL connection string (required)"
        echo ""
        ;;
esac

