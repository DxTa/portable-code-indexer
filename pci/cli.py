"""CLI entry point for PCI."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .config import Config
from .indexer.coordinator import IndexingCoordinator
from .storage.backend import MemvidBackend

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main():
    """PCI - Portable Code Index

    Local-first codebase intelligence with semantic search.
    """
    pass


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

    # Create empty index
    backend = MemvidBackend(pci_dir / "index.mv2")
    backend.create_index()

    console.print(f"[green]✓[/green] Initialized PCI at {pci_dir}")
    console.print(f"[dim]Next: pci index [path][/dim]")


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--update", is_flag=True, help="Re-index changed files only")
@click.option(
    "--clean", is_flag=True, help="Delete existing index and cache, then rebuild from scratch"
)
def index(path: str, update: bool, clean: bool):
    """Index codebase for search."""
    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized. Run 'pci init' first.[/red]")
        sys.exit(1)

    # Load config
    config = Config.load(pci_dir / "config.json")

    # Handle --clean flag
    backend = MemvidBackend(pci_dir / "index.mv2")
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
                # Incremental indexing with hash cache
                from .indexer.hash_cache import HashCache

                cache = HashCache(pci_dir / "cache" / "file_hashes.json")
                stats = coordinator.index_directory_incremental(directory, cache)

                console.print(f"\n[green]✓ Incremental indexing complete[/green]")
                console.print(f"  Changed files: {stats['changed_files']}")
                console.print(f"  Skipped files: {stats['skipped_files']}")
                console.print(f"  Indexed files: {stats['indexed_files']}/{stats['total_files']}")
                console.print(f"  Total chunks: {stats['total_chunks']}")
            else:
                # Full indexing
                stats = coordinator.index_directory(directory)
                progress.update(task, completed=True)

                console.print(f"\n[green]✓ Indexing complete[/green]")
                console.print(f"  Files indexed: {stats['indexed_files']}/{stats['total_files']}")
                console.print(f"  Total chunks: {stats['total_chunks']}")

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
def search(query: str, regex: bool, limit: int):
    """Search the codebase."""
    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized. Run 'pci init' first.[/red]")
        sys.exit(1)

    backend = MemvidBackend(pci_dir / "index.mv2")
    backend.open_index()

    mode = "lexical" if regex else "semantic"
    console.print(f"[dim]Searching ({mode})...[/dim]")

    if regex:
        results = backend.search_lexical(query, k=limit)
    else:
        results = backend.search_semantic(query, k=limit)

    if not results:
        console.print("[yellow]No results found[/yellow]")
        return

    # Display results
    for i, result in enumerate(results, 1):
        chunk = result.chunk
        console.print(f"\n[bold cyan]{i}. {chunk.symbol}[/bold cyan]")
        console.print(f"[dim]{chunk.file_path}:{chunk.start_line}-{chunk.end_line}[/dim]")
        console.print(f"Score: {result.score:.3f}")
        if result.snippet:
            console.print(f"\n{result.snippet}\n")


@main.command()
@click.argument("question")
@click.option("--hops", type=int, default=2, help="Maximum relationship hops")
@click.option("--graph", is_flag=True, help="Show call graph")
@click.option("-k", "--limit", type=int, default=5, help="Results per hop")
def research(question: str, hops: int, graph: bool, limit: int):
    """Multi-hop code research for architectural questions.

    Automatically discovers code relationships and builds a complete picture.

    Examples:
        pci research "How does authentication work?"
        pci research "What calls the indexer?" --graph
        pci research "How is configuration loaded?" --hops 3
    """
    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized. Run 'pci init' first.[/red]")
        sys.exit(1)

    from .search.multi_hop import MultiHopSearchStrategy

    backend = MemvidBackend(pci_dir / "index.mv2")
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
    """Show index statistics."""
    import datetime
    import json

    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized[/red]")
        sys.exit(1)

    backend = MemvidBackend(pci_dir / "index.mv2")
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

    console.print(table)

    # Staleness warning
    if index_path.exists():
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
@click.option("--show", is_flag=True, help="Show current configuration")
def config(show: bool):
    """Manage configuration."""
    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized[/red]")
        sys.exit(1)

    config_path = pci_dir / "config.json"
    cfg = Config.load(config_path)

    if show:
        console.print(cfg.model_dump_json(indent=2))
    else:
        console.print(f"Config path: {config_path}")
        console.print("Use --show to display configuration")


if __name__ == "__main__":
    main()
