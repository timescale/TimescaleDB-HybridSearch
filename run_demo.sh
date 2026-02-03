#!/bin/bash

# =============================================================================
# Hybrid Search Demo - Quick Launcher
# =============================================================================
#
# Validates environment and launches the interactive demo.
#
# Prerequisites (see README.md):
#   1. Python 3.10+ with virtual environment
#   2. .env file with DATABASE_URL configured
#   3. Database restored (150 documents loaded)
#
# Usage:
#   ./run_demo.sh
#
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Unicode symbols
CHECK="✓"
CROSS="✗"
WARN="⚠"

# =============================================================================
# Welcome Banner
# =============================================================================

print_banner() {
    clear 2>/dev/null || true
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}                                                                            ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                    ${BOLD}Hybrid Search Demo with TimescaleDB${NC}                     ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                                            ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# =============================================================================
# Environment Checks
# =============================================================================

check_python() {
    # Try to find Python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo -e "${RED}${CROSS} Python not found${NC}"
        echo ""
        echo -e "${YELLOW}Please install Python 3.10+ to continue.${NC}"
        echo -e "Visit: https://www.python.org/downloads/"
        echo ""
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}${CHECK} Python: ${PYTHON_CMD} (${PYTHON_VERSION})${NC}"
}

check_venv() {
    if [ ! -d ".venv" ]; then
        echo -e "${RED}${CROSS} Virtual environment not found${NC}"
        echo ""
        echo -e "${YELLOW}Please create virtual environment first:${NC}"
        echo -e "  ${CYAN}uv venv${NC}  # or: python -m venv .venv"
        echo -e "  ${CYAN}source .venv/bin/activate${NC}"
        echo -e "  ${CYAN}uv pip install -e .${NC}  # or: pip install -r requirements.txt"
        echo ""
        exit 1
    fi

    # Activate if not already active
    if [[ "$VIRTUAL_ENV" != *".venv"* ]]; then
        source .venv/bin/activate
    fi

    echo -e "${GREEN}${CHECK} Virtual environment: .venv${NC}"
}

check_env_file() {
    if [ ! -f ".env" ]; then
        echo -e "${RED}${CROSS} .env file not found${NC}"
        echo ""
        echo -e "${YELLOW}Please configure database connection:${NC}"
        echo -e "  1. ${CYAN}cp .env.example .env${NC}"
        echo -e "  2. Edit .env and add your DATABASE_URL"
        echo ""
        exit 1
    fi

    if ! grep -q "^DATABASE_URL=" .env 2>/dev/null; then
        echo -e "${RED}${CROSS} DATABASE_URL not set in .env${NC}"
        echo ""
        echo -e "${YELLOW}Please configure DATABASE_URL in .env${NC}"
        echo ""
        exit 1
    fi

    echo -e "${GREEN}${CHECK} Configuration: .env${NC}"
}

check_database() {
    source .venv/bin/activate

    DB_CHECK=$($PYTHON_CMD -c "
import sys
try:
    from src.config import get_database_url
    import psycopg

    conn_string = get_database_url()

    # Detect connection type
    if 'tsdb.cloud.timescale.com' in conn_string:
        print('TYPE:Tiger Cloud')
    else:
        print('TYPE:K8s/Local')

    # Test connection
    try:
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_name = \'documents\';')
                table_count = cur.fetchone()[0]

                if table_count == 1:
                    cur.execute('SELECT COUNT(*) FROM documents;')
                    doc_count = cur.fetchone()[0]
                    print(f'DOCS:{doc_count}')

                    if doc_count == 150:
                        print('STATUS:READY')
                    else:
                        print('STATUS:INCOMPLETE')
                else:
                    print('STATUS:NO_TABLES')
    except Exception as e:
        print(f'ERROR:{e}')
        sys.exit(1)

except Exception as e:
    print(f'ERROR:{e}')
    sys.exit(1)
" 2>&1)

    DB_CHECK_EXIT=$?

    if [ $DB_CHECK_EXIT -ne 0 ]; then
        echo -e "${RED}${CROSS} Database connection failed${NC}"
        echo ""
        echo -e "${YELLOW}Troubleshooting:${NC}"
        echo -e "  • For K8s: Ensure port-forward is running:"
        echo -e "    ${CYAN}kubectl port-forward svc/timescaledb 5432:5432${NC}"
        echo -e "  • For Tiger Cloud: Verify credentials in .env"
        echo -e "  • Check DATABASE_URL format in .env"
        echo ""
        exit 1
    fi

    # Parse results
    DB_TYPE=$(echo "$DB_CHECK" | grep "TYPE:" | cut -d: -f2-)
    DB_DOCS=$(echo "$DB_CHECK" | grep "DOCS:" | cut -d: -f2)
    DB_STATUS=$(echo "$DB_CHECK" | grep "STATUS:" | cut -d: -f2)

    echo -e "${GREEN}${CHECK} Database: $DB_TYPE${NC}"

    if [ "$DB_STATUS" = "READY" ]; then
        echo -e "${GREEN}${CHECK} Documents: $DB_DOCS${NC}"
        return 0
    elif [ "$DB_STATUS" = "INCOMPLETE" ]; then
        echo -e "${RED}${CROSS} Data incomplete: $DB_DOCS/150 documents${NC}"
        echo ""
        echo -e "${YELLOW}Please restore database first (see README.md)${NC}"
        echo ""
        exit 1
    else
        echo -e "${RED}${CROSS} Table 'documents' not found${NC}"
        echo ""
        echo -e "${YELLOW}Please restore database first (see README.md)${NC}"
        echo ""
        exit 1
    fi
}

# =============================================================================
# Main
# =============================================================================

main() {
    print_banner

    echo -e "${BOLD}Checking environment...${NC}\n"

    check_python
    check_venv
    check_env_file
    check_database

    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}✓ Environment ready!${NC} ${BOLD}Launching demo...${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
    echo ""

    # Launch demo
    source .venv/bin/activate
    $PYTHON_CMD demo.py

    # After demo exits
    echo ""
    echo -e "${CYAN}Thank you for using the Hybrid Search Demo!${NC}"
    echo -e "${CYAN}Learn more: https://docs.timescale.com/${NC}"
    echo ""
}

# Handle Ctrl+C gracefully
trap 'echo -e "\n\n${YELLOW}Interrupted by user.${NC}\n"; exit 130' INT

# Run
main
