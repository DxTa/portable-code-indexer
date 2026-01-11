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
def index(path: str, update: bool):
    """Index codebase for search."""
    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized. Run 'pci init' first.[/red]")
        sys.exit(1)

    # Load config
    config = Config.load(pci_dir / "config.json")

    # Open backend
    backend = MemvidBackend(pci_dir / "index.mv2")
    backend.open_index()

    # Create coordinator
    coordinator = IndexingCoordinator(config, backend)

    # Index directory
    directory = Path(path).resolve()
    console.print(f"[cyan]Indexing {directory}...[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Discovering files...", total=None)
        
        try:
            stats = coordinator.index_directory(directory)
            progress.update(task, completed=True)
            
            console.print(f"\n[green]✓ Indexing complete[/green]")
            console.print(f"  Files indexed: {stats['indexed_files']}/{stats['total_files']}")
            console.print(f"  Total chunks: {stats['total_chunks']}")
            
            if stats['errors']:
                console.print(f"\n[yellow]Warnings:[/yellow]")
                for error in stats['errors'][:5]:  # Show first 5 errors
                    console.print(f"  {error}")
                if len(stats['errors']) > 5:
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
def research(question: str):
    """Multi-hop code research."""
    console.print("[yellow]Research feature not yet implemented[/yellow]")
    console.print("[dim]Coming soon: Multi-hop semantic search[/dim]")


@main.command()
def status():
    """Show index statistics."""
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

    console.print(table)


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
