Contributing to litestar-storages
=================================

Thank you for your interest in contributing to litestar-storages! This document provides guidelines
and instructions for contributing.

Getting Started
---------------

1. Fork the repository on GitHub
2. Clone your fork locally::

    git clone https://github.com/YOUR_USERNAME/litestar-storages.git
    cd litestar-storages

3. Install uv (if not already installed)::

    curl -LsSf https://astral.sh/uv/install.sh | sh

4. Install development dependencies::

    make dev

5. Install pre-commit hooks::

    make prek-install

Development Workflow
--------------------

Creating a Feature Branch
~~~~~~~~~~~~~~~~~~~~~~~~~

Create a new branch for your work::

    git checkout -b feature/your-feature-name

Or use git worktrees for parallel development::

    make worktree NAME=your-feature-name

Running Tests
~~~~~~~~~~~~~

Run the test suite::

    make test

Run tests with coverage::

    make test-cov

Run only fast tests (excludes integration tests)::

    make test-fast

Code Quality
~~~~~~~~~~~~

Run all CI checks locally before pushing::

    make ci

This runs:

- ``make fmt-check`` - Code formatting check
- ``make lint`` - Linting with ruff
- ``make type-check`` - Type checking with ty
- ``make test-fast`` - Tests (excluding integration)

To auto-fix formatting and lint issues::

    make fmt
    make lint-fix

Building Documentation
~~~~~~~~~~~~~~~~~~~~~~

Build the documentation::

    make docs

Serve documentation with live reload::

    make docs-serve

Commit Guidelines
-----------------

We follow `Conventional Commits <https://www.conventionalcommits.org/>`_ for commit messages.

Format::

    <type>(<scope>): <description>

    [optional body]

    [optional footer]

Types:

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that don't affect code meaning (formatting)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Performance improvement
- **test**: Adding or correcting tests
- **chore**: Changes to build process or auxiliary tools

Examples::

    feat(s3): add multipart upload support
    fix(filesystem): handle unicode filenames correctly
    docs: update installation instructions
    test(memory): add tests for size limits

Pull Request Process
--------------------

1. Ensure all tests pass locally with ``make ci``
2. Update documentation if you're adding or changing features
3. Add tests for new functionality
4. Create a Pull Request with a clear description
5. Link any related issues
6. Wait for CI checks to pass
7. Request review from maintainers

Code Style
----------

- We use `ruff <https://docs.astral.sh/ruff/>`_ for linting and formatting
- Line length is 120 characters
- Use Google-style docstrings
- Type hints are required for public APIs
- All code must pass type checking with ``ty``

Testing Guidelines
------------------

- Write tests for all new functionality
- Use pytest fixtures from ``conftest.py``
- Mark tests appropriately:
  - ``@pytest.mark.unit`` - Fast, isolated tests
  - ``@pytest.mark.integration`` - Tests requiring external services
  - ``@pytest.mark.e2e`` - End-to-end tests
- Use the ``any_storage`` fixture to test against all backends

Example test::

    @pytest.mark.unit
    class TestMyFeature:
        async def test_something(self, any_storage: Storage):
            """Test description."""
            result = await any_storage.put("test.txt", b"data")
            assert result.key == "test.txt"

Release Process (Maintainers)
-----------------------------

This project uses GitHub's **immutable releases** feature for supply chain security.
Once a release is published, its assets and tag cannot be modified.

To create a new release:

1. Bump the version using uv (0.7.0+)::

    uv version --bump patch     # 1.2.3 => 1.2.4
    uv version --bump minor     # 1.2.3 => 1.3.0
    uv version --bump major     # 1.2.3 => 2.0.0

2. Commit and merge to main::

    git add pyproject.toml
    git commit -m "chore: bump version to X.Y.Z"
    # Create PR, wait for CI, merge

3. Push the tag to trigger the release workflow::

    git checkout main && git pull
    git tag vX.Y.Z
    git push origin vX.Y.Z

The CD workflow automatically:

1. Builds the distribution
2. Signs with Sigstore
3. Creates a **draft** GitHub release with assets attached
4. Publishes to PyPI (trusted publishing)
5. Publishes the release (removes draft status)
6. Creates a PR to update the changelog

.. note::

    With immutable releases enabled, tags cannot be reused. If a release
    fails after the tag is pushed, bump to the next patch version instead
    of attempting to recreate the same tag.

Questions?
----------

- Open a `GitHub Discussion <https://github.com/JacobCoffee/litestar-storages/discussions>`_
- Join the `Litestar Discord <https://discord.gg/litestar-919193495116337154>`_
- Check existing `Issues <https://github.com/JacobCoffee/litestar-storages/issues>`_

License
-------

By contributing, you agree that your contributions will be licensed under the MIT License.
