"""CLI entry point for Sia Code."""

import sys
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from . import __version__
from .config import Config
from .indexer.coordinator import IndexingCoordinator
from .storage.factory import create_backend, get_backend_type

console = Console()


def _display_skip_summary(
    console: Console, skipped: dict, verbose: bool = False, max_file_size_mb: float = 5.0
):
    """Display skip summary with optional file details.

    Args:
        console: Rich console for output
        skipped: Dictionary with skip categories
        verbose: Whether to show file names
        max_file_size_mb: Maximum file size threshold for display
    """
    total_skipped = sum(len(v) for v in skipped.values())
    if total_skipped == 0:
        return

    console.print(f"  Files skipped: {total_skipped}")

    categories = [
        ("unsupported_language", "Unsupported language"),
        ("empty_content", "Empty/minimal content"),
        ("parse_errors", "Parse errors"),
        ("too_large", f"Too large (>{max_file_size_mb}MB)"),
    ]

    for key, label in categories:
        items = skipped.get(key, [])
        if not items:
            continue
        console.print(f"    - {label}: {len(items)}")

        if verbose and items:
            # Show first 3 files
            display_items = items[:3]
            for item in display_items:
                if isinstance(item, tuple):
                    path, detail = item
                    # Shorten error messages
                    short_detail = detail if len(detail) < 50 else detail[:47] + "..."
                    console.print(f"        [dim]{Path(path).name}: {short_detail}[/dim]")
                else:
                    console.print(f"        [dim]{Path(item).name}[/dim]")
            if len(items) > 3:
                console.print(f"        [dim]... and {len(items) - 3} more[/dim]")


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def create_backend(index_path: Path, config: Config, valid_chunks=None):
    """Create storage backend with config-based embedding settings.

    NOTE: This function maintains backward compatibility with memvid while supporting
    the new usearch backend. It auto-detects the backend type based on existing files.

    Args:
        index_path: Path to .sia-code directory (or .mv2 file for legacy memvid)
        config: Sia Code configuration
        valid_chunks: Optional set of valid chunk IDs for filtering (memvid only, ignored for usearch)

    Returns:
        Configured StorageBackend instance
    """
    from .storage import factory

    # If index_path is a .mv2 file (legacy), use memvid directly
    if str(index_path).endswith(".mv2"):
        from .storage.backend import MemvidBackend

        return MemvidBackend(
            path=index_path,
            valid_chunks=valid_chunks,
            embedding_enabled=config.embedding.enabled,
            embedding_model=config.embedding.model,
            api_key_env=config.embedding.api_key_env,
        )

    # Otherwise use factory with auto-detection
    return factory.create_backend(
        path=index_path,
        backend_type="auto",
        embedding_enabled=config.embedding.enabled,
        embedding_model=config.embedding.model,
        ndim=config.embedding.dimensions,
        api_key_env=config.embedding.api_key_env,
        valid_chunks=valid_chunks,
    )


def require_initialized() -> tuple[Path, Config]:
    """Ensure Sia Code is initialized, return sia_dir and config.

    Returns:
        Tuple of (sia_dir, config)

    Raises:
        SystemExit: If .sia-code directory doesn't exist
    """
    sia_dir = Path(".sia-code")
    if not sia_dir.exists():
        console.print("[red]Error: Sia Code not initialized. Run 'sia-code init' first.[/red]")
        sys.exit(1)
    config = Config.load(sia_dir / "config.json")
    return sia_dir, config


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(verbose: bool):
    """Sia Code - Local-first codebase intelligence

    Semantic search, multi-hop research, and 12-language AST support.
    """
    setup_logging(verbose)


@main.command()
@click.option("--path", type=click.Path(), default=".", help="Directory to initialize")
@click.option("--dry-run", is_flag=True, help="Preview project analysis without creating index")
def init(path: str, dry_run: bool):
    """Initialize Sia Code in the current directory."""
    from .indexer.project_analyzer import ProjectAnalyzer

    project_dir = Path(path)
    sia_dir = project_dir / ".sia-code"

    if sia_dir.exists() and not dry_run:
        console.print(f"[yellow]Sia Code already initialized at {sia_dir}[/yellow]")
        return

    # Run project analysis
    analyzer = ProjectAnalyzer(project_dir)
    profile = analyzer.analyze()

    # Display analysis results
    console.print("\n[bold]Project Analysis[/bold]")
    console.print(f"  Languages: {', '.join(profile.primary_languages) or 'none detected'}")
    console.print(f"  Multi-language: {'yes' if profile.is_multi_language else 'no'}")
    console.print(f"  Has dependencies: {'yes' if profile.has_dependencies else 'no'}")
    console.print(f"  Has documentation: {'yes' if profile.has_documentation else 'no'}")
    console.print(f"  Recommended strategy: {profile.recommended_strategy}")

    if dry_run:
        console.print("\n[dim]Language detections:[/dim]")
        for detection in profile.detections[:5]:
            console.print(f"  {detection.language}: {detection.confidence:.0%} confidence")
            console.print(f"    Evidence: {', '.join(detection.evidence[:3])}")
        console.print("\n[yellow]Dry run complete. No index created.[/yellow]")
        return

    # Create .sia-code directory
    sia_dir.mkdir(parents=True, exist_ok=True)
    (sia_dir / "cache").mkdir(exist_ok=True)

    # Create config with auto-detected settings
    config = Config()

    # Apply auto-detected tier boost settings
    config.search.tier_boost = profile.tier_boost
    config.search.include_dependencies = profile.has_dependencies

    config.save(sia_dir / "config.json")

    # Create empty index with embedding support
    backend = create_backend(sia_dir, config)
    backend.create_index()
    backend.close()  # Persist vector index to disk

    console.print(f"\n[green]✓[/green] Initialized Sia Code at {sia_dir}")
    console.print("[dim]Next: sia-code index [path][/dim]")


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--update", is_flag=True, help="Re-index changed files only")
@click.option(
    "--clean", is_flag=True, help="Delete existing index and cache, then rebuild from scratch"
)
@click.option(
    "--parallel/--no-parallel",
    default=False,
    help="Use parallel processing (experimental, best for 100+ files)",
)
@click.option(
    "--workers", type=int, default=None, help="Number of worker processes (default: CPU count)"
)
@click.option(
    "--watch", is_flag=True, help="Watch for file changes and auto-reindex (Ctrl+C to stop)"
)
@click.option(
    "--debounce",
    type=float,
    default=2.0,
    help="Seconds to wait before reindexing after changes (default: 2.0)",
)
@click.pass_context
def index(
    ctx: click.Context,
    path: str,
    update: bool,
    clean: bool,
    parallel: bool,
    workers: int | None,
    watch: bool,
    debounce: float,
):
    """Index codebase for search."""
    # Get verbose flag from parent context
    verbose = ctx.parent.params.get("verbose", False) if ctx.parent else False

    sia_dir, config = require_initialized()

    # Handle --clean flag
    backend = create_backend(sia_dir, config)
    if clean:
        console.print("[yellow]Cleaning existing index and cache...[/yellow]")

        # Remove index file
        index_path = sia_dir
        if index_path.exists():
            index_path.unlink()
            console.print(f"  [dim]✓ Deleted: {index_path}[/dim]")

        # Remove cache file
        cache_path = sia_dir / "cache" / "file_hashes.json"
        if cache_path.exists():
            cache_path.unlink()
            console.print(f"  [dim]✓ Deleted: {cache_path}[/dim]")

        console.print("[green]Clean complete. Performing full reindex...[/green]\n")

        # Force full reindex by ensuring update=False
        update = False

        # Recreate index
        backend.create_index()
    else:
        # Open existing index
        backend.open_index()

    # Create coordinator
    coordinator = IndexingCoordinator(config, backend)

    # Index directory
    directory = Path(path).resolve()

    if update:
        console.print(f"[cyan]Incremental indexing {directory}...[/cyan]")
        console.print("[dim]Checking for changes...[/dim]")
    else:
        console.print(f"[cyan]Indexing {directory}...[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Discovering files...", total=None)

        def update_progress(stage: str, current: int, total: int, desc: str):
            """Update progress display based on indexing stage."""
            if stage == "discovering":
                progress.update(task, description="Discovering files...")
            elif stage == "checking":
                # For incremental mode, show checking phase
                if progress.tasks[task].total is None:
                    progress.update(task, total=total, completed=0)
                progress.update(task, completed=current, description=f"Checking: {desc}")
            elif stage == "indexing":
                # Switch to progress bar when indexing starts
                if progress.tasks[task].total is None:
                    progress.update(task, total=total, completed=0)
                progress.update(task, completed=current, description=f"Indexing: {desc}")

        try:
            if update:
                # Incremental indexing with hash cache and chunk index (v2.0)
                from .indexer.hash_cache import HashCache
                from .indexer.chunk_index import ChunkIndex

                cache = HashCache(sia_dir / "cache" / "file_hashes.json")
                chunk_index = ChunkIndex(sia_dir / "chunk_index.json")

                stats = coordinator.index_directory_incremental_v2(
                    directory, cache, chunk_index, progress_callback=update_progress
                )

                console.print("\n[green]✓ Incremental indexing complete (v2.0)[/green]")
                console.print(f"  Changed files: {stats['changed_files']}")
                console.print(f"  Unchanged files: {stats['skipped_files']}")
                console.print(f"  Indexed files: {stats['indexed_files']}/{stats['total_files']}")
                _display_skip_summary(
                    console,
                    stats.get("skipped", {}),
                    verbose=verbose,
                    max_file_size_mb=config.indexing.max_file_size_mb,
                )
                console.print(f"  Total chunks: {stats['total_chunks']}")

                # Show staleness info
                summary = chunk_index.get_staleness_summary()
                if summary.total_chunks > 0:
                    console.print(
                        f"  Index health: {summary.valid_chunks:,} valid, "
                        f"{summary.stale_chunks:,} stale ({summary.staleness_ratio:.1%})"
                    )
            else:
                # Full indexing (parallel by default)
                if parallel:
                    stats = coordinator.index_directory_parallel(
                        directory, max_workers=workers, progress_callback=update_progress
                    )
                else:
                    stats = coordinator.index_directory(
                        directory, progress_callback=update_progress
                    )
                progress.update(task, completed=True)

                console.print("\n[green]✓ Indexing complete[/green]")
                console.print(f"  Files indexed: {stats['indexed_files']}")
                _display_skip_summary(
                    console,
                    stats.get("skipped", {}),
                    verbose=verbose,
                    max_file_size_mb=config.indexing.max_file_size_mb,
                )
                console.print(f"  Total chunks: {stats['total_chunks']}")

            # Show performance metrics if available
            if stats.get("metrics"):
                m = stats["metrics"]
                console.print("\n[dim]Performance:[/dim]")
                console.print(f"  Duration: {m['duration_seconds']}s")
                console.print(
                    f"  Throughput: {m['files_per_second']:.1f} files/s, {m['chunks_per_second']:.1f} chunks/s"
                )
                console.print(f"  Processed: {m['mb_per_second']:.2f} MB/s")

            if stats["errors"]:
                console.print("\n[yellow]Warnings:[/yellow]")
                for error in stats["errors"][:5]:  # Show first 5 errors
                    console.print(f"  {error}")
                if len(stats["errors"]) > 5:
                    console.print(f"  ... and {len(stats['errors']) - 5} more")

            # Close backend to persist vectors to disk
            backend.close()

        except Exception as e:
            console.print(f"[red]Error during indexing: {e}[/red]")
            sys.exit(1)

    # Watch mode
    if watch:
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            import time
            from threading import Timer
        except ImportError:
            console.print("[red]Error: watchdog not installed[/red]")
            console.print("[dim]Install with: pip install watchdog>=3.0[/dim]")
            sys.exit(1)

        class CodeFileHandler(FileSystemEventHandler):
            def __init__(self, debounce_seconds):
                self.debounce_seconds = debounce_seconds
                self.timer = None
                self.pending_changes = set()

            def on_any_event(self, event):
                if event.is_directory:
                    return

                # Only track relevant file changes
                if any(
                    event.src_path.endswith(ext)
                    for ext in [
                        ".py",
                        ".js",
                        ".ts",
                        ".go",
                        ".rs",
                        ".java",
                        ".c",
                        ".cpp",
                        ".cs",
                        ".rb",
                        ".php",
                    ]
                ):
                    self.pending_changes.add(event.src_path)

                    # Reset timer
                    if self.timer:
                        self.timer.cancel()

                    self.timer = Timer(self.debounce_seconds, self.reindex)
                    self.timer.start()

            def reindex(self):
                if not self.pending_changes:
                    return

                console.print(
                    f"\n[yellow]File changes detected: {len(self.pending_changes)} files[/yellow]"
                )
                console.print("[dim]Re-indexing...[/dim]")

                try:
                    # Perform incremental reindex using v2
                    from .indexer.hash_cache import HashCache
                    from .indexer.chunk_index import ChunkIndex

                    cache_path = sia_dir / "cache" / "file_hashes.json"
                    cache = HashCache(cache_path)

                    chunk_index_path = sia_dir / "chunk_index.json"
                    chunk_index = ChunkIndex(chunk_index_path)
                    chunk_index.load()

                    coordinator = IndexingCoordinator(backend=backend, config=config)
                    stats = coordinator.index_directory_incremental_v2(
                        Path(path), cache, chunk_index, progress_callback=None
                    )

                    # Save updated chunk index
                    chunk_index.save()

                    console.print(
                        f"[green]✓[/green] Re-indexed {stats['files_indexed']} files, {stats['chunks_indexed']} chunks"
                    )

                except Exception as e:
                    console.print(f"[red]Error during re-indexing: {e}[/red]")
                finally:
                    self.pending_changes.clear()

        console.print("\n[bold cyan]Watch Mode Active[/bold cyan]")
        console.print(f"[dim]Monitoring: {Path(path).absolute()}[/dim]")
        console.print(f"[dim]Debounce: {debounce}s[/dim]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        event_handler = CodeFileHandler(debounce)
        observer = Observer()
        observer.schedule(event_handler, path, recursive=True)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping watch mode...[/yellow]")
            observer.stop()
            observer.join()
            console.print("[green]✓[/green] Watch mode stopped")
            sys.exit(0)


@main.command()
@click.argument("query")
@click.option("--regex", is_flag=True, help="Use regex/lexical search instead of hybrid")
@click.option("--semantic-only", is_flag=True, help="Use semantic-only search (no BM25)")
@click.option("-k", "--limit", type=int, default=10, help="Number of results")
@click.option("--no-filter", is_flag=True, help="Disable stale chunk filtering")
@click.option("--no-deps", is_flag=True, help="Exclude dependency code from results")
@click.option("--deps-only", is_flag=True, help="Show only dependency code (no project code)")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "table", "csv"]),
    default="text",
    help="Output format (default: text)",
)
@click.option("-o", "--output", type=click.Path(), help="Save results to file instead of stdout")
def search(
    query: str,
    regex: bool,
    semantic_only: bool,
    limit: int,
    no_filter: bool,
    no_deps: bool,
    deps_only: bool,
    output_format: str,
    output: str | None,
):
    """Search the codebase (default: hybrid BM25 + semantic)."""
    from .indexer.chunk_index import ChunkIndex

    sia_dir, config = require_initialized()

    # Load chunk index for filtering (if available and not disabled)
    valid_chunks = None
    if not no_filter:
        chunk_index_path = sia_dir / "chunk_index.json"
        if chunk_index_path.exists():
            try:
                chunk_index = ChunkIndex(chunk_index_path)
                valid_chunks = chunk_index.get_valid_chunks()
            except Exception:
                pass  # Silently fall back to no filtering

    # Handle mutually exclusive dependency flags
    if no_deps and deps_only:
        console.print("[red]Error: --no-deps and --deps-only are mutually exclusive[/red]")
        sys.exit(1)

    backend = create_backend(sia_dir, config, valid_chunks=valid_chunks)
    backend.open_index()

    # Determine dependency filtering
    # Default: include deps (from config or True)
    # --no-deps: exclude deps
    # --deps-only: show only deps (include_deps=True, then filter results)
    include_deps = not no_deps  # Exclude deps if --no-deps is set
    tier_boost = config.search.tier_boost if hasattr(config.search, "tier_boost") else None

    # Determine search mode (NEW: hybrid by default)
    if regex:
        mode = "lexical"
    elif semantic_only:
        mode = "semantic"
    else:
        mode = "hybrid"  # NEW DEFAULT: BM25 + semantic

    filter_status = "" if no_filter or not valid_chunks else " [filtered]"
    deps_status = " [no-deps]" if no_deps else " [deps-only]" if deps_only else ""

    # Suppress progress messages for structured output formats
    if output_format not in ("json", "csv"):
        console.print(f"[dim]Searching ({mode}{filter_status}{deps_status})...[/dim]")

    # Execute search based on mode
    if regex:
        results = backend.search_lexical(
            query, k=limit, include_deps=include_deps, tier_boost=tier_boost
        )
    elif semantic_only:
        results = backend.search_semantic(
            query, k=limit, include_deps=include_deps, tier_boost=tier_boost
        )
    else:
        # NEW: Hybrid search (BM25 + semantic) for best performance
        results = backend.search_hybrid(
            query,
            k=limit,
            vector_weight=config.search.vector_weight,
            include_deps=include_deps,
            tier_boost=tier_boost,
        )

    # Filter for --deps-only after search
    if deps_only and results:
        results = [r for r in results if r.chunk.metadata.get("tier") == "dependency"]

    if not results:
        # Handle empty results based on output format
        if output_format == "json":
            import json

            empty_output = {"query": query, "mode": mode, "results": []}
            print(json.dumps(empty_output, indent=2))
        elif output_format == "csv":
            # CSV header only for empty results
            print("File,Start Line,End Line,Symbol,Score,Preview")
        else:
            console.print("[yellow]No results found[/yellow]")
        return

    # Format results based on output_format
    if output_format == "json":
        import json

        output_data = {"query": query, "mode": mode, "results": [r.to_dict() for r in results]}
        formatted_output = json.dumps(output_data, indent=2)
    elif output_format == "csv":
        import csv
        import io

        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)
        # Write header
        csv_writer.writerow(["File", "Start Line", "End Line", "Symbol", "Score", "Preview"])
        # Write rows
        for result in results:
            chunk = result.chunk
            preview = (result.snippet or chunk.code)[:100].replace("\n", " ").replace("\r", "")
            csv_writer.writerow(
                [
                    chunk.file_path,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.symbol,
                    f"{result.score:.3f}",
                    preview,
                ]
            )
        formatted_output = csv_buffer.getvalue()
    elif output_format == "table":
        table = Table(title=f"Search Results: {query}")
        table.add_column("File", style="cyan")
        table.add_column("Line", style="dim")
        table.add_column("Symbol", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Preview", style="dim")

        for result in results:
            chunk = result.chunk
            preview = (result.snippet or chunk.code)[:80].replace("\n", " ")
            table.add_row(
                str(chunk.file_path),
                f"{chunk.start_line}-{chunk.end_line}",
                chunk.symbol,
                f"{result.score:.3f}",
                preview + "..." if len(preview) == 80 else preview,
            )
        formatted_output = table
    else:  # text format (default)
        formatted_output = None
        for i, result in enumerate(results, 1):
            chunk = result.chunk
            console.print(f"\n[bold cyan]{i}. {chunk.symbol}[/bold cyan]")
            console.print(f"[dim]{chunk.file_path}:{chunk.start_line}-{chunk.end_line}[/dim]")
            console.print(f"Score: {result.score:.3f}")
            if result.snippet:
                console.print(f"\n{result.snippet}\n")

    # Save to file or print to console
    if output:
        try:
            output_path = Path(output)
            if output_format == "json" or output_format == "csv":
                assert isinstance(formatted_output, str)
                output_path.write_text(formatted_output)
            elif output_format == "table":
                from rich.console import Console as FileConsole

                with open(output_path, "w") as f:
                    file_console = FileConsole(file=f, width=120)
                    file_console.print(formatted_output)
            else:  # text format
                # Re-format as plain text for file output
                lines = []
                for i, result in enumerate(results, 1):
                    chunk = result.chunk
                    lines.append(f"{i}. {chunk.symbol}")
                    lines.append(f"   {chunk.file_path}:{chunk.start_line}-{chunk.end_line}")
                    lines.append(f"   Score: {result.score:.3f}")
                    if result.snippet:
                        lines.append(f"\n{result.snippet}\n")
                output_path.write_text("\n".join(lines))
            console.print(f"[green]✓[/green] Results saved to {output}")
        except Exception as e:
            console.print(f"[red]Error saving to file: {e}[/red]")
            sys.exit(1)
    elif formatted_output is not None:
        if output_format == "json" or output_format == "csv":
            # Use print() for JSON/CSV to avoid rich console formatting
            print(formatted_output)
        else:  # table
            console.print(formatted_output)


@main.command()
@click.option("--regex", is_flag=True, help="Use regex/lexical search instead of semantic")
@click.option("-k", "--limit", type=int, default=10, help="Number of results per query")
def interactive(regex: bool, limit: int):
    """Interactive search mode with live query and result navigation.

    Features:
    - Live search as you type
    - Navigate results with arrow keys
    - Preview code chunks
    - Export results to file
    - Press Ctrl+C or Ctrl+D to exit
    """
    try:
        from prompt_toolkit import PromptSession
    except ImportError:
        console.print("[red]Error: prompt-toolkit not installed[/red]")
        console.print("[dim]Install with: pip install prompt-toolkit>=3.0[/dim]")
        sys.exit(1)

    from .indexer.chunk_index import ChunkIndex

    sia_dir, config = require_initialized()

    # Load chunk index for filtering
    valid_chunks = None
    chunk_index_path = sia_dir / "chunk_index.json"
    if chunk_index_path.exists():
        try:
            chunk_index = ChunkIndex(chunk_index_path)
            valid_chunks = chunk_index.get_valid_chunks()
        except Exception:
            pass

    backend = create_backend(sia_dir, config, valid_chunks=valid_chunks)
    backend.open_index()

    mode = "lexical" if regex else "semantic"
    console.print(f"[bold cyan]Sia Code Interactive Search[/bold cyan] ({mode} mode)")
    console.print("[dim]Type your query and press Enter. Ctrl+C or Ctrl+D to exit.[/dim]\n")

    session = PromptSession()
    current_results = []
    current_query = ""

    while True:
        try:
            # Get query from user
            query = session.prompt("Search> ")
            if not query.strip():
                continue

            current_query = query
            console.print(f"[dim]Searching for: {query}[/dim]")

            # Perform search
            if regex:
                results = backend.search_lexical(query, k=limit)
            else:
                results = backend.search_semantic(query, k=limit)

            current_results = results

            if not results:
                console.print("[yellow]No results found[/yellow]\n")
                continue

            # Display results
            console.print(f"\n[bold]Found {len(results)} results:[/bold]\n")
            for i, result in enumerate(results, 1):
                chunk = result.chunk
                console.print(f"[cyan]{i}.[/cyan] {chunk.symbol}")
                console.print(
                    f"   [dim]{chunk.file_path}:{chunk.start_line}-{chunk.end_line}[/dim]"
                )
                console.print(f"   Score: {result.score:.3f}")

                # Show preview
                if result.snippet:
                    preview = result.snippet[:150]
                    console.print(
                        f"   [dim]{preview}{'...' if len(result.snippet) > 150 else ''}[/dim]"
                    )
                console.print()

            # Ask what to do next
            action = session.prompt(
                "\nAction: [v]iew result, [e]xport to file, [n]ew query, [q]uit > "
            )

            if action.lower() == "q":
                console.print("[green]Goodbye![/green]")
                break
            elif action.lower() == "v":
                try:
                    idx = int(
                        session.prompt("Enter result number to view (1-{}): ".format(len(results)))
                    )
                    if 1 <= idx <= len(results):
                        result = results[idx - 1]
                        chunk = result.chunk
                        console.print(f"\n[bold cyan]{chunk.symbol}[/bold cyan]")
                        console.print(
                            f"[dim]{chunk.file_path}:{chunk.start_line}-{chunk.end_line}[/dim]\n"
                        )
                        console.print(chunk.code)
                        console.print()
                    else:
                        console.print("[yellow]Invalid result number[/yellow]\n")
                except (ValueError, EOFError):
                    console.print("[yellow]Invalid input[/yellow]\n")
            elif action.lower() == "e":
                try:
                    filename = session.prompt("Export filename (e.g., results.json): ")
                    if filename:
                        import json

                        output_data = {
                            "query": current_query,
                            "mode": mode,
                            "results": [r.to_dict() for r in current_results],
                        }
                        Path(filename).write_text(json.dumps(output_data, indent=2))
                        console.print(f"[green]✓[/green] Results exported to {filename}\n")
                except (EOFError, KeyboardInterrupt):
                    console.print("[yellow]Export cancelled[/yellow]\n")
            elif action.lower() == "n":
                continue
            else:
                console.print("[yellow]Unknown action[/yellow]\n")

        except (EOFError, KeyboardInterrupt):
            console.print("\n[green]Goodbye![/green]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]\n")


@main.command()
@click.argument("question")
@click.option("--hops", type=int, default=2, help="Maximum relationship hops")
@click.option("--graph", is_flag=True, help="Show call graph")
@click.option("-k", "--limit", type=int, default=5, help="Results per hop")
@click.option("--no-filter", is_flag=True, help="Disable stale chunk filtering")
def research(question: str, hops: int, graph: bool, limit: int, no_filter: bool):
    """Multi-hop code research for architectural questions.

    Automatically discovers code relationships and builds a complete picture.

    Examples:
        sia-code research "How does authentication work?"
        sia-code research "What calls the indexer?" --graph
        sia-code research "How is configuration loaded?" --hops 3
    """
    from .indexer.chunk_index import ChunkIndex
    from .search.multi_hop import MultiHopSearchStrategy

    sia_dir, config = require_initialized()

    # Load chunk index for filtering (if available and not disabled)
    valid_chunks = None
    if not no_filter:
        chunk_index_path = sia_dir / "chunk_index.json"
        if chunk_index_path.exists():
            try:
                chunk_index = ChunkIndex(chunk_index_path)
                valid_chunks = chunk_index.get_valid_chunks()
            except Exception:
                pass  # Silently fall back to no filtering

    backend = create_backend(sia_dir, config, valid_chunks=valid_chunks)
    backend.open_index()

    strategy = MultiHopSearchStrategy(backend, max_hops=hops)

    console.print(f"[dim]Researching: {question}[/dim]")
    console.print(f"[dim]Max hops: {hops}, Results per hop: {limit}[/dim]\n")

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task("Analyzing code relationships...", total=None)
        result = strategy.research(question, max_results_per_hop=limit)
        progress.update(task, completed=True)

    # Display results summary
    console.print("\n[bold green]✓ Research Complete[/bold green]")
    console.print(f"  Found: {len(result.chunks)} related code chunks")
    console.print(f"  Relationships: {len(result.relationships)}")
    console.print(f"  Entities discovered: {result.total_entities_found}")
    console.print(f"  Hops executed: {result.hops_executed}/{hops}\n")

    if not result.chunks:
        console.print("[yellow]No relevant code found. Try rephrasing your question.[/yellow]")
        return

    # Display top chunks
    console.print("[bold]Top Related Code:[/bold]\n")
    for i, chunk in enumerate(result.chunks[:10], 1):
        console.print(f"{i}. [cyan]{chunk.symbol}[/cyan]")
        console.print(f"   {chunk.file_path}:{chunk.start_line}-{chunk.end_line}")
        if i <= 3:  # Show code preview for top 3
            preview = chunk.code[:200].replace("\n", "\n   ")
            console.print(f"   [dim]{preview}...[/dim]")
        console.print()

    # Show call graph if requested
    if graph and result.relationships:
        call_graph = strategy.build_call_graph(result.relationships)
        entry_points = strategy.get_entry_points(result.relationships)

        console.print("\n[bold]Call Graph:[/bold]\n")

        if entry_points:
            console.print("[dim]Entry points:[/dim]")
            for entry in entry_points[:5]:
                console.print(f"  [green]→ {entry}[/green]")
            console.print()

        console.print("[dim]Relationships:[/dim]")
        for entity, targets in list(call_graph.items())[:15]:
            console.print(f"  {entity}")
            for target in targets[:3]:
                rel_type = target["type"].replace("_", " ")
                console.print(f"    [dim]{rel_type}[/dim] → {target['target']}")

        if len(call_graph) > 15:
            console.print(f"\n  [dim]... and {len(call_graph) - 15} more entities[/dim]")


@main.command()
def status():
    """Show index statistics and health."""
    import datetime
    import json
    from .indexer.chunk_index import ChunkIndex

    sia_dir, config = require_initialized()

    backend = create_backend(sia_dir, config)
    stats = backend.get_stats()

    table = Table(title="Sia Code Index Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Index Path", str(stats["path"]))
    table.add_row("Exists", "Yes" if stats["exists"] else "No")

    # Cache statistics
    cache_path = sia_dir / "cache" / "file_hashes.json"
    if cache_path.exists():
        try:
            cache_data = json.loads(cache_path.read_text())
            cache_size = cache_path.stat().st_size
            table.add_row("", "")  # Separator
            table.add_row("Cached Files", str(len(cache_data)))
            table.add_row("Cache Size", f"{cache_size:,} bytes")
        except (json.JSONDecodeError, OSError):
            pass

    # Index age and size
    index_path = sia_dir
    if index_path.exists():
        try:
            stat = index_path.stat()
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
            age = datetime.datetime.now() - mtime
            table.add_row("", "")  # Separator
            table.add_row("Index Size", f"{stat.st_size:,} bytes")
            table.add_row("Index Age", f"{age.days} days, {age.seconds // 3600} hours")
        except OSError:
            pass

    # Chunk index staleness (v2.0)
    chunk_index_path = sia_dir / "chunk_index.json"
    if chunk_index_path.exists():
        try:
            chunk_index = ChunkIndex(chunk_index_path)
            summary = chunk_index.get_staleness_summary()

            table.add_row("", "")  # Separator
            table.add_row("Total Chunks", f"{summary.total_chunks:,}")
            table.add_row("Valid Chunks", f"{summary.valid_chunks:,}")
            table.add_row("Stale Chunks", f"{summary.stale_chunks:,}")
            table.add_row("Staleness Ratio", f"{summary.staleness_ratio:.1%}")
            table.add_row("Health Status", summary.status)
        except Exception:
            pass

    console.print(table)

    # Recommendations
    if chunk_index_path.exists():
        try:
            chunk_index = ChunkIndex(chunk_index_path)
            summary = chunk_index.get_staleness_summary()

            if summary.staleness_ratio >= 0.2:
                console.print(f"\n{summary.status}")
                console.print(f"[dim]Recommendation: {summary.recommendation}[/dim]")
        except Exception:
            pass
    elif index_path.exists():
        # Fallback to age-based warning
        try:
            stat = index_path.stat()
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
            age = datetime.datetime.now() - mtime
            if age.days > 30:
                console.print("\n[yellow]⚠️  Warning: Index is over 30 days old.[/yellow]")
                console.print(
                    "[dim]Consider running 'sia-code index --clean' to rebuild fresh index.[/dim]"
                )
        except OSError:
            pass


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--threshold", type=float, default=0.2, help="Minimum staleness ratio to compact")
@click.option("--force", is_flag=True, help="Force compaction regardless of threshold")
def compact(path: str, threshold: float, force: bool):
    """Compact index by removing stale chunks.

    This rebuilds the index with only valid chunks, removing all stale
    chunks that accumulated from file modifications. Improves search
    quality and reduces index size.

    Example:
        sia-code compact              # Compact if >20% stale
        sia-code compact --threshold 0.1  # Compact if >10% stale
        sia-code compact --force      # Force compaction now
    """
    from .indexer.chunk_index import ChunkIndex

    sia_dir, config = require_initialized()

    # Check if chunk index exists
    chunk_index_path = sia_dir / "chunk_index.json"
    if not chunk_index_path.exists():
        console.print("[yellow]Chunk index not found. Compaction requires chunk tracking.[/yellow]")
        console.print(
            "[dim]Run incremental indexing to build chunk index, or use --clean to rebuild.[/dim]"
        )
        sys.exit(1)

    # Load chunk index
    chunk_index = ChunkIndex(chunk_index_path)
    summary = chunk_index.get_staleness_summary()

    console.print("[cyan]Index Health Check[/cyan]")
    console.print(f"  Total chunks: {summary.total_chunks:,}")
    console.print(f"  Valid chunks: {summary.valid_chunks:,}")
    console.print(f"  Stale chunks: {summary.stale_chunks:,}")
    console.print(f"  Staleness: {summary.staleness_ratio:.1%}")
    console.print(f"  Status: {summary.status}\n")

    # Load backend
    backend = create_backend(sia_dir, config)
    backend.open_index()

    coordinator = IndexingCoordinator(config, backend)
    directory = Path(path).resolve()

    # Override threshold if force
    if force:
        threshold = 0.0
        console.print("[yellow]Forcing compaction...[/yellow]\n")

    # Perform compaction
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task("Compacting index...", total=None)

        try:
            stats = coordinator.compact_index(directory, chunk_index, threshold)
            progress.update(task, completed=True)

            if not stats["compaction_needed"]:
                console.print(f"\n[green]✓ {stats['message']}[/green]")
            else:
                console.print("\n[green]✓ Compaction complete[/green]")
                console.print(f"  Files reindexed: {stats['files_reindexed']}")
                console.print(f"  Chunks stored: {stats['chunks_stored']}")
                console.print(
                    f"  Removed {stats['stale_chunks']:,} stale chunks "
                    f"({stats['staleness_ratio']:.1%} of total)"
                )

                if stats.get("metrics"):
                    m = stats["metrics"]
                    console.print("\n[dim]Performance:[/dim]")
                    console.print(f"  Duration: {m['duration_seconds']}s")
                    console.print(
                        f"  Throughput: {m['files_per_second']:.1f} files/s, "
                        f"{m['chunks_per_second']:.1f} chunks/s"
                    )

                if stats["errors"]:
                    console.print("\n[yellow]Warnings:[/yellow]")
                    for error in stats["errors"][:5]:
                        console.print(f"  {error}")
                    if len(stats["errors"]) > 5:
                        console.print(f"  ... and {len(stats['errors']) - 5} more")

        except Exception as e:
            console.print(f"[red]Error during compaction: {e}[/red]")
            sys.exit(1)


@main.group()
def config():
    """Manage Sia Code configuration."""
    pass


@config.command(name="show")
def config_show():
    """Display current configuration."""
    sia_dir, cfg = require_initialized()
    config_path = sia_dir / "config.json"

    console.print("[bold cyan]Sia Code Configuration[/bold cyan]\n")
    console.print(cfg.model_dump_json(indent=2))
    console.print(f"\n[dim]Config file: {config_path}[/dim]")


@config.command(name="path")
def config_path():
    """Show configuration file path."""
    sia_dir, _ = require_initialized()
    config_path = sia_dir / "config.json"
    console.print(str(config_path.absolute()))


@config.command(name="edit")
def config_edit():
    """Open configuration in $EDITOR."""
    import os
    import subprocess

    sia_dir, _ = require_initialized()
    config_path = sia_dir / "config.json"

    editor = os.environ.get("EDITOR", "nano")
    try:
        subprocess.run([editor, str(config_path)], check=True)
        console.print("[green]✓[/green] Configuration updated")

        # Validate the edited config
        try:
            Config.load(config_path)
            console.print("[green]✓[/green] Configuration is valid")
        except Exception as e:
            console.print(f"[red]Error: Invalid configuration: {e}[/red]")
            console.print("[yellow]Please fix the configuration file manually[/yellow]")
            sys.exit(1)
    except subprocess.CalledProcessError:
        console.print("[yellow]Editor exited with error[/yellow]")
        sys.exit(1)
    except FileNotFoundError:
        console.print(f"[red]Error: Editor '{editor}' not found[/red]")
        console.print("[dim]Set $EDITOR environment variable or install nano[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
