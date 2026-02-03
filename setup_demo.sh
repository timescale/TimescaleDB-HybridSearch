#!/usr/bin/env bash
# ==============================================================================
# Hybrid Search Demo - Complete Setup Script
# ==============================================================================
# This script automates the complete setup process:
#   1. Creates Python virtual environment using uv
#   2. Installs all dependencies
#   3. Detects database type (K8s vs Tiger Cloud)
#   4. Restores database with appropriate method
#
# Prerequisites:
#   - uv package manager installed (https://github.com/astral-sh/uv)
#   - .env file configured with DATABASE_URL
#   - For K8s: port-forward running (kubectl port-forward svc/timescaledb 5432:5432)
#
# Usage:
#   ./setup_demo.sh
#
# ==============================================================================

set -e  # Exit on error

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Print colored message
print_status() {
    local color=$1
    shift
    echo -e "${color}$*${NC}"
}

print_header() {
    echo ""
    echo "=============================================================================="
    print_status "$BLUE" "$*"
    echo "=============================================================================="
    echo ""
}

print_step() {
    print_status "$BLUE" "➤ $*"
}

print_success() {
    print_status "$GREEN" "✓ $*"
}

print_error() {
    print_status "$RED" "✗ $*"
}

print_warning() {
    print_status "$YELLOW" "⚠ $*"
}

# ==============================================================================
# Step 1: Check Prerequisites
# ==============================================================================

print_header "Hybrid Search Demo - Setup"

print_step "Checking prerequisites..."

# Check uv is installed
if ! command -v uv &> /dev/null; then
    print_error "uv package manager not found"
    echo ""
    echo "Please install uv first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    echo "Or visit: https://github.com/astral-sh/uv"
    exit 1
fi
print_success "uv package manager found"

# Check .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found"
    echo ""
    echo "Please create .env file:"
    echo "  cp .env.example .env"
    echo "  # Edit .env and set DATABASE_URL"
    echo ""
    exit 1
fi
print_success ".env file found"

# Validate DATABASE_URL is set
if ! grep -q "^DATABASE_URL=" .env || grep -q "^DATABASE_URL=$" .env; then
    print_error "DATABASE_URL not configured in .env"
    echo ""
    echo "Please edit .env and set DATABASE_URL to your database connection string:"
    echo ""
    echo "For K8s (with port-forward):"
    echo "  DATABASE_URL=postgresql://app:PASSWORD@localhost:5432/app"
    echo ""
    echo "For Tiger Cloud:"
    echo "  DATABASE_URL=postgres://tsdbadmin:PASSWORD@HOST.tsdb.cloud.timescale.com:PORT/tsdb?sslmode=require"
    echo ""
    exit 1
fi
print_success "DATABASE_URL configured"

# ==============================================================================
# Step 2: Setup Python Virtual Environment
# ==============================================================================

print_header "Setting up Python virtual environment"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    print_step "Creating virtual environment..."
    uv venv
    print_success "Virtual environment created"
else
    print_success "Virtual environment already exists"
fi

# Activate virtual environment
print_step "Activating virtual environment..."
source .venv/bin/activate
print_success "Virtual environment activated"

# Install dependencies
print_step "Installing dependencies..."
uv pip install -r requirements.txt > /dev/null 2>&1
print_success "Dependencies installed"

# ==============================================================================
# Step 3: Detect Database Type
# ==============================================================================

print_header "Detecting database type"

# Extract DATABASE_URL from .env
DATABASE_URL=$(grep "^DATABASE_URL=" .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")

# Detect if Tiger Cloud or K8s/Local
if [[ "$DATABASE_URL" == *"tsdb.cloud.timescale.com"* ]]; then
    DB_TYPE="Tiger Cloud"
    RESTORE_METHOD="csv"
else
    DB_TYPE="K8s/Local"
    RESTORE_METHOD="sql"
fi

print_success "Database type detected: $DB_TYPE"
echo "  Connection: ${DATABASE_URL%%@*}@***" # Hide credentials in output

# ==============================================================================
# Step 4: Test Database Connection
# ==============================================================================

print_header "Testing database connection"

# Test connection using psql or Python
if command -v psql &> /dev/null; then
    # Use psql for quick connection test
    if psql "$DATABASE_URL" -c "SELECT 1;" > /dev/null 2>&1; then
        print_success "Database connection successful"
    else
        print_error "Cannot connect to database"
        echo ""
        if [ "$DB_TYPE" = "K8s/Local" ]; then
            print_warning "For K8s deployments, ensure port-forward is running:"
            echo "  kubectl port-forward svc/timescaledb 5432:5432"
        else
            print_warning "Check your Tiger Cloud connection string in .env"
        fi
        echo ""
        exit 1
    fi
else
    # Fall back to Python test
    python3 -c "import psycopg; psycopg.connect('$DATABASE_URL').close()" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Database connection successful"
    else
        print_error "Cannot connect to database"
        echo ""
        if [ "$DB_TYPE" = "K8s/Local" ]; then
            print_warning "For K8s deployments, ensure port-forward is running:"
            echo "  kubectl port-forward svc/timescaledb 5432:5432"
        else
            print_warning "Check your Tiger Cloud connection string in .env"
        fi
        echo ""
        exit 1
    fi
fi

# ==============================================================================
# Step 5: Restore Database
# ==============================================================================

print_header "Restoring database"

if [ "$RESTORE_METHOD" = "csv" ]; then
    # Tiger Cloud: CSV import + setup
    print_step "Using Tiger Cloud restore method (CSV + hypertable conversion)"
    echo ""
    print_warning "Tiger Cloud requires two steps:"
    echo "  1. Import CSV via Python script"
    echo "  2. Convert to hypertable and create indexes"
    echo ""

    # Run CSV import
    print_step "Importing CSV data..."
    python test_tiger_import.py

    # Run Tiger Cloud setup
    print_step "Converting to hypertable and creating indexes..."
    python restore_tiger_cloud.py

else
    # K8s/Local: SQL restore
    print_step "Using K8s/Local restore method (SQL dump)"
    echo ""

    # Run unified restore script
    python restore_database.py
fi

# ==============================================================================
# Step 6: Final Verification
# ==============================================================================

print_header "Verifying setup"

# Quick verification query
DOC_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM documents;" 2>/dev/null | xargs)

if [ "$DOC_COUNT" = "150" ]; then
    print_success "Database verified: 150 documents loaded"
else
    print_warning "Document count: $DOC_COUNT (expected 150)"
fi

# Check for embeddings
EMBED_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL;" 2>/dev/null | xargs)
if [ "$EMBED_COUNT" = "150" ]; then
    print_success "All documents have embeddings"
else
    print_warning "Embeddings: $EMBED_COUNT/150"
fi

# ==============================================================================
# Complete!
# ==============================================================================

print_header "Setup Complete!"

echo "Your hybrid search demo is ready to use!"
echo ""
echo "Next steps:"
echo ""
echo "  1. Run the demo:"
echo "     ./run_demo.sh"
echo ""
echo "  2. Or run directly with Python:"
echo "     source .venv/bin/activate"
echo "     python demo.py"
echo ""
echo "  3. Try example queries:"
echo "     - How to enable debug logging in NovaCLI"
echo "     - Connection refused error when connecting to database"
echo "     - How do I configure SCRAM-SHA-256 authentication?"
echo ""
print_success "Happy searching! 🔍"
echo ""
