"""
Benchmarks for litestar-storages operations.

Run with: uv run python benchmarks/benchmark_operations.py

This script measures the performance of core storage operations using the Memory backend
for reproducibility. It reports timing statistics including mean, median, min, max,
standard deviation, and operations per second.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add src to path for running standalone
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from litestar_storages.backends.memory import MemoryStorage


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""

    operation: str
    description: str
    iterations: int
    total_ns: int
    mean_ns: float
    median_ns: float
    min_ns: int
    max_ns: int
    stddev_ns: float
    ops_per_sec: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "operation": self.operation,
            "description": self.description,
            "iterations": self.iterations,
            "total_ns": self.total_ns,
            "mean_ns": self.mean_ns,
            "median_ns": self.median_ns,
            "min_ns": self.min_ns,
            "max_ns": self.max_ns,
            "stddev_ns": self.stddev_ns,
            "ops_per_sec": self.ops_per_sec,
        }


def format_time(ns: float) -> str:
    """Format nanoseconds to appropriate unit."""
    if ns < 1_000:
        return f"{ns:.2f} ns"
    if ns < 1_000_000:
        return f"{ns / 1_000:.2f} µs"
    if ns < 1_000_000_000:
        return f"{ns / 1_000_000:.2f} ms"
    return f"{ns / 1_000_000_000:.2f} s"


def format_ops_per_sec(ops: float) -> str:
    """Format operations per second."""
    if ops >= 1_000_000:
        return f"{ops / 1_000_000:.2f}M ops/s"
    if ops >= 1_000:
        return f"{ops / 1_000:.2f}K ops/s"
    return f"{ops:.2f} ops/s"


async def benchmark_operation(
    operation: Callable[[], Any],
    iterations: int,
) -> list[int]:
    """Run an operation multiple times and collect timing data.

    Args:
        operation: Async callable to benchmark
        iterations: Number of times to run the operation

    Returns:
        List of timing measurements in nanoseconds
    """
    timings = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        await operation()
        end = time.perf_counter_ns()
        timings.append(end - start)
    return timings


def analyze_timings(
    operation: str,
    description: str,
    timings: list[int],
) -> BenchmarkResult:
    """Analyze timing measurements and compute statistics.

    Args:
        operation: Operation name
        description: Human-readable description
        timings: List of timing measurements in nanoseconds

    Returns:
        BenchmarkResult with computed statistics
    """
    total = sum(timings)
    mean = statistics.mean(timings)
    median = statistics.median(timings)
    min_time = min(timings)
    max_time = max(timings)
    stddev = statistics.stdev(timings) if len(timings) > 1 else 0.0
    ops_per_sec = 1_000_000_000 / mean if mean > 0 else 0.0

    return BenchmarkResult(
        operation=operation,
        description=description,
        iterations=len(timings),
        total_ns=total,
        mean_ns=mean,
        median_ns=median,
        min_ns=min_time,
        max_ns=max_time,
        stddev_ns=stddev,
        ops_per_sec=ops_per_sec,
    )


class Benchmarks:
    """Collection of storage operation benchmarks."""

    def __init__(self) -> None:
        """Initialize benchmarks."""
        self.storage = MemoryStorage()
        self.results: list[BenchmarkResult] = []

    async def run_all(self) -> None:
        """Run all benchmark suites."""
        print("=" * 80)
        print("litestar-storages Performance Benchmarks")
        print("=" * 80)
        print()

        await self.benchmark_write_operations()
        await self.benchmark_read_operations()
        await self.benchmark_exists_operations()
        await self.benchmark_delete_operations()
        await self.benchmark_copy_operations()
        await self.benchmark_move_operations()
        await self.benchmark_list_operations()

        print()
        print("=" * 80)
        print("Benchmark Complete")
        print("=" * 80)

    async def benchmark_write_operations(self) -> None:
        """Benchmark write operations with various file sizes."""
        print("Write Operations")
        print("-" * 80)

        sizes = [
            (1_024, "1KB", 1000),  # 1KB, 1000 iterations
            (10_240, "10KB", 500),  # 10KB, 500 iterations
            (102_400, "100KB", 200),  # 100KB, 200 iterations
            (1_048_576, "1MB", 50),  # 1MB, 50 iterations
        ]

        for size, label, iterations in sizes:
            data = b"x" * size
            counter = [0]  # Use list to avoid closure issues

            async def operation() -> None:
                await self.storage.put(f"write_test_{counter[0]}", data)
                counter[0] += 1

            timings = await benchmark_operation(operation, iterations)
            result = analyze_timings(
                f"write_{label}",
                f"Write {label} file",
                timings,
            )
            self.results.append(result)
            self._print_result(result)

        print()

    async def benchmark_read_operations(self) -> None:
        """Benchmark read operations with various file sizes."""
        print("Read Operations")
        print("-" * 80)

        sizes = [
            (1_024, "1KB", 1000),
            (10_240, "10KB", 500),
            (102_400, "100KB", 200),
            (1_048_576, "1MB", 50),
        ]

        # Pre-populate storage with test files
        for size, label, _ in sizes:
            data = b"x" * size
            await self.storage.put(f"read_test_{label}", data)

        for _size, label, iterations in sizes:

            async def operation() -> None:
                await self.storage.get_bytes(f"read_test_{label}")

            timings = await benchmark_operation(operation, iterations)
            result = analyze_timings(
                f"read_{label}",
                f"Read {label} file",
                timings,
            )
            self.results.append(result)
            self._print_result(result)

        print()

    async def benchmark_exists_operations(self) -> None:
        """Benchmark exists checks."""
        print("Exists Operations")
        print("-" * 80)

        # Pre-populate storage
        await self.storage.put("exists_test", b"data")

        iterations = 10000

        async def operation() -> None:
            await self.storage.exists("exists_test")

        timings = await benchmark_operation(operation, iterations)
        result = analyze_timings(
            "exists",
            "Check file existence",
            timings,
        )
        self.results.append(result)
        self._print_result(result)

        print()

    async def benchmark_delete_operations(self) -> None:
        """Benchmark delete operations."""
        print("Delete Operations")
        print("-" * 80)

        iterations = 1000
        data = b"test data"

        # Pre-populate storage
        for i in range(iterations):
            await self.storage.put(f"delete_test_{i}", data)

        counter = [0]

        async def operation() -> None:
            await self.storage.delete(f"delete_test_{counter[0]}")
            counter[0] += 1

        timings = await benchmark_operation(operation, iterations)
        result = analyze_timings(
            "delete",
            "Delete file",
            timings,
        )
        self.results.append(result)
        self._print_result(result)

        print()

    async def benchmark_copy_operations(self) -> None:
        """Benchmark copy operations."""
        print("Copy Operations")
        print("-" * 80)

        sizes = [
            (1_024, "1KB", 500),
            (102_400, "100KB", 100),
            (1_048_576, "1MB", 50),
        ]

        for size, label, iterations in sizes:
            data = b"x" * size
            await self.storage.put(f"copy_source_{label}", data)

            counter = [0]

            async def operation() -> None:
                await self.storage.copy(
                    f"copy_source_{label}",
                    f"copy_dest_{label}_{counter[0]}",
                )
                counter[0] += 1

            timings = await benchmark_operation(operation, iterations)
            result = analyze_timings(
                f"copy_{label}",
                f"Copy {label} file",
                timings,
            )
            self.results.append(result)
            self._print_result(result)

        print()

    async def benchmark_move_operations(self) -> None:
        """Benchmark move operations."""
        print("Move Operations")
        print("-" * 80)

        sizes = [
            (1_024, "1KB", 500),
            (102_400, "100KB", 100),
            (1_048_576, "1MB", 50),
        ]

        for size, label, iterations in sizes:
            data = b"x" * size

            # Pre-populate storage
            for i in range(iterations):
                await self.storage.put(f"move_source_{label}_{i}", data)

            counter = [0]

            async def operation() -> None:
                await self.storage.move(
                    f"move_source_{label}_{counter[0]}",
                    f"move_dest_{label}_{counter[0]}",
                )
                counter[0] += 1

            timings = await benchmark_operation(operation, iterations)
            result = analyze_timings(
                f"move_{label}",
                f"Move {label} file",
                timings,
            )
            self.results.append(result)
            self._print_result(result)

        print()

    async def benchmark_list_operations(self) -> None:
        """Benchmark list operations with varying file counts."""
        print("List Operations")
        print("-" * 80)

        file_counts = [
            (10, "10 files", 500),
            (100, "100 files", 200),
            (1000, "1000 files", 50),
        ]

        for count, label, iterations in file_counts:
            # Pre-populate storage
            for i in range(count):
                await self.storage.put(f"list_test_{count}_{i}", b"data")

            async def operation() -> None:
                files = []
                async for file in self.storage.list(prefix=f"list_test_{count}_"):
                    files.append(file)

            timings = await benchmark_operation(operation, iterations)
            result = analyze_timings(
                f"list_{count}",
                f"List {label}",
                timings,
            )
            self.results.append(result)
            self._print_result(result)

        print()

    def _print_result(self, result: BenchmarkResult) -> None:
        """Print a benchmark result in table format."""
        print(f"  {result.description:20} | ", end="")
        print(f"Mean: {format_time(result.mean_ns):>12} | ", end="")
        print(f"Median: {format_time(result.median_ns):>12} | ", end="")
        print(f"StdDev: {format_time(result.stddev_ns):>12}")
        print(f"{'':22} | ", end="")
        print(f"Min: {format_time(result.min_ns):>13} | ", end="")
        print(f"Max: {format_time(result.max_ns):>15} | ", end="")
        print(f"Rate: {format_ops_per_sec(result.ops_per_sec):>12}")

    def export_json(self, filepath: Path) -> None:
        """Export results to JSON file.

        Args:
            filepath: Path to output JSON file
        """
        data = {
            "benchmark": "litestar-storages",
            "backend": "memory",
            "timestamp": time.time(),
            "results": [result.to_dict() for result in self.results],
        }

        with filepath.open("w") as f:
            json.dump(data, f, indent=2)

        print(f"Results exported to: {filepath}")


async def main() -> None:
    """Run benchmarks."""
    benchmarks = Benchmarks()
    await benchmarks.run_all()

    # Export to JSON if requested
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        output_file = Path("benchmark_results.json")
        if len(sys.argv) > 2:
            output_file = Path(sys.argv[2])
        benchmarks.export_json(output_file)


if __name__ == "__main__":
    asyncio.run(main())
