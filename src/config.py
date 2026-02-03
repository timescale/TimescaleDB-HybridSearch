"""
Configuration management for the hybrid search demo.

Handles database connections for both Tiger Cloud and K8s/Local deployments.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_database_url() -> str:
    """
    Get database URL from environment variables.

    Returns:
        Database connection string

    Raises:
        ValueError: If DATABASE_URL is not set
    """
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError(
            "DATABASE_URL not found in environment.\n"
            "Please create a .env file with your connection string.\n"
            "See .env.example for template."
        )
    return db_url


def is_tiger_cloud() -> bool:
    """
    Detect if connection is to Tiger Cloud or K8s/Local.

    Returns:
        True if Tiger Cloud, False if K8s/Local
    """
    db_url = get_database_url()
    return 'tsdb.cloud.timescale.com' in db_url


def get_backup_path() -> Path:
    """
    Get path to the database backup file.

    Returns:
        Path to hybrid_search_demo.sql.gz
    """
    project_root = Path(__file__).parent.parent
    return project_root / 'data' / 'hybrid_search_demo.sql.gz'


def get_queries_json_path() -> Path:
    """
    Get path to the demo queries JSON file.

    Returns:
        Path to demo_queries.json
    """
    project_root = Path(__file__).parent.parent
    return project_root / 'data' / 'demo_queries.json'


def validate_environment() -> dict:
    """
    Validate environment configuration and return status.

    Returns:
        Dictionary with validation results
    """
    results = {
        'database_url': False,
        'backup_file': False,
        'queries_file': False,
        'connection_type': None,
        'errors': []
    }

    # Check DATABASE_URL
    try:
        db_url = get_database_url()
        results['database_url'] = True
        results['connection_type'] = 'Tiger Cloud' if is_tiger_cloud() else 'K8s/Local'
    except ValueError as e:
        results['errors'].append(str(e))

    # Check backup file
    backup_path = get_backup_path()
    if backup_path.exists():
        results['backup_file'] = True
    else:
        results['errors'].append(f"Backup file not found: {backup_path}")

    # Check queries JSON
    queries_path = get_queries_json_path()
    if queries_path.exists():
        results['queries_file'] = True
    else:
        results['errors'].append(f"Queries file not found: {queries_path}")

    return results


def get_connection_info() -> dict:
    """
    Get human-readable connection information.

    Returns:
        Dictionary with connection details for display
    """
    try:
        db_url = get_database_url()
        connection_type = 'Tiger Cloud' if is_tiger_cloud() else 'K8s/Local'

        # Parse connection string for display (without password)
        parts = db_url.split('@')
        if len(parts) == 2:
            host_info = parts[1].split(':')[0]
        else:
            host_info = "localhost"

        return {
            'type': connection_type,
            'host': host_info,
            'configured': True
        }
    except ValueError:
        return {
            'type': 'Unknown',
            'host': 'Not configured',
            'configured': False
        }
