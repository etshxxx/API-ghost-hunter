import os
import sys
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .fetcher import Fetcher
from .parser import OpenAPIParser, JSParser
from .snapshot import SnapshotManager
from .differ import Differ
from .analyzer import Analyzer
from .archiver import Archiver
from .reporter import Reporter
from .models import Snapshot
from .utils import (
    setup_logger,
    normalize_url,
    parse_headers,
    format_timestamp,
    format_archive_timestamp,
)

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version="2.0.0", prog_name="API Ghost Hunter")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--timeout", "-t", default=15, help="Request timeout in seconds")
@click.option("--no-verify-ssl", is_flag=True, help="Disable SSL verification")
@click.option("--proxy", default=None, help="HTTP/HTTPS proxy URL")
@click.pass_context
def cli(ctx, verbose, timeout, no_verify_ssl, proxy):
    """API Ghost Hunter - Discover, diff, and hunt ghost API endpoints."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["timeout"] = timeout
    ctx.obj["verify_ssl"] = not no_verify_ssl
    ctx.obj["proxy"] = proxy
    setup_logger(verbose)


@cli.command()
@click.argument("target")
@click.option("--spec-url", "-s", help="Direct URL to OpenAPI/Swagger spec")
@click.option("--scan-js", is_flag=True, help="Also scan JavaScript files for endpoints")
@click.option("--output-dir", "-o", default="snapshots", help="Directory to save snapshots")
@click.option("--headers", default=None, help="Custom headers (JSON string or file path)")
@click.pass_context
def scan(ctx, target, spec_url, scan_js, output_dir, headers):
    """Scan a target and create an endpoint snapshot."""
    custom_headers = parse_headers(headers) if headers else None

    fetcher = Fetcher(
        timeout=ctx.obj["timeout"],
        verify_ssl=ctx.obj["verify_ssl"],
        proxy=ctx.obj["proxy"],
        headers=custom_headers,
    )

    spec_data = None
    spec_url_found = ""

    if spec_url:
        console.print(f"[cyan]Fetching spec from {spec_url}...[/cyan]")
        spec = fetcher.fetch_spec(spec_url)
        if spec:
            spec_data = spec
            spec_url_found = spec_url
        else:
            console.print("[red]Failed to fetch spec from provided URL.[/red]")
            sys.exit(1)
    else:
        console.print(f"[cyan]Discovering API spec for {target}...[/cyan]")
        result = fetcher.discover_spec(target)
        if result:
            spec_data = result["spec"]
            spec_url_found = result["url"]
        else:
            console.print("[red]No API spec found. Try providing --spec-url manually.[/red]")
            sys.exit(1)

    endpoints = OpenAPIParser.parse(spec_data, spec_url_found)
    spec_version = OpenAPIParser.get_spec_version(spec_data)

    if scan_js:
        console.print("[cyan]Scanning JavaScript files for additional endpoints...[/cyan]")
        js_files = fetcher.fetch_js_files(target)
        for js_file in js_files:
            js_endpoints = JSParser.parse(js_file["content"], js_file["url"])
            existing_keys = {ep.key for ep in endpoints}
            for ep in js_endpoints:
                if ep.key not in existing_keys:
                    endpoints.append(ep)
                    existing_keys.add(ep.key)
        console.print(f"[green]Total endpoints: {len(endpoints)}[/green]")

    snapshot = Snapshot(
        target_url=normalize_url(target),
        timestamp=datetime.now().isoformat(),
        endpoints=endpoints,
        spec_url=spec_url_found,
        spec_version=spec_version,
        source="openapi" + ("+js" if scan_js else ""),
    )

    manager = SnapshotManager(output_dir)
    filepath = manager.save(snapshot)

    console.print()
    console.print(
        Panel.fit(
            f"[green]Snapshot saved![/green]\n"
            f"Target: {snapshot.target_url}\n"
            f"Endpoints: {len(endpoints)}\n"
            f"Spec: {spec_url_found}\n"
            f"Version: {spec_version}\n"
            f"File: {filepath}",
            border_style="green",
        )
    )


@cli.command(name="list")
@click.option("--snapshot-dir", "-d", default="snapshots", help="Snapshot directory")
@click.option("--target", "-t", help="Filter by target URL")
def list_cmd(snapshot_dir, target):
    """List all saved snapshots."""
    manager = SnapshotManager(snapshot_dir)
    snapshots = manager.list_snapshots(target)

    if not snapshots:
        console.print("[yellow]No snapshots found.[/yellow]")
        return

    table = Table(
        title="Saved Snapshots", show_header=True, header_style="bold magenta"
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Target")
    table.add_column("Timestamp")
    table.add_column("EPs", justify="right")
    table.add_column("Spec URL")
    table.add_column("Source")
    table.add_column("File")

    for i, s in enumerate(snapshots, 1):
        spec_display = s["spec_url"][:40] + "..." if len(s["spec_url"]) > 40 else s["spec_url"]
        ts_display = format_timestamp(s["timestamp"])
        if s.get("archive_timestamp"):
            ts_display += f" [dim](archive: {format_archive_timestamp(s['archive_timestamp'])})[/dim]"
        table.add_row(
            str(i),
            s["target_url"],
            ts_display,
            str(s["endpoint_count"]),
            spec_display,
            s["source"],
            s["filename"],
        )

    console.print(table)


@cli.command()
@click.argument("old_snapshot")
@click.argument("new_snapshot")
@click.option(
    "--format", "-f", "report_format",
    type=click.Choice(["console", "json", "html", "markdown", "all"]),
    default="console", help="Output format",
)
@click.option("--output", "-o", help="Output file path (for json/html/markdown)")
@click.option("--probe", is_flag=True, help="Probe removed endpoints to find ghosts")
@click.option("--auth-header", default=None, help="Auth header for probing (e.g. 'Authorization: Bearer token')")
@click.option("--delay", default=0.5, help="Delay between probes in seconds")
@click.pass_context
def diff(ctx, old_snapshot, new_snapshot, report_format, output, probe, auth_header, delay):
    """Compare two snapshots and show differences."""
    manager = SnapshotManager()

    old_snap = manager.load(old_snapshot)
    new_snap = manager.load(new_snapshot)

    if old_snap is None:
        console.print(f"[red]Cannot load old snapshot: {old_snapshot}[/red]")
        sys.exit(1)
    if new_snap is None:
        console.print(f"[red]Cannot load new snapshot: {new_snapshot}[/red]")
        sys.exit(1)

    result = Differ.compare(old_snap, new_snap)

    ghosts = None
    if probe and result.removed:
        console.print(
            f"[cyan]Probing {len(result.removed)} removed endpoints for ghosts...[/cyan]"
        )
        analyzer = Analyzer(
            timeout=ctx.obj["timeout"],
            verify_ssl=ctx.obj["verify_ssl"],
            proxy=ctx.obj["proxy"],
            auth_header=auth_header,
            delay=delay,
        )
        ghosts = analyzer.find_ghosts(new_snap.target_url, result.removed)

    if report_format == "console":
        Reporter.console_summary(result)
        if ghosts:
            Reporter.console_ghosts(ghosts)
    elif report_format == "json":
        out = output or "diff_report.json"
        Reporter.generate_json(result, ghosts, out)
        console.print(f"[green]JSON report saved to {out}[/green]")
    elif report_format == "html":
        out = output or "diff_report.html"
        Reporter.generate_html(result, ghosts, out)
        console.print(f"[green]HTML report saved to {out}[/green]")
    elif report_format == "markdown":
        out = output or "diff_report.md"
        Reporter.generate_markdown(result, ghosts, out)
        console.print(f"[green]Markdown report saved to {out}[/green]")
    elif report_format == "all":
        base = output or "diff_report"
        Reporter.generate_json(result, ghosts, f"{base}.json")
        Reporter.generate_html(result, ghosts, f"{base}.html")
        Reporter.generate_markdown(result, ghosts, f"{base}.md")
        Reporter.console_summary(result)
        if ghosts:
            Reporter.console_ghosts(ghosts)
        console.print(f"[green]Reports saved: {base}.json, {base}.html, {base}.md[/green]")


@cli.command()
@click.argument("target")
@click.option("--snapshot-dir", "-d", default="snapshots", help="Snapshot directory")
@click.option("--spec-url", "-s", help="Direct URL to OpenAPI/Swagger spec")
@click.option("--scan-js", is_flag=True, help="Also scan JavaScript files")
@click.option(
    "--report-format", "-f",
    type=click.Choice(["console", "json", "html", "markdown", "all"]),
    default="console", help="Report format",
)
@click.option("--output", "-o", help="Output file path for report")
@click.option("--probe", is_flag=True, help="Probe removed endpoints to find ghosts")
@click.option("--check-archives", is_flag=True, help="Also check Wayback Machine for old API specs")
@click.option("--auth-header", default=None, help="Auth header for probing (e.g. 'Authorization: Bearer token')")
@click.option("--headers", default=None, help="Custom headers (JSON string or file path)")
@click.option("--delay", default=0.5, help="Delay between probes in seconds")
@click.pass_context
def hunt(ctx, target, snapshot_dir, spec_url, scan_js, report_format, output, probe,
         check_archives, auth_header, headers, delay):
    """Full hunt: scan, diff with previous snapshot, and optionally probe ghosts."""
    target = normalize_url(target)
    custom_headers = parse_headers(headers) if headers else None

    fetcher = Fetcher(
        timeout=ctx.obj["timeout"],
        verify_ssl=ctx.obj["verify_ssl"],
        proxy=ctx.obj["proxy"],
        headers=custom_headers,
    )

    manager = SnapshotManager(snapshot_dir)
    previous = manager.get_latest(target)

    if previous:
        console.print(
            f"[cyan]Found previous snapshot from {format_timestamp(previous.timestamp)}[/cyan]"
        )

    console.print(f"[cyan]Scanning {target}...[/cyan]")

    if spec_url:
        spec = fetcher.fetch_spec(spec_url)
        if not spec:
            console.print("[red]Failed to fetch spec.[/red]")
            sys.exit(1)
        spec_data = spec
        spec_url_found = spec_url
    else:
        result = fetcher.discover_spec(target)
        if not result:
            console.print("[red]No API spec found.[/red]")
            sys.exit(1)
        spec_data = result["spec"]
        spec_url_found = result["url"]

    endpoints = OpenAPIParser.parse(spec_data, spec_url_found)
    spec_version = OpenAPIParser.get_spec_version(spec_data)

    if scan_js:
        js_files = fetcher.fetch_js_files(target)
        for js_file in js_files:
            js_endpoints = JSParser.parse(js_file["content"], js_file["url"])
            existing_keys = {ep.key for ep in endpoints}
            for ep in js_endpoints:
                if ep.key not in existing_keys:
                    endpoints.append(ep)
                    existing_keys.add(ep.key)

    current_snapshot = Snapshot(
        target_url=target,
        timestamp=datetime.now().isoformat(),
        endpoints=endpoints,
        spec_url=spec_url_found,
        spec_version=spec_version,
        source="openapi" + ("+js" if scan_js else ""),
    )

    filepath = manager.save(current_snapshot)
    console.print(f"[green]Current snapshot saved: {filepath}[/green]")

    archive_snapshots = []
    if check_archives:
        console.print()
        console.print("[cyan]Checking Wayback Machine for archived API specs...[/cyan]")
        archiver = Archiver(
            timeout=ctx.obj["timeout"],
            verify_ssl=ctx.obj["verify_ssl"],
            delay=1.0,
        )
        archived_specs = archiver.fetch_all_archived_specs(
            target, spec_url=spec_url_found
        )

        valid_archives = [a for a in archived_specs if a.spec_data is not None]

        if valid_archives:
            console.print(
                f"[green]Found {len(valid_archives)} valid archived specs![/green]"
            )
            for archived in valid_archives:
                arch_endpoints = OpenAPIParser.parse(
                    archived.spec_data, archived.original_url
                )
                arch_version = OpenAPIParser.get_spec_version(archived.spec_data)

                arch_snapshot = Snapshot(
                    target_url=target,
                    timestamp=datetime.now().isoformat(),
                    endpoints=arch_endpoints,
                    spec_url=archived.original_url,
                    spec_version=arch_version,
                    source="wayback",
                    archive_timestamp=archived.timestamp,
                )
                arch_filepath = manager.save(arch_snapshot)
                console.print(
                    f"  [green]Saved archive snapshot: "
                    f"{format_archive_timestamp(archived.timestamp)} "
                    f"({len(arch_endpoints)} endpoints) -> {arch_filepath}[/green]"
                )
                archive_snapshots.append(arch_snapshot)

            if not previous and archive_snapshots:
                previous = archive_snapshots[0]
                console.print(
                    f"[cyan]Using oldest archive as previous snapshot: "
                    f"{format_archive_timestamp(previous.archive_timestamp)}[/cyan]"
                )
        else:
            console.print("[yellow]No valid archived specs found on Wayback Machine.[/yellow]")
        console.print()

    if not previous:
        console.print(
            "[yellow]No previous snapshot found. This is the first scan.[/yellow]"
        )
        console.print(
            f"[green]Saved {len(endpoints)} endpoints. Run again later to compare.[/green]"
        )
        return

    console.print("[cyan]Comparing with previous snapshot...[/cyan]")
    diff_result = Differ.compare(previous, current_snapshot)

    ghosts = None
    if probe and diff_result.removed:
        console.print(
            f"[cyan]Probing {len(diff_result.removed)} removed endpoints for ghosts...[/cyan]"
        )
        analyzer = Analyzer(
            timeout=ctx.obj["timeout"],
            verify_ssl=ctx.obj["verify_ssl"],
            proxy=ctx.obj["proxy"],
            auth_header=auth_header,
            delay=delay,
        )
        ghosts = analyzer.find_ghosts(target, diff_result.removed)

    if report_format == "console":
        Reporter.console_summary(diff_result)
        if ghosts:
            Reporter.console_ghosts(ghosts)
    elif report_format == "json":
        out = output or "hunt_report.json"
        Reporter.generate_json(diff_result, ghosts, out)
        console.print(f"[green]Report saved to {out}[/green]")
    elif report_format == "html":
        out = output or "hunt_report.html"
        Reporter.generate_html(diff_result, ghosts, out)
        console.print(f"[green]Report saved to {out}[/green]")
    elif report_format == "markdown":
        out = output or "hunt_report.md"
        Reporter.generate_markdown(diff_result, ghosts, out)
        console.print(f"[green]Report saved to {out}[/green]")
    elif report_format == "all":
        base = output or "hunt_report"
        Reporter.generate_json(diff_result, ghosts, f"{base}.json")
        Reporter.generate_html(diff_result, ghosts, f"{base}.html")
        Reporter.generate_markdown(diff_result, ghosts, f"{base}.md")
        Reporter.console_summary(diff_result)
        if ghosts:
            Reporter.console_ghosts(ghosts)
        console.print(
            f"[green]Reports saved: {base}.json, {base}.html, {base}.md[/green]"
        )


@cli.command()
@click.argument("target")
@click.option("--snapshot-dir", "-d", default="snapshots", help="Snapshot directory")
@click.option(
    "--report-format", "-f",
    type=click.Choice(["console", "json", "html", "markdown", "all"]),
    default="console", help="Report format",
)
@click.option("--output", "-o", help="Output file path for report")
@click.option("--auth-header", default=None, help="Auth header for probing (e.g. 'Authorization: Bearer token')")
@click.option("--delay", default=0.5, help="Delay between probes in seconds")
@click.pass_context
def ghosts(ctx, target, snapshot_dir, report_format, output, auth_header, delay):
    """Find and probe ghost endpoints (removed but still alive)."""
    target = normalize_url(target)
    manager = SnapshotManager(snapshot_dir)

    snapshots = manager.list_snapshots(target)
    if len(snapshots) < 2:
        console.print(
            "[red]Need at least 2 snapshots to find ghosts. Run 'scan' first.[/red]"
        )
        sys.exit(1)

    snapshots.sort(key=lambda x: x["timestamp"], reverse=True)
    new_snap = manager.load(snapshots[0]["filepath"])
    old_snap = manager.load(snapshots[1]["filepath"])

    console.print(f"[cyan]Comparing snapshots:[/cyan]")
    console.print(
        f"  Old: {format_timestamp(old_snap.timestamp)} ({len(old_snap.endpoints)} endpoints)"
    )
    if old_snap.archive_timestamp:
        console.print(
            f"       [dim]Archived: {format_archive_timestamp(old_snap.archive_timestamp)}[/dim]"
        )
    console.print(
        f"  New: {format_timestamp(new_snap.timestamp)} ({len(new_snap.endpoints)} endpoints)"
    )

    diff_result = Differ.compare(old_snap, new_snap)

    if not diff_result.removed:
        console.print("[green]No removed endpoints found. No ghosts to hunt.[/green]")
        return

    console.print(
        f"[cyan]Found {len(diff_result.removed)} removed endpoints. "
        f"Probing for ghosts...[/cyan]"
    )

    analyzer = Analyzer(
        timeout=ctx.obj["timeout"],
        verify_ssl=ctx.obj["verify_ssl"],
        proxy=ctx.obj["proxy"],
        auth_header=auth_header,
        delay=delay,
    )

    ghost_results = analyzer.find_ghosts(target, diff_result.removed)

    if report_format == "console":
        Reporter.console_ghosts(ghost_results)
    elif report_format == "json":
        out = output or "ghost_report.json"
        Reporter.generate_json(diff_result, ghost_results, out)
        console.print(f"[green]Report saved to {out}[/green]")
    elif report_format == "html":
        out = output or "ghost_report.html"
        Reporter.generate_html(diff_result, ghost_results, out)
        console.print(f"[green]Report saved to {out}[/green]")
    elif report_format == "markdown":
        out = output or "ghost_report.md"
        Reporter.generate_markdown(diff_result, ghost_results, out)
        console.print(f"[green]Report saved to {out}[/green]")
    elif report_format == "all":
        base = output or "ghost_report"
        Reporter.generate_json(diff_result, ghost_results, f"{base}.json")
        Reporter.generate_html(diff_result, ghost_results, f"{base}.html")
        Reporter.generate_markdown(diff_result, ghost_results, f"{base}.md")
        Reporter.console_ghosts(ghost_results)
        console.print(
            f"[green]Reports saved: {base}.json, {base}.html, {base}.md[/green]"
        )


@cli.command()
@click.argument("target")
@click.option("--spec-url", "-s", help="Direct URL to OpenAPI/Swagger spec (uses this URL for archive search)")
@click.option("--output-dir", "-o", default="snapshots", help="Directory to save snapshots")
@click.option("--from-date", default=None, help="Start date for Wayback Machine (YYYYMMDD)")
@click.option("--to-date", default=None, help="End date for Wayback Machine (YYYYMMDD)")
@click.option("--limit", default=50, help="Max archived versions to fetch per URL")
@click.pass_context
def archive(ctx, target, spec_url, output_dir, from_date, to_date, limit):
    """Search the Wayback Machine for archived API specs and save snapshots."""
    target = normalize_url(target)
    fetcher = Fetcher(
        timeout=ctx.obj["timeout"],
        verify_ssl=ctx.obj["verify_ssl"],
        proxy=ctx.obj["proxy"],
    )

    discovered_spec_url = spec_url
    if not discovered_spec_url:
        console.print(f"[cyan]Discovering current API spec for {target}...[/cyan]")
        result = fetcher.discover_spec(target)
        if result:
            discovered_spec_url = result["url"]
            console.print(f"[green]Found API spec at {discovered_spec_url}[/green]")
        else:
            console.print(
                "[yellow]No current API spec found. "
                "Will search Wayback Machine for common spec paths.[/yellow]"
            )

    console.print()
    console.print("[cyan]Querying Wayback Machine for archived API specs...[/cyan]")

    archiver = Archiver(
        timeout=ctx.obj["timeout"],
        verify_ssl=ctx.obj["verify_ssl"],
        delay=1.0,
    )

    archived_specs = archiver.fetch_all_archived_specs(
        target,
        spec_url=discovered_spec_url,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )

    if not archived_specs:
        console.print("[yellow]No archived specs found on Wayback Machine.[/yellow]")
        return

    console.print()
    table = Table(
        title="Archived Specs Found",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Archive Date")
    table.add_column("Original URL")
    table.add_column("Status")
    table.add_column("Endpoints")
    table.add_column("Version")

    valid_archives = []
    for i, a in enumerate(archived_specs, 1):
        if a.spec_data is not None:
            valid_archives.append(a)
            status = "[green]Valid[/green]"
            ep_count = str(a.endpoints_count)
        else:
            status = "[red]Failed[/red]"
            ep_count = "-"

        url_display = a.original_url[:50] + "..." if len(a.original_url) > 50 else a.original_url
        table.add_row(
            str(i),
            a.formatted_date,
            url_display,
            status,
            ep_count,
            a.spec_version,
        )

    console.print(table)

    if not valid_archives:
        console.print("[red]No valid archived specs could be parsed.[/red]")
        return

    console.print()
    console.print(f"[cyan]Creating snapshots from {len(valid_archives)} valid archives...[/cyan]")

    manager = SnapshotManager(output_dir)

    for a in valid_archives:
        endpoints = OpenAPIParser.parse(a.spec_data, a.original_url)
        a.endpoints_count = len(endpoints)

        snapshot = Snapshot(
            target_url=target,
            timestamp=datetime.now().isoformat(),
            endpoints=endpoints,
            spec_url=a.original_url,
            spec_version=a.spec_version,
            source="wayback",
            archive_timestamp=a.timestamp,
        )
        filepath = manager.save(snapshot)
        console.print(
            f"  [green]Saved: {format_archive_timestamp(a.timestamp)} "
            f"({len(endpoints)} endpoints) -> {filepath}[/green]"
        )

    console.print()
    console.print(
        Panel.fit(
            f"[green]Archive scan complete![/green]\n"
            f"Target: {target}\n"
            f"Archived specs found: {len(archived_specs)}\n"
            f"Valid specs parsed: {len(valid_archives)}\n"
            f"Snapshots saved to: {output_dir}/\n\n"
            f"[cyan]Next steps:[/cyan]\n"
            f"  1. Run [bold]api-ghost-hunter scan {target}[/bold] to create a current snapshot\n"
            f"  2. Run [bold]api-ghost-hunter diff <old> <new> --probe[/bold] to find ghosts\n"
            f"  3. Or run [bold]api-ghost-hunter hunt {target} --probe --check-archives[/bold]",
            border_style="green",
        )
    )


def main():
    cli()


if __name__ == "__main__":
    main()
