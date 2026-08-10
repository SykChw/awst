"""Output formatting — rich tables when available, plain-text fallback."""
from __future__ import annotations
from typing import Sequence
try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    _console = Console()
    _HAS_RICH = True
except ImportError:
    _console = None  # type: ignore
    _HAS_RICH = False
def table(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    title: str = "",
) -> None:
    if not rows:
        print(f"  (no results)")
        return
    str_rows = [[str(c) for c in row] for row in rows]
    if _HAS_RICH:
        t = Table(title=title or None, show_header=True, header_style="bold cyan",
                  border_style="dim", expand=False)
        for h in headers:
            t.add_column(h, no_wrap=True)
        for row in str_rows:
            t.add_row(*row)
        _console.print(t)
    else:
        widths = [max(len(h), *(len(r[i]) for r in str_rows)) for i, h in enumerate(headers)]
        sep = "  "
        line = sep.join(f"{h:<{w}}" for h, w in zip(headers, widths))
        if title:
            print(f"\n{title}")
        print(line)
        print("─" * len(line))
        for row in str_rows:
            print(sep.join(f"{c:<{w}}" for c, w in zip(row, widths)))
def kv(data: dict[str, object], title: str = "") -> None:
    if title:
        heading(title)
    if not data:
        return
    w = max(len(k) for k in data)
    for k, v in data.items():
        if _HAS_RICH:
            _console.print(f"  [bold]{k:<{w}}[/bold] : {v}")
        else:
            print(f"  {k:<{w}} : {v}")
def heading(text: str) -> None:
    if _HAS_RICH:
        _console.rule(f"[bold]{text}[/bold]")
    else:
        print(f"\n{text}\n" + "─" * 72)
def ok(msg: str) -> None:
    if _HAS_RICH:
        _console.print(f"  [green]✓[/green] {msg}")
    else:
        print(f"  ✓ {msg}")
def warn(msg: str) -> None:
    if _HAS_RICH:
        _console.print(f"  [yellow]?[/yellow] {msg}")
    else:
        print(f"  ? {msg}")
def err(msg: str, hint: str = "") -> None:
    if _HAS_RICH:
        _console.print(f"  [red]✗[/red] {msg}")
        if hint:
            _console.print(f"    [dim]{hint}[/dim]")
    else:
        print(f"  ✗ {msg}")
        if hint:
            print(f"    {hint}")
def error_box(title: str, detail: str, hints: list[str] | None = None) -> None:
    if _HAS_RICH:
        _console.print(f"\n[bold red]✗ {title}[/bold red]")
        _console.print(f"[dim]{detail}[/dim]")
        if hints:
            _console.print("\n[dim]Possible causes:[/dim]")
            for h in hints:
                _console.print(f"  [dim]• {h}[/dim]")
    else:
        print(f"\n✗ {title}")
        print(detail)
        if hints:
            print("\nPossible causes:")
            for h in hints:
                print(f"  • {h}")
def fmt_mib(mib: int | float | str) -> str:
    mib = int(mib)
    return f"{mib//1024}GB" if mib >= 1024 else f"{mib}MB"
def fmt_uptime(launch_time: str) -> str:
    from datetime import datetime, timezone
    try:
        t = datetime.fromisoformat(launch_time.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - t
        s = int(delta.total_seconds())
        h, rem = divmod(s, 3600)
        m = rem // 60
        return f"{h}h{m}m" if h else f"{m}m"
    except Exception:
        return "-"
def confirm(prompt: str, default: bool = False) -> bool:
    hint = "[y/N]" if not default else "[Y/n]"
    try:
        answer = input(f"\n  {prompt} {hint}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")
def pick(prompt: str, options: list[tuple[str, str]]) -> int | None:
    """Interactive numbered picker. Returns 0-based index or None."""
    print(f"\n  {prompt}")
    for i, (label, desc) in enumerate(options):
        if _HAS_RICH:
            _console.print(f"  [cyan]{i+1}[/cyan]  {label}  [dim]{desc}[/dim]")
        else:
            print(f"  {i+1}  {label}  {desc}")
    try:
        answer = input("\n  Select [1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    try:
        idx = int(answer) - 1 if answer else 0
        return idx if 0 <= idx < len(options) else None
    except ValueError:
        return None
