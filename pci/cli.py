"""CLI entry point for PCI."""

import sys
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import __version__
from .config import Config
from .indexer.coordinator import IndexingCoordinator
from .storage.backend import MemvidBackend

console = Console()


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def create_backend(index_path: Path, config: Config, valid_chunks=None) -> MemvidBackend:
    """Create MemvidBackend with config-based embedding settings.

    Args:
        index_path: Path to index .mv2 file
        config: PCI configuration
        valid_chunks: Optional set of valid chunk IDs for filtering

    Returns:
        Configured MemvidBackend instance
    """
    return MemvidBackend(
        path=index_path,
        valid_chunks=valid_chunks,
        embedding_enabled=config.embedding.enabled,
        embedding_model=config.embedding.model,
        api_key_env=config.embedding.api_key_env,
    )


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(verbose: bool):
    """PCI - Portable Code Index

    Local-first codebase intelligence with semantic search.
    """
    setup_logging(verbose)


@main.command()
@click.option("--path", type=click.Path(), default=".", help="Directory to initialize")
def init(path: str):
    """Initialize PCI in the current directory."""
    project_dir = Path(path)
    pci_dir = project_dir / ".pci"

    if pci_dir.exists():
        console.print(f"[yellow]PCI already initialized at {pci_dir}[/yellow]")
        return

    # Create .pci directory
    pci_dir.mkdir(parents=True, exist_ok=True)
    (pci_dir / "cache").mkdir(exist_ok=True)

    # Create default config
    config = Config()
    config.save(pci_dir / "config.json")

    # Create empty index with embedding support
    backend = create_backend(pci_dir / "index.mv2", config)
    backend.create_index()

    console.print(f"[green]✓[/green] Initialized PCI at {pci_dir}")
    console.print(f"[dim]Next: pci index [path][/dim]")


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
def index(path: str, update: bool, clean: bool, parallel: bool, workers: int | None):
    """Index codebase for search."""
    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized. Run 'pci init' first.[/red]")
        sys.exit(1)

    # Load config
    config = Config.load(pci_dir / "config.json")

    # Handle --clean flag
    backend = create_backend(pci_dir / "index.mv2", config)
    if clean:
        console.print("[yellow]Cleaning existing index and cache...[/yellow]")

        # Remove index file
        index_path = pci_dir / "index.mv2"
        if index_path.exists():
            index_path.unlink()
            console.print(f"  [dim]✓ Deleted: {index_path}[/dim]")

        # Remove cache file
        cache_path = pci_dir / "cache" / "file_hashes.json"
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
        console.print(f"[dim]Checking for changes...[/dim]")
    else:
        console.print(f"[cyan]Indexing {directory}...[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Discovering files...", total=None)

        try:
            if update:
                # Incremental indexing with hash cache and chunk index (v2.0)
                from .indexer.hash_cache import HashCache
                from .indexer.chunk_index import ChunkIndex

                cache = HashCache(pci_dir / "cache" / "file_hashes.json")
                chunk_index = ChunkIndex(pci_dir / "chunk_index.json")

                stats = coordinator.index_directory_incremental_v2(directory, cache, chunk_index)

                console.print(f"\n[green]✓ Incremental indexing complete (v2.0)[/green]")
                console.print(f"  Changed files: {stats['changed_files']}")
                console.print(f"  Skipped files: {stats['skipped_files']}")
                console.print(f"  Indexed files: {stats['indexed_files']}/{stats['total_files']}")
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
                    stats = coordinator.index_directory_parallel(directory, max_workers=workers)
                else:
                    stats = coordinator.index_directory(directory)
                progress.update(task, completed=True)

                console.print(f"\n[green]✓ Indexing complete[/green]")
                console.print(f"  Files indexed: {stats['indexed_files']}/{stats['total_files']}")
                console.print(f"  Total chunks: {stats['total_chunks']}")

            # Show performance metrics if available
            if stats.get("metrics"):
                m = stats["metrics"]
                console.print(f"\n[dim]Performance:[/dim]")
                console.print(f"  Duration: {m['duration_seconds']}s")
                console.print(
                    f"  Throughput: {m['files_per_second']:.1f} files/s, {m['chunks_per_second']:.1f} chunks/s"
                )
                console.print(f"  Processed: {m['mb_per_second']:.2f} MB/s")

            if stats["errors"]:
                console.print(f"\n[yellow]Warnings:[/yellow]")
                for error in stats["errors"][:5]:  # Show first 5 errors
                    console.print(f"  {error}")
                if len(stats["errors"]) > 5:
                    console.print(f"  ... and {len(stats['errors']) - 5} more")

        except Exception as e:
            console.print(f"[red]Error during indexing: {e}[/red]")
            sys.exit(1)


@main.command()
@click.argument("query")
@click.option("--regex", is_flag=True, help="Use regex/lexical search instead of semantic")
@click.option("-k", "--limit", type=int, default=10, help="Number of results")
@click.option("--no-filter", is_flag=True, help="Disable stale chunk filtering")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "table"]),
    default="text",
    help="Output format (default: text)",
)
@click.option("-o", "--output", type=click.Path(), help="Save results to file instead of stdout")
def search(
    query: str, regex: bool, limit: int, no_filter: bool, output_format: str, output: str | None
):
    """Search the codebase."""
    from .indexer.chunk_index import ChunkIndex

    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized. Run 'pci init' first.[/red]")
        sys.exit(1)

    # Load config
    config = Config.load(pci_dir / "config.json")

    # Load chunk index for filtering (if available and not disabled)
    valid_chunks = None
    if not no_filter:
        chunk_index_path = pci_dir / "chunk_index.json"
        if chunk_index_path.exists():
            try:
                chunk_index = ChunkIndex(chunk_index_path)
                valid_chunks = chunk_index.get_valid_chunks()
            except Exception:
                pass  # Silently fall back to no filtering

    backend = create_backend(pci_dir / "index.mv2", config, valid_chunks=valid_chunks)
    backend.open_index()

    mode = "lexical" if regex else "semantic"
    filter_status = "" if no_filter or not valid_chunks else " [filtered]"
    console.print(f"[dim]Searching ({mode}{filter_status})...[/dim]")

    if regex:
        results = backend.search_lexical(query, k=limit)
    else:
        results = backend.search_semantic(query, k=limit)

    if not results:
        console.print("[yellow]No results found[/yellow]")
        return

    # Format results based on output_format
    if output_format == "json":
        import json

        output_data = {"query": query, "mode": mode, "results": [r.to_dict() for r in results]}
        formatted_output = json.dumps(output_data, indent=2)
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
            if output_format == "json":
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
        if output_format == "json":
            console.print(formatted_output)
        else:  # table
            console.print(formatted_output)


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
        pci research "How does authentication work?"
        pci research "What calls the indexer?" --graph
        pci research "How is configuration loaded?" --hops 3
    """
    from .indexer.chunk_index import ChunkIndex
    from .search.multi_hop import MultiHopSearchStrategy

    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized. Run 'pci init' first.[/red]")
        sys.exit(1)

    # Load config
    config = Config.load(pci_dir / "config.json")

    # Load chunk index for filtering (if available and not disabled)
    valid_chunks = None
    if not no_filter:
        chunk_index_path = pci_dir / "chunk_index.json"
        if chunk_index_path.exists():
            try:
                chunk_index = ChunkIndex(chunk_index_path)
                valid_chunks = chunk_index.get_valid_chunks()
            except Exception:
                pass  # Silently fall back to no filtering

    backend = create_backend(pci_dir / "index.mv2", config, valid_chunks=valid_chunks)
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
    console.print(f"\n[bold green]✓ Research Complete[/bold green]")
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

    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized[/red]")
        sys.exit(1)

    # Load config
    config = Config.load(pci_dir / "config.json")

    backend = create_backend(pci_dir / "index.mv2", config)
    stats = backend.get_stats()

    table = Table(title="PCI Index Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Index Path", str(stats["path"]))
    table.add_row("Exists", "Yes" if stats["exists"] else "No")

    # Cache statistics
    cache_path = pci_dir / "cache" / "file_hashes.json"
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
    index_path = pci_dir / "index.mv2"
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
    chunk_index_path = pci_dir / "chunk_index.json"
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
                    "[dim]Consider running 'pci index --clean' to rebuild fresh index.[/dim]"
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
        pci compact              # Compact if >20% stale
        pci compact --threshold 0.1  # Compact if >10% stale
        pci compact --force      # Force compaction now
    """
    from .indexer.chunk_index import ChunkIndex

    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized. Run 'pci init' first.[/red]")
        sys.exit(1)

    # Check if chunk index exists
    chunk_index_path = pci_dir / "chunk_index.json"
    if not chunk_index_path.exists():
        console.print("[yellow]Chunk index not found. Compaction requires chunk tracking.[/yellow]")
        console.print(
            "[dim]Run incremental indexing to build chunk index, or use --clean to rebuild.[/dim]"
        )
        sys.exit(1)

    # Load chunk index
    chunk_index = ChunkIndex(chunk_index_path)
    summary = chunk_index.get_staleness_summary()

    console.print(f"[cyan]Index Health Check[/cyan]")
    console.print(f"  Total chunks: {summary.total_chunks:,}")
    console.print(f"  Valid chunks: {summary.valid_chunks:,}")
    console.print(f"  Stale chunks: {summary.stale_chunks:,}")
    console.print(f"  Staleness: {summary.staleness_ratio:.1%}")
    console.print(f"  Status: {summary.status}\n")

    # Load config and backend
    config = Config.load(pci_dir / "config.json")
    backend = create_backend(pci_dir / "index.mv2", config)
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
                console.print(f"\n[green]✓ Compaction complete[/green]")
                console.print(f"  Files reindexed: {stats['files_reindexed']}")
                console.print(f"  Chunks stored: {stats['chunks_stored']}")
                console.print(
                    f"  Removed {stats['stale_chunks']:,} stale chunks "
                    f"({stats['staleness_ratio']:.1%} of total)"
                )

                if stats.get("metrics"):
                    m = stats["metrics"]
                    console.print(f"\n[dim]Performance:[/dim]")
                    console.print(f"  Duration: {m['duration_seconds']}s")
                    console.print(
                        f"  Throughput: {m['files_per_second']:.1f} files/s, "
                        f"{m['chunks_per_second']:.1f} chunks/s"
                    )

                if stats["errors"]:
                    console.print(f"\n[yellow]Warnings:[/yellow]")
                    for error in stats["errors"][:5]:
                        console.print(f"  {error}")
                    if len(stats["errors"]) > 5:
                        console.print(f"  ... and {len(stats['errors']) - 5} more")

        except Exception as e:
            console.print(f"[red]Error during compaction: {e}[/red]")
            sys.exit(1)


@main.group()
def config():
    """Manage PCI configuration."""
    pass


@config.command(name="show")
def config_show():
    """Display current configuration."""
    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized. Run 'pci init' first.[/red]")
        sys.exit(1)

    config_path = pci_dir / "config.json"
    cfg = Config.load(config_path)

    console.print("[bold cyan]PCI Configuration[/bold cyan]\n")
    console.print(cfg.model_dump_json(indent=2))
    console.print(f"\n[dim]Config file: {config_path}[/dim]")


@config.command(name="path")
def config_path():
    """Show configuration file path."""
    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized. Run 'pci init' first.[/red]")
        sys.exit(1)

    config_path = pci_dir / "config.json"
    console.print(str(config_path.absolute()))


@config.command(name="edit")
def config_edit():
    """Open configuration in $EDITOR."""
    import os
    import subprocess

    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized. Run 'pci init' first.[/red]")
        sys.exit(1)

    config_path = pci_dir / "config.json"

    editor = os.environ.get("EDITOR", "nano")
    try:
        subprocess.run([editor, str(config_path)], check=True)
        console.print(f"[green]✓[/green] Configuration updated")

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
