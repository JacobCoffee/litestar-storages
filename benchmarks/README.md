# litestar-storages Benchmarks

Performance benchmarks for core storage operations.

## Running Benchmarks

### Console Output

Run the benchmarks with human-readable output:

```bash
uv run python benchmarks/benchmark_operations.py
```

### JSON Export

Export results to JSON for CI integration:

```bash
uv run python benchmarks/benchmark_operations.py --json benchmark_results.json
```

The JSON output includes:
- Operation name and description
- Number of iterations
- Timing statistics (mean, median, min, max, standard deviation)
- Operations per second

## What is Measured

The benchmark suite measures the following operations using the Memory backend:

### Write Operations
- Small files: 1KB (1000 iterations)
- Small files: 10KB (500 iterations)
- Medium files: 100KB (200 iterations)
- Large files: 1MB (50 iterations)

### Read Operations
- Same sizes as write operations
- Uses `get_bytes()` to read entire file into memory

### Exists Operations
- File existence checks (10,000 iterations)

### Delete Operations
- File deletion (1000 iterations)

### Copy Operations
- Copy 1KB files (500 iterations)
- Copy 100KB files (100 iterations)
- Copy 1MB files (50 iterations)

### Move Operations
- Move 1KB files (500 iterations)
- Move 100KB files (100 iterations)
- Move 1MB files (50 iterations)

### List Operations
- List 10 files (500 iterations)
- List 100 files (200 iterations)
- List 1000 files (50 iterations)

## Implementation Details

- Uses `time.perf_counter_ns()` for precise timing
- Reports mean, median, min, max, and standard deviation
- Calculates operations per second
- Uses Memory backend for reproducibility
- All operations are async/await based

## Example Output

```
Write Operations
--------------------------------------------------------------------------------
  Write 1KB file       | Mean:      3.06 µs | Median:      2.67 µs | StdDev:      7.50 µs
                       | Min:       2.54 µs | Max:       228.33 µs | Rate: 326.56K ops/s
  Write 10KB file      | Mean:     15.19 µs | Median:     15.12 µs | StdDev:    525.79 ns
                       | Min:      14.92 µs | Max:        20.75 µs | Rate: 65.84K ops/s
```

## Notes

- The Memory backend is used for reproducibility and to isolate storage logic from I/O
- Results will vary based on system resources and Python version
- First run may show warm-up effects
- Standard deviation indicates timing consistency
