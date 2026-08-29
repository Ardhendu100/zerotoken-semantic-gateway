import time
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

GATEWAY_URL = "http://localhost:8000/v1/chat/completions"

TEST_SUITE = [
    {
        "name": "Scenario 1: Cold Request (Cache MISS)",
        "tenant": "demo_tenant_a",
        "prompt": "Explain the concept of rate limiting in web APIs and gateway proxies.",
        "expected_cache": "MISS"
    },
    {
        "name": "Scenario 2: Semantically Equivalent Query (Cache HIT)",
        "tenant": "demo_tenant_a",
        "prompt": "Explain rate limiting in web APIs and gateways please.",
        "expected_cache": "HIT"
    },
    {
        "name": "Scenario 3: Volatile Query with Time Keyword (Cache BYPASS)",
        "tenant": "demo_tenant_b",
        "prompt": "What is the stock price of Apple today?",
        "expected_cache": "BYPASS"
    }
]


def run_request(client: httpx.Client, tenant_id: str, prompt: str) -> dict:
    payload = {
        "model": "openai/gpt-oss-20b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    headers = {
        "Content-Type": "application/json",
        "X-Tenant-ID": tenant_id
    }

    start_time = time.perf_counter()
    response = client.post(GATEWAY_URL, json=payload, headers=headers)
    latency_ms = (time.perf_counter() - start_time) * 1000

    cache_header = response.headers.get("X-Cache", "UNKNOWN")
    cache_score = response.headers.get("X-Cache-Score", "N/A")

    return {
        "status_code": response.status_code,
        "latency_ms": latency_ms,
        "cache_header": cache_header,
        "cache_score": cache_score,
        "content_sample": response.json().get("choices", [{}])[0].get("message", {}).get("content", "")[:80] + "..."
    }


def main():
    console.print(
        Panel.fit(
            "[bold cyan]⚡ ZeroToken Gateway — Sub-15ms Enterprise Cache Benchmark[/bold cyan]\n"
            "[dim]Demonstrating Semantic Hit Speedup & Smart TTL Bypass[/dim]",
            border_style="cyan"
        )
    )

    client = httpx.Client(timeout=30.0)

    # 1. Verify Gateway Health
    try:
        health = client.get("http://localhost:8000/health")
        if health.status_code != 200:
            console.print("[bold red]❌ Gateway server is not healthy. Start server with `uv run uvicorn app.main:app`[/bold red]")
            return
    except Exception:
        console.print("[bold red]❌ Cannot connect to Gateway at http://localhost:8000. Ensure server is running![/bold red]")
        return

    results = []

    # 2. Run Test Suite
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:

        for test in TEST_SUITE:
            progress.add_task(description=f"[yellow]Running {test['name']}...", total=None)
            res = run_request(client, test["tenant"], test["prompt"])
            results.append({**test, **res})
            time.sleep(0.5)

    # 3. Print Results Table
    table = Table(title="📊 Benchmark Summary Results", show_header=True, header_style="bold magenta")
    table.add_column("Scenario", style="dim", width=32)
    table.add_column("Tenant", style="cyan")
    table.add_column("Cache Status", style="bold")
    table.add_column("Match Score", justify="right")
    table.add_column("Latency (ms)", justify="right")
    table.add_column("HTTP Status", justify="center")

    miss_latency = 0.0
    hit_latency = 0.0

    for r in results:
        status_color = "green" if r["cache_header"] == "HIT" else "yellow" if r["cache_header"] == "MISS" else "blue"
        cache_display = f"[{status_color}]{r['cache_header']}[/{status_color}]"

        if r["cache_header"] == "MISS":
            miss_latency = r["latency_ms"]
        elif r["cache_header"] == "HIT":
            hit_latency = r["latency_ms"]

        table.add_row(
            r["name"].split(":")[0],
            r["tenant"],
            cache_display,
            r["cache_score"],
            f"{r['latency_ms']:.2f} ms",
            str(r["status_code"])
        )

    console.print(table)

    # 4. Print Performance Metrics Summary
    if miss_latency > 0 and hit_latency > 0:
        speedup = miss_latency / hit_latency if hit_latency > 0 else 0
        latency_reduction = ((miss_latency - hit_latency) / miss_latency) * 100

        console.print("\n" + "=" * 60)
        console.print(f"[bold green]🚀 Latency Reduction:[/bold green] [bold white]{latency_reduction:.1f}%[/bold white]")
        console.print(f"[bold green]⚡ Speedup Factor:[/bold green] [bold white]{speedup:.1f}x Faster[/bold white] (From {miss_latency:.1f}ms down to {hit_latency:.1f}ms)")
        console.print(f"[bold green]💰 Upstream API Cost Saved:[/bold green] [bold white]100% on Cache HITs[/bold white]")
        console.print("=" * 60 + "\n")


if __name__ == "__main__":
    main()