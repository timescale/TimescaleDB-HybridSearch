#!/usr/bin/env python3
"""
Hybrid Search Demo - Interactive Documentation Search

This demo allows you to enter any query and see how different search methods
perform: vector search, text search, hybrid search, and hybrid + temporal.

The demo generates embeddings on-the-fly for your queries and searches against
a fixed dataset of 150 TimescaleDB documentation documents.

Usage:
    python demo.py

Enter queries when prompted. Type 'quit' or press Ctrl+C to exit.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional
import psycopg
from psycopg.rows import dict_row
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box

from src.config import (
    get_database_url,
    validate_environment
)
from src.search import (
    search_vector,
    search_text,
    search_hybrid,
    search_hybrid_temporal
)

console = Console()


def load_sentence_transformer():
    """
    Load the sentence transformer model for generating embeddings.

    This is loaded once at startup and kept in memory for fast query processing.

    Returns:
        SentenceTransformer model instance
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        console.print("[red]Error: sentence-transformers not installed[/red]")
        console.print("This is a maintainer-only dependency for embedding generation.")
        console.print("\nInstall with: pip install sentence-transformers")
        sys.exit(1)

    console.print("\n[cyan]Loading embedding model...[/cyan]")
    console.print("  Model: all-mpnet-base-v2 (768 dimensions)")

    try:
        model = SentenceTransformer('all-mpnet-base-v2')
        console.print("  ✓ Model loaded successfully\n")
        return model
    except Exception as e:
        console.print(f"[red]Error loading model: {e}[/red]")
        sys.exit(1)


def generate_query_embedding(query_text: str, model) -> List[float]:
    """
    Generate embedding for a user query.

    Args:
        query_text: The query string
        model: Loaded SentenceTransformer model

    Returns:
        768-dimensional embedding vector as list
    """
    embedding = model.encode([query_text], show_progress_bar=False)[0]
    return embedding.tolist()


def render_score_bar(score: float, max_score: float = 1.0, width: int = 25) -> str:
    """
    Render ASCII bar for score visualization.

    Args:
        score: Score value to visualize
        max_score: Maximum possible score for scaling
        width: Width of the bar in characters

    Returns:
        ASCII bar string with score
    """
    bar_width = int((score / max_score) * width)
    bar = "█" * bar_width
    spaces = " " * (width - bar_width)
    return f"{bar}{spaces} {score:.3f}"


def get_trap_indicator(doc: Dict, query_trap_set: Optional[str] = None) -> str:
    """
    Get visual indicator for document's trap type.

    Args:
        doc: Document dict with trap_set and trap_type
        query_trap_set: Optional trap set for context-aware display

    Returns:
        Visual indicator emoji
    """
    doc_trap_set = doc.get('trap_set', '')
    trap_type = doc.get('trap_type', '')

    # If no trap metadata, it's a general document
    if not doc_trap_set or not trap_type:
        return "📄"

    # If query_trap_set provided and matches, show specific indicators
    if query_trap_set and doc_trap_set == query_trap_set:
        if trap_type == 'winner':
            return "🎯"
        elif trap_type in ['semantic_bait', 'keyword_bait', 'temporal_bait']:
            return "🎣"

    # Document from a trap set (but not the query's target set)
    return "📋"


def format_trap_type_display(doc: Dict, query_trap_set: Optional[str] = None) -> str:
    """
    Format trap type for display with simplified labels.

    Args:
        doc: Document dict with trap_set and trap_type
        query_trap_set: Optional trap set for context-aware display

    Returns:
        Formatted string with indicator and label
    """
    indicator = get_trap_indicator(doc, query_trap_set)
    doc_trap_set = doc.get('trap_set')
    trap_type = doc.get('trap_type')

    # Document with no trap metadata
    if not doc_trap_set or not trap_type:
        return f"{indicator} General Document"

    # If query_trap_set matches document's trap_set (relevant to THIS query)
    if query_trap_set and doc_trap_set == query_trap_set:
        if trap_type == 'winner':
            return f"{indicator} Target Answer"
        else:
            # Any type of bait (semantic, keyword, temporal)
            return f"{indicator} Trap Document"

    # Document from a different trap set or general document (not relevant to THIS query)
    return f"{indicator} General Document"


def display_search_results(
    search_result: Dict,
    query_text: str,
    query_trap_set: Optional[str] = None,
    expected_winner_id: Optional[str] = None,
    max_score: float = 1.0
):
    """
    Display search results with SQL, answer preview, and ranking table.

    Args:
        search_result: Dict containing 'results', 'execution_time_ms', 'method', and 'sql'
        query_text: The user's query text
        query_trap_set: Optional trap set for context-aware display
        expected_winner_id: Expected winner document ID for correctness check
        max_score: Maximum score for bar scaling (ignored for text/hybrid methods)
    """
    results = search_result.get('results', [])
    method_name = search_result.get('method', 'Unknown')
    execution_time = search_result.get('execution_time_ms', 0)
    sql_query = search_result.get('sql', '')

    # Print method header (removed performance indicator from title)
    console.print(f"\n[bold cyan]{method_name} - {execution_time:.2f}ms[/bold cyan]\n")

    # Check if results exist
    if not results:
        console.print("[yellow]No results found[/yellow]\n")
        return

    # Get top result info
    top_result = results[0]
    top_doc_id = top_result.get('id')
    top_title = top_result.get('title', 'Untitled')
    top_body = top_result.get('body', '')
    top_tags = top_result.get('tags', [])
    top_category = top_result.get('category', 'Uncategorized')
    top_deprecation_note = top_result.get('deprecation_note', '')

    # Determine correctness
    is_correct = False
    if expected_winner_id:
        is_correct = (top_doc_id == expected_winner_id)

    # Truncate answer for display (300 chars for richer context)
    answer_preview = top_body[:300] + "..." if len(top_body) > 300 else top_body

    # Build answer status text
    top_trap_type = top_result.get('trap_type', '')
    if is_correct:
        answer_status = "✓ Correct"
        answer_text = answer_preview
        answer_border = "green"
        answer_style = "green"
    elif query_trap_set and top_result.get('trap_set') == query_trap_set and top_trap_type != 'winner':
        answer_status = f"✗ Trapped by {top_trap_type}"
        answer_text = answer_preview
        answer_border = "red"
        answer_style = "red"
    else:
        answer_status = "⚠ General Document"
        answer_text = answer_preview
        answer_border = "yellow"
        answer_style = "yellow"

    # Display Query Panel
    console.print(Panel(
        f"[bold]{query_text}[/bold]",
        title="[cyan]Query[/cyan]",
        border_style="cyan",
        padding=(0, 1),
        box=box.ROUNDED
    ))

    # Format tags for display
    tags_display = ', '.join(top_tags) if top_tags else 'none'

    # Truncate tags if too long
    if len(tags_display) > 80:
        tags_display = tags_display[:77] + "..."

    # Truncate title if too long
    title_display = top_title
    if len(title_display) > 100:
        title_display = title_display[:97] + "..."

    # Format deprecation note
    deprecation_display = top_deprecation_note if top_deprecation_note else 'none'

    # Truncate deprecation note if too long
    if len(deprecation_display) > 200 and deprecation_display != 'none':
        deprecation_display = deprecation_display[:197] + "..."

    # Build structured panel content
    panel_content = f"""[{answer_style}]{answer_status}[/{answer_style}]

[bold]Title:[/bold] {title_display}
[bold]Tags:[/bold] {tags_display}
[bold]Category:[/bold] {top_category}
[bold]Deprecation Note:[/bold] {deprecation_display}

[bold]Answer:[/bold]
{answer_preview}"""

    # Display Answer Panel
    console.print(Panel(
        panel_content,
        title=f"[{answer_style}]Answer[/{answer_style}]",
        border_style=answer_border,
        padding=(0, 1),
        box=box.ROUNDED
    ))

    console.print()  # Blank line before table

    # Build results table
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Rank", style="dim", width=4)
    table.add_column("Published Date", style="cyan", width=12)
    table.add_column("CLI Version", style="yellow", width=10)
    table.add_column("Document Type", width=25)
    table.add_column("Score", width=30)

    # Method-specific score bar scaling
    if method_name == "Vector Search":
        scale_max = 1.0
    else:
        # For text and hybrid methods, scale to max in result set
        scores = [float(doc['score']) for doc in results]
        scale_max = max(scores) if scores else 1.0

    for i, doc in enumerate(results, 1):
        trap_type_display = format_trap_type_display(doc, query_trap_set)
        score = float(doc['score'])

        # Format published_date
        published_date = doc.get('published_date')
        if published_date:
            pub_date_str = str(published_date).split()[0] if ' ' in str(published_date) else str(published_date)
        else:
            pub_date_str = "N/A"

        version = doc.get('version', 'N/A')
        score_bar = render_score_bar(score, scale_max)

        table.add_row(
            str(i),
            pub_date_str,
            version,
            trap_type_display,
            score_bar
        )

    console.print(table)

    # Separator line between methods
    console.print("\n" + "-" * 100 + "\n")


def run_all_searches(query_text: str, embedding: List[float], conn_string: str, time_window: str = "12 months"):
    """
    Run all four search methods and display results.

    Args:
        query_text: The search query
        embedding: Query embedding vector
        conn_string: Database connection string
        time_window: Time window for temporal search
    """
    console.print("\n[bold cyan]Searching across all methods...[/bold cyan]\n")

    try:
        # Run all searches
        vector_results = search_vector(embedding, limit=5, conn_string=conn_string)
        text_results = search_text(query_text, limit=5, conn_string=conn_string)
        hybrid_results = search_hybrid(query_text, embedding, limit=5, conn_string=conn_string)
        hybrid_temporal_results = search_hybrid_temporal(
            query_text,
            embedding,
            time_window=time_window,
            limit=5,
            conn_string=conn_string
        )

        # Try to detect trap set and expected winner from top results
        query_trap_set = None
        expected_winner_id = None

        # Check top 5 results from vector search for trap set
        for result in vector_results['results'][:5]:
            trap_set = result.get('trap_set')
            trap_type = result.get('trap_type')
            if trap_set and trap_type == 'winner':
                query_trap_set = trap_set
                expected_winner_id = result.get('id')
                break

        # Display all results with query text and expected winner
        display_search_results(vector_results, query_text, query_trap_set, expected_winner_id)
        display_search_results(text_results, query_text, query_trap_set, expected_winner_id)
        display_search_results(hybrid_results, query_text, query_trap_set, expected_winner_id)
        display_search_results(hybrid_temporal_results, query_text, query_trap_set, expected_winner_id)

        # Simplified performance comparison table
        summary = Table(
            title="Performance Comparison",
            box=box.DOUBLE,
            show_header=True,
            header_style="bold yellow"
        )

        summary.add_column("Method", style="bold", width=20)
        summary.add_column("Execution Time", width=15)

        methods_data = [
            ("Vector Search", vector_results),
            ("Text Search", text_results),
            ("Hybrid Search", hybrid_results),
            ("Hybrid + Temporal", hybrid_temporal_results)
        ]

        for method_name, result_dict in methods_data:
            elapsed = result_dict['execution_time_ms']

            if elapsed < 10:
                time_display = f"[green]{elapsed:.2f}ms[/green]"
            elif elapsed < 50:
                time_display = f"[yellow]{elapsed:.2f}ms[/yellow]"
            else:
                time_display = f"[red]{elapsed:.2f}ms[/red]"

            summary.add_row(method_name, time_display)

        console.print(summary)
        console.print()

    except Exception as e:
        console.print(f"[red]Search error: {e}[/red]")
        import traceback
        traceback.print_exc()


def check_database_ready(conn_string: str) -> bool:
    """
    Check if database has been restored and is ready.

    Args:
        conn_string: Database connection string

    Returns:
        True if ready, False otherwise
    """
    try:
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                # Check if documents table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'documents'
                    );
                """)
                table_exists = cur.fetchone()[0]

                if not table_exists:
                    return False

                # Check document count
                cur.execute("SELECT COUNT(*) FROM documents;")
                doc_count = cur.fetchone()[0]

                if doc_count == 0:
                    return False

                console.print(f"  ✓ Database ready ({doc_count} documents loaded)\n")
                return True

    except Exception as e:
        console.print(f"[red]Database error: {e}[/red]")
        return False


def check_environment():
    """Check environment before starting demo."""
    console.print("\n[bold]Checking environment...[/bold]")

    validation = validate_environment()

    if not validation['database_url']:
        console.print("\n[red]Error: DATABASE_URL not configured[/red]")
        console.print("Please create a .env file with your connection string.")
        console.print("See .env.example for template.\n")
        return False

    console.print(f"  ✓ Database: {validation['connection_type']}")

    # Test database connection
    try:
        conn_string = get_database_url()
        if not check_database_ready(conn_string):
            console.print("\n[red]Error: Database not ready[/red]")
            console.print("\nPlease restore the database first:")
            console.print("  python restore_database.py\n")
            return False
    except Exception as e:
        console.print(f"\n[red]Error: Cannot connect to database[/red]")
        console.print(f"[red]{e}[/red]")
        console.print("\nTroubleshooting:")
        console.print("  • Verify DATABASE_URL in .env")
        console.print("  • For K8s: Check port-forward is running")
        console.print("  • Run: python restore_database.py\n")
        return False

    return True


def show_help():
    """Display help information."""
    help_text = """
[bold cyan]Hybrid Search Demo - Interactive Documentation Search[/bold cyan]

This demo lets you explore how different search methods perform on the same query:

[bold yellow]Search Methods:[/bold yellow]
  1. [cyan]Vector Search[/cyan]      - Semantic similarity using embeddings
  2. [cyan]Text Search[/cyan]        - Full-text search using PostgreSQL
  3. [cyan]Hybrid Search[/cyan]      - Combines vector + text with RRF
  4. [cyan]Hybrid + Temporal[/cyan]  - Hybrid with time-based filtering

[bold yellow]Commands:[/bold yellow]
  [cyan]help[/cyan]     - Show this help message
  [cyan]stats[/cyan]    - Show database statistics
  [cyan]quit[/cyan]     - Exit the demo

[bold yellow]Example Queries:[/bold yellow]
  • How do I configure SCRAM-SHA-256 authentication?
  • Connection refused error when connecting to database
  • How to troubleshoot deployment performance issues?
  • How do I enable debug logging in CLI?
  • What are best practices for connection pooling?

[bold yellow]Tips:[/bold yellow]
  • Try different query styles (questions, keywords, phrases)
  • Notice how each method ranks documents differently
  • Compare execution times across methods
  • Temporal search filters to last 12 months by default
"""
    console.print(Panel(help_text, border_style="cyan"))


def show_stats(conn_string: str):
    """Display database statistics."""
    try:
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                # Total documents
                cur.execute("SELECT COUNT(*) FROM documents;")
                total_docs = cur.fetchone()[0]

                # Trap sets
                cur.execute("""
                    SELECT COUNT(DISTINCT trap_set)
                    FROM documents
                    WHERE trap_set IS NOT NULL;
                """)
                trap_sets = cur.fetchone()[0]

                # Version distribution
                cur.execute("""
                    SELECT version, COUNT(*) as count
                    FROM documents
                    GROUP BY version
                    ORDER BY version;
                """)
                versions = cur.fetchall()

        stats_text = f"""
[bold cyan]Database Statistics[/bold cyan]

[bold]Documents:[/bold] {total_docs} total
[bold]Trap Sets:[/bold] {trap_sets} engineered test cases

[bold]Version Distribution:[/bold]
"""
        for version, count in versions:
            stats_text += f"  • v{version}: {count} documents\n"

        console.print(Panel(stats_text, border_style="green"))

    except Exception as e:
        console.print(f"[red]Error fetching stats: {e}[/red]")


def main():
    """Main application loop."""
    #console.print("\n" + "="*80)
    console.print("[bold cyan]Hybrid Search Demo - Interactive Documentation Search[/bold cyan]")
    #console.print("="*80)

    # Check environment
    if not check_environment():
        sys.exit(1)

    # Load sentence transformer model (once)
    model = load_sentence_transformer()

    conn_string = get_database_url()

    # Show initial help
    console.print("\n[dim]Type 'help' for usage information or enter a query to begin.[/dim]")
    console.print("[dim]Type 'quit' to exit.[/dim]\n")

    # Main query loop
    while True:
        try:
            # Get user query
            query_text = Prompt.ask("\n[bold green]>>[/bold green] Enter your question")

            # Handle special commands
            if query_text.lower() in ['quit', 'exit', 'q']:
                console.print("\n[yellow]Goodbye![/yellow]\n")
                break

            if query_text.lower() == 'help':
                show_help()
                continue

            if query_text.lower() == 'stats':
                show_stats(conn_string)
                continue

            if not query_text.strip():
                console.print("[yellow]Please enter a query or type 'help' for assistance.[/yellow]")
                continue

            # Show what we're searching for
            console.print(f"\n[bold]Query:[/bold] {query_text}")

            # Generate embedding
            console.print("[dim]Generating embedding...[/dim]", end=" ")
            embedding = generate_query_embedding(query_text, model)
            console.print("[green]✓[/green]")

            # Run all searches
            run_all_searches(query_text, embedding, conn_string)

            console.print("-" * 80)

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Interrupted. Type 'quit' to exit or continue with another query.[/yellow]\n")
            continue
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Demo interrupted by user.[/yellow]\n")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
