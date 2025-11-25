# litestar-storages Implementation Plan

## Executive Summary

**litestar-storages** is an async-first file storage abstraction library for Litestar, providing a unified interface for storing and retrieving files across multiple cloud and local backends.

### Key Differentiators

- **Async-native**: Built from the ground up for async/await, unlike django-storages (sync) or fastapi-storages (sync despite the name)
- **Litestar Integration**: First-class plugin support with dependency injection, lifespan management, and DTO integration
- **Modern Python**: Type-safe with full typing support, dataclass-based configuration, protocol-driven design

---

## Implementation Status

### Completed

- [x] **Phase 1: Foundation (MVP)**
  - [x] Project scaffolding with pyproject.toml, CI/CD
  - [x] Core protocol and base class (`base.py`, `types.py`, `exceptions.py`)
  - [x] MemoryStorage backend (for testing)
  - [x] FileSystemStorage backend (with aiofiles)
  - [x] Basic test suite with protocol compliance tests
  - [x] Documentation (Sphinx with Shibuya theme)

- [x] **Phase 2: Cloud Storage (S3)**
  - [x] S3Storage backend with full feature set
  - [x] S3 test suite (30 tests using moto server mode)
  - [x] Documentation for S3 configuration
  - [ ] S3-compatible service validation (R2, Spaces, MinIO) - needs real-world testing

- [x] **Phase 3: Litestar Integration**
  - [x] StoragePlugin implementation
  - [x] Dependency injection support (`provide_storage`)
  - [x] Response DTOs (`StoredFileDTO`)
  - [x] Integration tests with real Litestar app (19 tests)
  - [x] Lifespan management for connection cleanup

- [x] **Project Infrastructure**
  - [x] CI workflow (lint, format, type-check, test matrix)
  - [x] CD workflow (changelog generation, trusted PyPI publishing)
  - [x] git-cliff for automated changelogs
  - [x] Makefile with comprehensive targets
  - [x] prek hooks (pre-commit alternative)
  - [x] ty type checker (Rust-based)
  - [x] CONTRIBUTING.rst guide
  - [x] GitHub PR template

- [x] **Test Suite Optimization** (awesome-pytest-speedup checklist)
  - [x] Fast collection (~0.12s for 145 tests)
  - [x] PYTHONDONTWRITEBYTECODE=1 in Makefile and CI
  - [x] Disabled unused pytest plugins (pastebin, nose, doctest)
  - [x] pytest-socket for network access control
  - [x] pytest-timeout (60s) for hanging test protection
  - [x] pytest-xdist for parallel execution
  - [x] pytest-sugar for better output
  - [x] Optimized fixture scoping (session for immutable data)
  - [x] norecursedirs configured for faster collection

- [x] **Phase 4: Additional Backends**
  - [x] GCSStorage backend (Google Cloud Storage)
  - [x] AzureStorage backend (Azure Blob Storage)
  - [x] Backend-specific documentation
  - [ ] Migration guide between backends

- [x] **Phase 5: API Documentation & Test Optimization**
  - [x] API reference generation (autodoc) - comprehensive docs/api/
  - [x] Test suite optimization (72% faster S3 tests)
  - [x] Auto-managed Docker fixtures (GCS, Azure via pytest-databases)
  - [x] Example applications with full test coverage

### In Progress

- [ ] **Phase 6: Release & Advanced Features**
  - [ ] PyPI release (v0.1.0)
  - [ ] Performance benchmarks
  - [ ] Security audit
  - [x] Multipart upload support for large files (S3)
  - [x] Progress callbacks for uploads/downloads
  - [x] Retry logic with exponential backoff
  - [x] zizmor workflow security scanning in CI

---

## Current Project Structure

```
litestar-storages/
├── src/
│   └── litestar_storages/
│       ├── __init__.py           # Public API exports
│       ├── __metadata__.py       # Version from importlib.metadata
│       ├── base.py               # Storage protocol + BaseStorage ABC
│       ├── types.py              # StoredFile, UploadResult, ProgressInfo, etc.
│       ├── exceptions.py         # StorageError hierarchy (prefixed names)
│       ├── retry.py              # Retry utilities with exponential backoff
│       ├── backends/
│       │   ├── __init__.py       # Backend exports
│       │   ├── filesystem.py     # Local filesystem (aiofiles)
│       │   ├── memory.py         # In-memory (testing)
│       │   └── s3.py             # S3-compatible (aioboto3)
│       └── contrib/
│           ├── __init__.py
│           ├── plugin.py         # Litestar StoragePlugin
│           ├── dependencies.py   # DI utilities
│           └── dto.py            # Response DTOs
├── tests/
│   ├── conftest.py               # Shared fixtures
│   ├── test_protocol.py          # Protocol compliance (all backends)
│   ├── backends/
│   │   ├── test_filesystem.py
│   │   ├── test_memory.py
│   │   └── test_s3.py            # @pytest.mark.integration
│   └── contrib/
│       ├── test_plugin.py        # @pytest.mark.integration
│       └── test_dto.py           # @pytest.mark.integration
├── docs/
│   ├── conf.py                   # Sphinx config (Shibuya theme)
│   ├── index.md                  # Landing page
│   ├── getting-started.md
│   ├── changelog.md              # Auto-generated by git-cliff
│   ├── backends/
│   │   ├── filesystem.md
│   │   ├── s3.md
│   │   └── memory.md
│   └── advanced/
│       └── custom-backends.md
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                # Lint, format, type-check, test matrix
│   │   ├── cd.yml                # Changelog + PyPI publish
│   │   ├── docs.yml              # GitHub Pages deploy
│   │   └── release.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── .claude/
│   └── CLAUDE.md                 # Development instructions
├── pyproject.toml                # uv_build backend, dependency-groups
├── Makefile                      # Development targets
├── CONTRIBUTING.rst
├── README.md
├── LICENSE
└── PLAN.md                       # This file
```

---

## Dependency Configuration

### Core Dependencies
```toml
dependencies = ["litestar>=2.0.0"]
```

### Optional Backend Extras
```toml
[project.optional-dependencies]
filesystem = ["aiofiles>=23.0.0"]
s3 = ["aioboto3>=12.0.0"]
gcs = ["gcloud-aio-storage>=9.0.0"]      # Not yet implemented
azure = ["azure-storage-blob>=12.0.0"]   # Not yet implemented
all = [...]
```

### Development Groups
```toml
[dependency-groups]
dev = [...]   # All dev deps
docs = [...]  # Sphinx, shibuya, myst-parser
lint = [...]  # prek, ruff, codespell, ty
test = [...]  # pytest, pytest-asyncio, moto
```

---

## Exception Naming Convention

Exceptions are prefixed with `Storage` to avoid shadowing Python builtins:

| Our Exception | Avoids Shadowing |
|---------------|------------------|
| `StorageFileNotFoundError` | `FileNotFoundError` |
| `StorageFileExistsError` | `FileExistsError` |
| `StoragePermissionError` | `PermissionError` |
| `StorageConnectionError` | `ConnectionError` |
| `StorageError` | Base class |
| `ConfigurationError` | Configuration issues |

---

## Testing Status

| Test Category | Count | Status |
|---------------|-------|--------|
| All tests | 224 | ✅ Passing |
| Skipped (known limitations) | 6 | ⏭️ Expected |
| S3 backend | 30 | ✅ via moto server |
| Azure backend | 22 | ✅ via pytest-databases |
| GCS backend | 18 | ✅ via fake-gcs-server |
| Example apps | 23 | ✅ Full coverage |
| Retry utilities | 14 | ✅ Unit tests |

**Test Performance:**
- Collection: ~0.14s (230 tests)
- Full suite: ~7s (224 tests, with Docker emulators)
- S3 tests: ~4s (session-scoped moto server - 72% faster)
- Parallel mode: `make ci` uses pytest-xdist

**Run tests:**
```bash
make test-fast        # Unit tests only (default)
make test             # All tests including integration
make test-cov         # With coverage report
make test-parallel    # All tests in parallel (pytest-xdist)
make test-debug       # Verbose with no capture
make test-failed      # Re-run only failed tests
```

---

## Next Steps (Priority Order)

### Immediate (v0.1.0 Release)

1. ~~**Fix remaining integration tests**~~ ✅
   - S3 tests with moto server mode (30 tests)
   - Plugin tests with Litestar test client (19 tests)

2. ~~**Add lifespan management to StoragePlugin**~~ ✅
   - close() method in Storage protocol and backends
   - on_shutdown handler for cleanup
   - Error handling with logging

3. **First PyPI release**
   - Tag v0.1.0
   - Verify trusted publishing works

### Short-term (v0.2.0)

4. **GCS Backend**
   - Implement GCSStorage with gcloud-aio-storage
   - Add GCS-specific tests
   - Document authentication options

5. **Azure Backend**
   - Implement AzureStorage with azure-storage-blob
   - Support multiple auth methods
   - Document connection string setup

### Medium-term (v0.3.0+)

6. **Advanced Features**
   - Multipart uploads for large files
   - Progress callbacks
   - Retry logic with exponential backoff
   - Connection pooling configuration

7. **Performance & Production Readiness**
   - Benchmarks against django-storages
   - Security audit
   - Production deployment guide

---

## Open Questions

1. ~~**Exception naming** - Should we shadow builtins or prefix?~~ **Resolved: Prefix with `Storage`**

2. **Streaming uploads from Litestar's UploadFile** - Need to verify async iteration works correctly with all backends

3. **Connection pooling** - Should backends manage their own pools or accept external clients?

4. **Retry logic** - Built-in retries with backoff, or leave to user?

5. **Multipart uploads** - Automatic multipart for large files, or explicit API?

---

## References

- [Litestar Stores Documentation](https://docs.litestar.dev/2/usage/stores.html)
- [django-storages Documentation](https://django-storages.readthedocs.io/)
- [fastapi-storages Repository](https://github.com/aminalaee/fastapi-storages)
- [aioboto3 Documentation](https://aioboto3.readthedocs.io/)
- [gcloud-aio-storage](https://github.com/talkiq/gcloud-aio)
- [Azure Storage Blob (async)](https://learn.microsoft.com/en-us/python/api/azure-storage-blob/)

---

*Plan Version: 3.1.0*
*Last Updated: 2025-11-25*
*Status: Phases 1-5 Complete. Phase 6 in progress (advanced features done, release pending).*
