import json
import html as html_lib
from datetime import datetime
from typing import List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .models import DiffResult, GhostEndpoint
from .utils import format_timestamp, format_archive_timestamp

console = Console()


class Reporter:
    @staticmethod
    def console_summary(diff_result: DiffResult):
        console.print()

        old_archive = ""
        if diff_result.old_snapshot.archive_timestamp:
            old_archive = (
                f"\n[dim]Archived: "
                f"{format_archive_timestamp(diff_result.old_snapshot.archive_timestamp)}[/dim]"
            )

        new_archive = ""
        if diff_result.new_snapshot.archive_timestamp:
            new_archive = (
                f"\n[dim]Archived: "
                f"{format_archive_timestamp(diff_result.new_snapshot.archive_timestamp)}[/dim]"
            )

        console.print(
            Panel.fit(
                f"[bold cyan]API Ghost Hunter - Diff Report[/bold cyan]\n"
                f"Old: {diff_result.old_snapshot.target_url} "
                f"({format_timestamp(diff_result.old_snapshot.timestamp)})"
                f"{old_archive}\n"
                f"New: {diff_result.new_snapshot.target_url} "
                f"({format_timestamp(diff_result.new_snapshot.timestamp)})"
                f"{new_archive}",
                border_style="cyan",
            )
        )

        summary_table = Table(
            title="Summary", show_header=True, header_style="bold magenta"
        )
        summary_table.add_column("Category", style="dim")
        summary_table.add_column("Count", justify="right")
        summary_table.add_row("[green]Added[/green]", str(len(diff_result.added)))
        summary_table.add_row(
            "[red]Removed[/red]", str(len(diff_result.removed))
        )
        summary_table.add_row(
            "[yellow]Modified[/yellow]", str(len(diff_result.modified))
        )
        summary_table.add_row(
            "[dim]Unchanged[/dim]", str(len(diff_result.unchanged))
        )
        console.print(summary_table)

        if diff_result.added:
            table = Table(
                title="[green]Added Endpoints (New)[/green]",
                show_header=True,
                header_style="bold green",
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("Method", style="bold")
            table.add_column("Path")
            table.add_column("Auth", justify="center")
            table.add_column("Deprecated", justify="center")
            for i, ep in enumerate(diff_result.added, 1):
                auth = "[green]Yes[/green]" if ep.requires_auth else "[red]No[/red]"
                dep = "[yellow]Yes[/yellow]" if ep.deprecated else "No"
                table.add_row(str(i), ep.method, ep.path, auth, dep)
            console.print(table)

        if diff_result.removed:
            table = Table(
                title="[red]Removed Endpoints (Potential Ghosts)[/red]",
                show_header=True,
                header_style="bold red",
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("Method", style="bold")
            table.add_column("Path")
            table.add_column("Auth", justify="center")
            table.add_column("Summary")
            for i, ep in enumerate(diff_result.removed, 1):
                auth = "[green]Yes[/green]" if ep.requires_auth else "[red]No[/red]"
                summary = ep.summary[:50] if ep.summary else ""
                table.add_row(str(i), ep.method, ep.path, auth, summary)
            console.print(table)

        if diff_result.modified:
            table = Table(
                title="[yellow]Modified Endpoints[/yellow]",
                show_header=True,
                header_style="bold yellow",
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("Endpoint")
            table.add_column("Changes")
            for i, mod in enumerate(diff_result.modified, 1):
                changes = ", ".join(mod["changes"].keys())
                table.add_row(str(i), mod["endpoint"], changes)
            console.print(table)

        console.print()

    @staticmethod
    def console_ghosts(ghosts: List[GhostEndpoint]):
        if not ghosts:
            console.print("[dim]No ghost endpoints found.[/dim]")
            return

        table = Table(
            title="[bold red]Ghost Endpoints (Still Alive!)[/bold red]",
            show_header=True,
            header_style="bold red",
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Method", style="bold")
        table.add_column("Path")
        table.add_column("Status", justify="center")
        table.add_column("Size", justify="right")
        table.add_column("Time", justify="right")
        table.add_column("Auth Bypass", justify="center")

        alive_count = 0
        bypass_count = 0

        for i, g in enumerate(ghosts, 1):
            if g.still_alive:
                alive_count += 1
                status = f"[green]{g.status_code}[/green]"
            else:
                status = f"[red]{g.status_code}[/red]"

            if g.auth_bypassed:
                bypass_count += 1
                bypass = "[bold yellow]YES![/bold yellow]"
            else:
                bypass = "[dim]No[/dim]"

            table.add_row(
                str(i),
                g.endpoint.method,
                g.endpoint.path,
                status,
                str(g.response_length),
                f"{g.response_time}s",
                bypass,
            )

        console.print(table)

        for g in ghosts:
            if g.still_alive and g.response_snippet:
                console.print()
                snippet_preview = (
                    g.response_snippet[:200].replace("\n", " ").strip()
                )
                console.print(
                    f"  [dim]Snippet for[/dim] [bold]{g.endpoint.method} "
                    f"{g.endpoint.path}[/bold]:"
                )
                console.print(f"  [dim]{snippet_preview}[/dim]")

        console.print()
        console.print(
            f"[bold]Summary:[/bold] {alive_count}/{len(ghosts)} ghost endpoints "
            f"still alive, {bypass_count} with auth bypass"
        )
        console.print()

    @staticmethod
    def generate_json(
        diff_result: DiffResult,
        ghosts: Optional[List[GhostEndpoint]] = None,
        filepath: str = "",
    ) -> str:
        data = {
            "generated_at": datetime.now().isoformat(),
            "diff": diff_result.to_dict(),
        }
        if ghosts:
            data["ghosts"] = [g.to_dict() for g in ghosts]

        json_str = json.dumps(data, indent=2)
        if filepath:
            with open(filepath, "w") as f:
                f.write(json_str)
        return json_str

    @staticmethod
    def generate_html(
        diff_result: DiffResult,
        ghosts: Optional[List[GhostEndpoint]] = None,
        filepath: str = "",
    ) -> str:
        html = Reporter._build_html(diff_result, ghosts)
        if filepath:
            with open(filepath, "w") as f:
                f.write(html)
        return html

    @staticmethod
    def _build_html(
        diff_result: DiffResult,
        ghosts: Optional[List[GhostEndpoint]] = None,
    ) -> str:
        def esc(text):
            return html_lib.escape(str(text)) if text else ""

        added_rows = ""
        for ep in diff_result.added:
            auth = "Yes" if ep.requires_auth else "No"
            added_rows += (
                f"<tr><td><span class='method {ep.method}'>{ep.method}</span></td>"
                f"<td>{esc(ep.path)}</td><td>{auth}</td></tr>"
            )

        removed_rows = ""
        for ep in diff_result.removed:
            auth = "Yes" if ep.requires_auth else "No"
            removed_rows += (
                f"<tr class='ghost'><td><span class='method {ep.method}'>"
                f"{ep.method}</span></td><td>{esc(ep.path)}</td><td>{auth}</td></tr>"
            )

        modified_rows = ""
        for mod in diff_result.modified:
            changes = ", ".join(mod["changes"].keys())
            modified_rows += (
                f"<tr><td>{esc(mod['endpoint'])}</td><td>{esc(changes)}</td></tr>"
            )

        ghost_rows = ""
        ghost_section = ""
        if ghosts:
            for g in ghosts:
                cls = "alive" if g.still_alive else "dead"
                bypass = "YES" if g.auth_bypassed else "No"
                snippet = esc(g.response_snippet[:200]) if g.response_snippet else ""
                ghost_rows += (
                    f"<tr class='{cls}'><td><span class='method "
                    f"{g.endpoint.method}'>{g.endpoint.method}</span></td>"
                    f"<td>{esc(g.endpoint.path)}</td><td>{g.status_code}</td>"
                    f"<td>{g.response_length}</td><td>{bypass}</td>"
                    f"<td class='snippet'>{snippet}</td></tr>"
                )
            ghost_section = f"""
            <h2>Ghost Endpoints</h2>
            <table>
                <tr><th>Method</th><th>Path</th><th>Status</th><th>Size</th><th>Auth Bypass</th><th>Response Snippet</th></tr>
                {ghost_rows}
            </table>"""

        added_section = ""
        if diff_result.added:
            added_section = (
                "<h2>Added Endpoints</h2><table><tr><th>Method</th>"
                "<th>Path</th><th>Auth Required</th></tr>" + added_rows + "</table>"
            )

        removed_section = ""
        if diff_result.removed:
            removed_section = (
                "<h2>Removed Endpoints (Potential Ghosts)</h2><table><tr>"
                "<th>Method</th><th>Path</th><th>Auth Required</th></tr>"
                + removed_rows + "</table>"
            )

        modified_section = ""
        if diff_result.modified:
            modified_section = (
                "<h2>Modified Endpoints</h2><table><tr><th>Endpoint</th>"
                "<th>Changes</th></tr>" + modified_rows + "</table>"
            )

        old_archive_info = ""
        if diff_result.old_snapshot.archive_timestamp:
            old_archive_info = (
                f" | <strong>Archived:</strong> "
                f"{esc(format_archive_timestamp(diff_result.old_snapshot.archive_timestamp))}"
            )

        new_archive_info = ""
        if diff_result.new_snapshot.archive_timestamp:
            new_archive_info = (
                f" | <strong>Archived:</strong> "
                f"{esc(format_archive_timestamp(diff_result.new_snapshot.archive_timestamp))}"
            )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Ghost Hunter Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
               margin: 40px; background: #0d1117; color: #c9d1d9; }}
        h1 {{ color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 10px; }}
        h2 {{ color: #f0c674; margin-top: 30px; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }}
        .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                 padding: 20px; flex: 1; min-width: 120px; text-align: center; }}
        .card h3 {{ margin: 0 0 10px 0; font-size: 14px; color: #8b949e; }}
        .card .number {{ font-size: 32px; font-weight: bold; }}
        .card.added .number {{ color: #3fb950; }}
        .card.removed .number {{ color: #f85149; }}
        .card.modified .number {{ color: #f0c674; }}
        .card.unchanged .number {{ color: #8b949e; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0 30px 0; }}
        th {{ background: #161b22; text-align: left; padding: 10px;
             border-bottom: 2px solid #30363d; color: #58a6ff; }}
        td {{ padding: 10px; border-bottom: 1px solid #21262d; }}
        tr:hover {{ background: #161b22; }}
        tr.ghost {{ background: rgba(248,81,73,0.1); }}
        tr.alive {{ background: rgba(63,185,80,0.1); }}
        tr.dead {{ opacity: 0.5; }}
        .method {{ padding: 4px 10px; border-radius: 4px; font-weight: bold;
                   font-size: 12px; }}
        .method.GET {{ background: #1a7f37; color: white; }}
        .method.POST {{ background: #fb8500; color: white; }}
        .method.PUT {{ background: #0a369d; color: white; }}
        .method.DELETE {{ background: #cf222e; color: white; }}
        .method.PATCH {{ background: #8250df; color: white; }}
        .method.HEAD {{ background: #6e7681; color: white; }}
        .method.OPTIONS {{ background: #6e7681; color: white; }}
        .snippet {{ max-width: 400px; overflow: hidden; text-overflow: ellipsis;
                    white-space: nowrap; font-family: monospace; font-size: 11px;
                    color: #8b949e; }}
        .footer {{ margin-top: 40px; color: #484f58; font-size: 12px;
                   text-align: center; }}
    </style>
</head>
<body>
    <h1>API Ghost Hunter - Diff Report</h1>
    <p><strong>Old Target:</strong> {esc(diff_result.old_snapshot.target_url)}
       | <strong>Timestamp:</strong> {esc(format_timestamp(diff_result.old_snapshot.timestamp))}
       {old_archive_info}</p>
    <p><strong>New Target:</strong> {esc(diff_result.new_snapshot.target_url)}
       | <strong>Timestamp:</strong> {esc(format_timestamp(diff_result.new_snapshot.timestamp))}
       {new_archive_info}</p>
    <div class="summary">
        <div class="card added"><h3>Added</h3><div class="number">{len(diff_result.added)}</div></div>
        <div class="card removed"><h3>Removed</h3><div class="number">{len(diff_result.removed)}</div></div>
        <div class="card modified"><h3>Modified</h3><div class="number">{len(diff_result.modified)}</div></div>
        <div class="card unchanged"><h3>Unchanged</h3><div class="number">{len(diff_result.unchanged)}</div></div>
    </div>
    {added_section}
    {removed_section}
    {modified_section}
    {ghost_section}
    <div class="footer">Generated by API Ghost Hunter</div>
</body>
</html>"""

    @staticmethod
    def generate_markdown(
        diff_result: DiffResult,
        ghosts: Optional[List[GhostEndpoint]] = None,
        filepath: str = "",
    ) -> str:
        lines = []
        lines.append("# API Ghost Hunter - Diff Report\n")
        old_archive = ""
        if diff_result.old_snapshot.archive_timestamp:
            old_archive = (
                f" | **Archived:** "
                f"{format_archive_timestamp(diff_result.old_snapshot.archive_timestamp)}"
            )
        new_archive = ""
        if diff_result.new_snapshot.archive_timestamp:
            new_archive = (
                f" | **Archived:** "
                f"{format_archive_timestamp(diff_result.new_snapshot.archive_timestamp)}"
            )
        lines.append(
            f"**Old Target:** {diff_result.old_snapshot.target_url} | "
            f"**Timestamp:** {format_timestamp(diff_result.old_snapshot.timestamp)}"
            f"{old_archive}\n"
        )
        lines.append(
            f"**New Target:** {diff_result.new_snapshot.target_url} | "
            f"**Timestamp:** {format_timestamp(diff_result.new_snapshot.timestamp)}"
            f"{new_archive}\n"
        )

        lines.append("## Summary\n")
        lines.append("| Category | Count |")
        lines.append("|----------|-------|")
        lines.append(f"| Added | {len(diff_result.added)} |")
        lines.append(f"| Removed | {len(diff_result.removed)} |")
        lines.append(f"| Modified | {len(diff_result.modified)} |")
        lines.append(f"| Unchanged | {len(diff_result.unchanged)} |")
        lines.append("")

        if diff_result.added:
            lines.append("## Added Endpoints\n")
            lines.append("| Method | Path | Auth |")
            lines.append("|--------|------|------|")
            for ep in diff_result.added:
                auth = "Yes" if ep.requires_auth else "No"
                lines.append(f"| `{ep.method}` | `{ep.path}` | {auth} |")
            lines.append("")

        if diff_result.removed:
            lines.append("## Removed Endpoints (Potential Ghosts)\n")
            lines.append("| Method | Path | Auth |")
            lines.append("|--------|------|------|")
            for ep in diff_result.removed:
                auth = "Yes" if ep.requires_auth else "No"
                lines.append(f"| `{ep.method}` | `{ep.path}` | {auth} |")
            lines.append("")

        if diff_result.modified:
            lines.append("## Modified Endpoints\n")
            lines.append("| Endpoint | Changes |")
            lines.append("|----------|---------|")
            for mod in diff_result.modified:
                changes = ", ".join(mod["changes"].keys())
                lines.append(f"| `{mod['endpoint']}` | {changes} |")
            lines.append("")

        if ghosts:
            lines.append("## Ghost Endpoints (Probed)\n")
            lines.append("| Method | Path | Status | Size | Time | Auth Bypass |")
            lines.append("|--------|------|--------|------|------|-------------|")
            for g in ghosts:
                bypass = "YES" if g.auth_bypassed else "No"
                lines.append(
                    f"| `{g.endpoint.method}` | `{g.endpoint.path}` | "
                    f"{g.status_code} | {g.response_length} | "
                    f"{g.response_time}s | {bypass} |"
                )
            lines.append("")

            alive_ghosts = [g for g in ghosts if g.still_alive and g.response_snippet]
            if alive_ghosts:
                lines.append("### Response Snippets\n")
                for g in alive_ghosts:
                    snippet = g.response_snippet[:200].replace("\n", " ").strip()
                    lines.append(f"**{g.endpoint.method} {g.endpoint.path}:**")
                    lines.append(f"```\n{snippet}\n```\n")

        md = "\n".join(lines)
        if filepath:
            with open(filepath, "w") as f:
                f.write(md)
        return md
