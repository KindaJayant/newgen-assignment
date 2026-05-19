# Implementation Approaches

## Assignment 1: Out-of-Core Join

### Approach 1: DuckDB CSV Join

DuckDB is the primary implementation. It reads both CSV files directly, performs the inner join in its query engine, and writes the result to CSV.

Why it fits the 256 MB RAM constraint:

- The API sets `memory_limit` to `200MB`.
- DuckDB scans files instead of loading both files into Python objects.
- Intermediate data can spill to the configured temp directory.

Pros:

- Small amount of code.
- Fast and production-realistic.
- Easy to explain and demonstrate.

Cons:

- Depends on an external engine.
- Less educational than writing the algorithm manually.

### Approach 2: External Sort-Merge Join

The pure Python implementation reads each CSV in chunks, sorts each chunk by `user_id`, writes sorted chunks to disk, then performs a k-way merge and streams matching groups into the output CSV.

Why it fits the 256 MB RAM constraint:

- Only one chunk is held in memory during sorting.
- The merge step keeps one row per sorted chunk in memory.
- Joined rows are streamed directly to the output file.

Pros:

- Demonstrates the out-of-core algorithm clearly.
- No database engine required.
- Gives full control over chunk size and temp files.

Cons:

- More code and more edge cases.
- Usually slower than DuckDB.
- Large duplicate-key groups can still be memory-sensitive.

## Assignment 2: Non-Blocking API

### Approach 1: FastAPI BackgroundTasks

The endpoint returns the `job_id` immediately, then FastAPI runs the join function after the response is sent.

Pros:

- Very simple.
- No separate worker setup.
- Good for demos and small internal tools.

Cons:

- Runs inside the web server process.
- Not ideal for CPU-heavy joins.
- Jobs can be interrupted if the server process stops.

### Approach 2: ProcessPoolExecutor

The endpoint creates a job record and submits the join to a separate process. The API process stays free to answer status requests.

Pros:

- Better isolation for CPU-heavy work.
- Keeps the FastAPI event loop responsive.
- Still simple enough for an assignment.

Cons:

- More moving pieces than `BackgroundTasks`.
- Local process pools are not a distributed queue.
- For production, Celery, RQ, or a managed queue would be more durable.
