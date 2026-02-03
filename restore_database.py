#!/usr/bin/env python3
"""
Database Restore Script - Auto-detecting K8s vs Tiger Cloud

This script automatically detects your database type and uses the appropriate
restore method:
  - K8s/Local: Restores from data/hybrid_search_demo.sql.gz
  - Tiger Cloud: Imports data/documents.csv + converts to hypertable

Prerequisites:
  - DATABASE_URL configured in .env file
  - For K8s: port-forward running (kubectl port-forward svc/timescaledb 5432:5432)
  - For Tiger Cloud: Database service created in Timescale Console

Usage:
  python restore_database.py [--force]

Options:
  --force    Skip confirmation prompts and drop existing tables
"""

import gzip
import sys
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table
import psycopg
from dotenv import load_dotenv

console = Console()

# ==============================================================================
# Environment & Configuration
# ==============================================================================

def load_database_url():
    """Load DATABASE_URL from .env file"""
    load_dotenv()
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        console.print("[red]✗ DATABASE_URL not set in .env[/red]")
        console.print("\nPlease configure .env with your database connection:")
        console.print("\nFor K8s (with port-forward):")
        console.print("  DATABASE_URL=postgresql://app:PASSWORD@localhost:5432/app")
        console.print("\nFor Tiger Cloud:")
        console.print("  DATABASE_URL=postgres://tsdbadmin:PASSWORD@HOST.tsdb.cloud.timescale.com:PORT/tsdb?sslmode=require")
        sys.exit(1)

    return database_url

def detect_database_type(database_url: str) -> str:
    """Detect if connection is to Tiger Cloud or K8s/Local"""
    if 'tsdb.cloud.timescale.com' in database_url:
        return 'tiger_cloud'
    return 'k8s_local'

# ==============================================================================
# Connection Testing
# ==============================================================================

def test_connection(conn_string: str, db_type: str) -> bool:
    """Test database connection and check extensions"""
    console.print("\n🔌 Testing database connection...")

    try:
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                # Check PostgreSQL version
                cur.execute("SELECT version();")
                console.print("   ✓ Connected to PostgreSQL")

                # Check required extensions
                cur.execute("""
                    SELECT extname, extversion
                    FROM pg_extension
                    WHERE extname IN ('timescaledb', 'vector', 'vectorscale')
                    ORDER BY extname;
                """)
                extensions = cur.fetchall()

                if len(extensions) < 2:  # At least timescaledb + vector
                    console.print("[yellow]   ⚠ Some extensions missing[/yellow]")
                    console.print(f"   Found: {[e[0] for e in extensions]}")
                    console.print("   Required: timescaledb, vector, vectorscale")
                    return False

                for name, version in extensions:
                    console.print(f"   ✓ {name}: v{version}")

        return True

    except Exception as e:
        console.print(f"[red]✗ Connection failed: {e}[/red]")
        console.print("\n[yellow]Troubleshooting:[/yellow]")
        if db_type == 'k8s_local':
            console.print("  • Ensure port-forward is running:")
            console.print("    kubectl port-forward svc/timescaledb 5432:5432")
        else:
            console.print("  • Check your Tiger Cloud connection string in .env")
            console.print("  • Verify database service is running in Timescale Console")
        return False

# ==============================================================================
# Table Management
# ==============================================================================

def check_existing_tables(conn_string: str) -> dict:
    """Check if documents table already exists"""
    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'documents';
            """)
            documents_exists = cur.fetchone()[0] > 0

            # If table exists, get row count
            row_count = 0
            if documents_exists:
                cur.execute("SELECT COUNT(*) FROM documents;")
                row_count = cur.fetchone()[0]

    return {
        'exists': documents_exists,
        'row_count': row_count
    }

def drop_existing_tables(conn_string: str):
    """Drop existing documents table if it exists"""
    console.print("\n🗑️  Dropping existing tables...")

    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS documents CASCADE;")
            console.print("   ✓ Dropped documents table")
        conn.commit()

# ==============================================================================
# K8s/Local Restore (SQL Method)
# ==============================================================================

def restore_from_sql(conn_string: str):
    """Restore database from compressed SQL backup"""
    console.print("\n📦 Using K8s/Local restore method (SQL dump)")

    # Check backup file exists
    backup_path = Path('data/hybrid_search_demo.sql.gz')
    if not backup_path.exists():
        console.print(f"[red]✗ Backup file not found: {backup_path}[/red]")
        sys.exit(1)

    size_mb = backup_path.stat().st_size / (1024 * 1024)
    console.print(f"   ✓ Backup file found ({size_mb:.2f} MB)")

    # Read and decompress backup
    console.print("\n📄 Loading SQL backup...")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Decompressing backup...", total=None)

        with gzip.open(backup_path, 'rt') as f:
            sql_content = f.read()

        progress.update(task, completed=True)

    console.print(f"   ✓ Decompressed ({len(sql_content) / 1024:.0f} KB)")

    # Execute SQL
    console.print("\n⚙️  Restoring database...")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Executing SQL statements...", total=None)

        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(sql_content)
            conn.commit()

        progress.update(task, completed=True)

    console.print("   ✓ SQL executed successfully")

    # Update published_date with dynamic timestamps
    update_published_dates(conn_string)

# ==============================================================================
# Tiger Cloud Restore (CSV Method)
# ==============================================================================

def create_table_for_csv(conn):
    """Create documents table schema for CSV import"""
    # This matches the CSV structure exactly
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                category TEXT,
                version TEXT,
                created_at TIMESTAMPTZ NOT NULL,
                published_date TIMESTAMPTZ,
                is_deprecated BOOLEAN DEFAULT FALSE,
                deprecation_note TEXT,
                tags TEXT[],
                embedding VECTOR(768),
                trap_set TEXT,
                trap_type TEXT
            );
        """)
    conn.commit()

def import_csv_data(conn, csv_file: Path):
    """Import CSV using psycopg COPY command"""
    with open(csv_file, 'r') as f:
        with conn.cursor() as cur:
            # Use COPY for efficient bulk import
            with cur.copy("COPY documents FROM STDIN WITH (FORMAT CSV, HEADER true)") as copy:
                while data := f.read(8192):
                    copy.write(data)
    conn.commit()

    # Check row count
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents;")
        return cur.fetchone()[0]

def convert_to_hypertable(conn):
    """Convert documents table to TimescaleDB hypertable"""
    with conn.cursor() as cur:
        # Check if already a hypertable
        cur.execute("""
            SELECT COUNT(*)
            FROM timescaledb_information.hypertables
            WHERE hypertable_name = 'documents';
        """)
        is_hypertable = cur.fetchone()[0] > 0

        if is_hypertable:
            console.print("   ℹ Already a hypertable")
            return

        # Convert to hypertable with data migration
        cur.execute("""
            SELECT create_hypertable(
                'documents',
                'created_at',
                chunk_time_interval => INTERVAL '6 months',
                migrate_data => TRUE,
                if_not_exists => TRUE
            );
        """)
    conn.commit()

def add_search_vector_column(conn):
    """Add search_vector generated column for full-text search"""
    with conn.cursor() as cur:
        # Check if column already exists
        cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'documents' AND column_name = 'search_vector';
        """)
        column_exists = cur.fetchone()[0] > 0

        if column_exists:
            console.print("   ℹ search_vector column already exists")
            return

        # Add generated column for full-text search
        # This combines title (weight A) and body (weight B) into a tsvector
        cur.execute("""
            ALTER TABLE documents
            ADD COLUMN search_vector TSVECTOR
            GENERATED ALWAYS AS (
                setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(body, '')), 'B')
            ) STORED;
        """)
    conn.commit()

def create_indexes(conn):
    """Create DiskANN and GIN indexes for vector and text search"""
    with conn.cursor() as cur:
        # DiskANN index for fast approximate nearest neighbor vector search
        # Used by: search_vector(), search_hybrid(), search_hybrid_temporal()
        cur.execute("""
            CREATE INDEX IF NOT EXISTS documents_embedding_idx
            ON documents USING diskann (embedding);
        """)

        # GIN index for full-text search using tsvector
        # Used by: search_text(), search_hybrid(), search_hybrid_temporal()
        cur.execute("""
            CREATE INDEX IF NOT EXISTS documents_search_vector_idx
            ON documents USING GIN (search_vector);
        """)
    conn.commit()

def restore_from_csv(conn_string: str):
    """Restore database from CSV file (Tiger Cloud method)"""
    console.print("\n📦 Using Tiger Cloud restore method (CSV + hypertable)")

    # Check CSV file exists
    csv_file = Path('data/documents.csv')
    if not csv_file.exists():
        console.print(f"[red]✗ CSV file not found: {csv_file}[/red]")
        sys.exit(1)

    size_mb = csv_file.stat().st_size / (1024 * 1024)
    console.print(f"   ✓ CSV file found ({size_mb:.2f} MB)")

    with psycopg.connect(conn_string) as conn:
        # Step 1: Create table schema
        console.print("\n📋 Creating table schema...")
        create_table_for_csv(conn)
        console.print("   ✓ Table created")

        # Step 2: Import CSV data
        console.print("\n📥 Importing CSV data...")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Importing rows...", total=None)
            row_count = import_csv_data(conn, csv_file)
            progress.update(task, completed=True)

        console.print(f"   ✓ Imported {row_count} rows")

        # Step 3: Add search_vector column
        console.print("\n📝 Adding search_vector column...")
        add_search_vector_column(conn)
        console.print("   ✓ search_vector column added")

        # Step 4: Convert to hypertable
        console.print("\n📊 Converting to hypertable...")
        convert_to_hypertable(conn)
        console.print("   ✓ Converted to hypertable (6-month chunks)")

        # Step 5: Create indexes
        console.print("\n🔧 Creating indexes...")
        console.print("   • DiskANN index on embedding...")
        console.print("   • GIN index on search_vector...")
        create_indexes(conn)
        console.print("   ✓ Indexes created")

    # Step 6: Update published_date with dynamic timestamps
    update_published_dates(conn_string)

# ==============================================================================
# Dynamic Timestamp Update (Both Methods)
# ==============================================================================

def update_published_dates(conn_string: str):
    """
    Update published_date column with dynamic timestamps.

    This ensures the demo works perpetually by calculating dates relative to NOW():
      - winner: 3 months ago (should appear in 12-month temporal window)
      - semantic_bait: 6 months ago (still in window, but less relevant)
      - keyword_bait: 9 months ago (still in window, but least relevant)
      - temporal_bait: 3 years ago (excluded by 12-month temporal filter)

    This is critical for the trap quartet methodology to work correctly.
    """
    console.print("\n📅 Updating published_date timestamps...")

    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE documents SET published_date = CASE
                    WHEN trap_type = 'winner'         THEN NOW() - INTERVAL '3 months'
                    WHEN trap_type = 'semantic_bait'  THEN NOW() - INTERVAL '6 months'
                    WHEN trap_type = 'keyword_bait'   THEN NOW() - INTERVAL '9 months'
                    WHEN trap_type = 'temporal_bait'  THEN NOW() - INTERVAL '3 years'
                    ELSE created_at
                END;
            """)
            updated = cur.rowcount
        conn.commit()

    console.print(f"   ✓ Updated {updated} rows with dynamic timestamps")

# ==============================================================================
# Verification
# ==============================================================================

def verify_restore(conn_string: str):
    """Verify database restoration was successful"""
    console.print("\n✅ Verifying setup...")

    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            # Check row count
            cur.execute("SELECT COUNT(*) FROM documents;")
            total = cur.fetchone()[0]

            # Check embeddings
            cur.execute("SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL;")
            with_embeddings = cur.fetchone()[0]

            # Check search_vector
            cur.execute("SELECT COUNT(*) FROM documents WHERE search_vector IS NOT NULL;")
            with_search = cur.fetchone()[0]

            # Check published_date
            cur.execute("SELECT COUNT(*) FROM documents WHERE published_date IS NOT NULL;")
            with_dates = cur.fetchone()[0]

            # Check hypertable
            cur.execute("""
                SELECT num_chunks
                FROM timescaledb_information.hypertables
                WHERE hypertable_name = 'documents';
            """)
            hypertable_result = cur.fetchone()
            num_chunks = hypertable_result[0] if hypertable_result else 0

            # Check indexes
            cur.execute("""
                SELECT COUNT(*)
                FROM pg_indexes
                WHERE tablename = 'documents';
            """)
            num_indexes = cur.fetchone()[0]

    # Build verification table
    table = Table(title="Database Verification")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")

    table.add_row("Total documents", f"{total} rows")
    table.add_row("With embeddings", f"{with_embeddings} rows")
    table.add_row("With search_vector", f"{with_search} rows")
    table.add_row("With published_date", f"{with_dates} rows")
    table.add_row("Hypertable chunks", f"{num_chunks} chunks")
    table.add_row("Indexes", f"{num_indexes} indexes")

    console.print(table)

    # Check for issues
    if total != 150:
        console.print(f"\n[yellow]⚠ Expected 150 documents, found {total}[/yellow]")
        return False

    if with_embeddings != 150:
        console.print(f"\n[yellow]⚠ Not all documents have embeddings ({with_embeddings}/150)[/yellow]")
        return False

    console.print("\n   ✓ All checks passed!")
    return True

# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    """Main execution flow"""
    # Parse arguments
    force = '--force' in sys.argv

    # Display header
    console.print(Panel.fit(
        "[bold]Hybrid Search Demo - Database Restore[/bold]\n"
        "Auto-detecting K8s vs Tiger Cloud",
        border_style="cyan"
    ))

    # Load configuration from .env
    database_url = load_database_url()
    db_type = detect_database_type(database_url)

    # Display detected type
    type_name = "Tiger Cloud" if db_type == 'tiger_cloud' else "K8s/Local"
    console.print(f"\n🔍 Detected database type: [bold]{type_name}[/bold]")

    # Test connection
    if not test_connection(database_url, db_type):
        sys.exit(1)

    # Check for existing tables
    existing = check_existing_tables(database_url)

    if existing['exists']:
        console.print(f"\n[yellow]⚠ documents table already exists ({existing['row_count']} rows)[/yellow]")

        if not force:
            if not Confirm.ask("\nDrop existing table and restore fresh data?", default=False):
                console.print("\n[yellow]Restore cancelled[/yellow]")
                sys.exit(0)

        drop_existing_tables(database_url)

    # Execute appropriate restore method
    console.print("\n" + "=" * 80)
    if db_type == 'tiger_cloud':
        restore_from_csv(database_url)
    else:
        restore_from_sql(database_url)

    # Verify restoration
    if verify_restore(database_url):
        console.print("\n" + "=" * 80)
        console.print("[bold green]✓ Database restore complete![/bold green]")
        console.print("=" * 80)
        console.print("\n📋 Next steps:")
        console.print("   1. Run the demo: python demo.py")
        console.print("   2. Or use the launcher: ./run_demo.sh")
        console.print()
    else:
        console.print("\n[yellow]⚠ Restore completed with warnings[/yellow]")
        console.print("Check the verification results above")
        sys.exit(1)

if __name__ == "__main__":
    main()
