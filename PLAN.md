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

- [x] **Phase 6: Release & Advanced Features**
  - [x] Multipart upload support for large files (S3, GCS, Azure)
  - [x] Progress callbacks for uploads/downloads
  - [x] Retry logic with exponential backoff
  - [x] zizmor workflow security scanning in CI
  - [x] Comprehensive test coverage (99% overall)
  - [x] Performance benchmarking script
  - [x] Library comparison documentation
  - [ ] PyPI release (v0.1.0) - pending PR merges

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
| All tests | 408 | ✅ Passing |
| Code coverage | 99% | ✅ 1206 statements |
| Skipped (known limitations) | 8 | ⏭️ Expected |
| S3 backend | 100% | ✅ via moto server |
| Azure backend | 99% | ✅ via pytest-databases |
| GCS backend | 100% | ✅ via fake-gcs-server |
| Filesystem backend | 97% | ✅ aiofiles |
| Memory backend | 100% | ✅ In-memory |
| Retry utilities | 100% | ✅ Full coverage |

**Test Performance:**
- Collection: ~0.12s (408 tests)
- Full suite: ~12s (with Docker emulators)
- Parallel mode: `make ci` uses pytest-xdist (~1.8s)

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
2. ~~**Add lifespan management to StoragePlugin**~~ ✅
3. ~~**GCS Backend**~~ ✅ - Implemented with gcloud-aio-storage
4. ~~**Azure Backend**~~ ✅ - Implemented with azure-storage-blob
5. ~~**Advanced Features**~~ ✅ - Multipart uploads, progress callbacks, retry logic
6. ~~**Test Coverage**~~ ✅ - 99% overall coverage
7. **First PyPI release**
   - Merge cascading PRs to main
   - Tag v0.1.0
   - Verify trusted publishing works

### Future (v0.2.0+)

8. **Production Hardening**
   - S3-compatible service validation (R2, Spaces, MinIO)
   - Migration guide between backends
   - Connection pooling configuration
   - Production deployment guide

---

## Resolved Questions

1. ~~**Exception naming**~~ **Resolved: Prefix with `Storage`**
2. ~~**Retry logic**~~ **Resolved: Built-in with `@with_retry` decorator and configurable backoff**
3. ~~**Multipart uploads**~~ **Resolved: Automatic for files >5MB, with progress callbacks**

## Open Questions

1. **Streaming uploads from Litestar's UploadFile** - Need to verify async iteration works correctly with all backends
2. **Connection pooling** - Should backends manage their own pools or accept external clients?

---

## References

- [Litestar Stores Documentation](https://docs.litestar.dev/2/usage/stores.html)
- [django-storages Documentation](https://django-storages.readthedocs.io/)
- [fastapi-storages Repository](https://github.com/aminalaee/fastapi-storages)
- [aioboto3 Documentation](https://aioboto3.readthedocs.io/)
- [gcloud-aio-storage](https://github.com/talkiq/gcloud-aio)
- [Azure Storage Blob (async)](https://learn.microsoft.com/en-us/python/api/azure-storage-blob/)

---

*Plan Version: 4.0.0*
*Last Updated: 2025-11-25*
*Status: All Phases Complete (1-6). 99% test coverage. Awaiting PR merges for v0.1.0 release.*
