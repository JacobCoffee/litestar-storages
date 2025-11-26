# asyncio-storages-that-also-works-great-with-litestar-but-you-do-you

[![PyPI version](https://img.shields.io/pypi/v/asyncio-storages-that-also-works-great-with-litestar-but-you-do-you.svg)](https://pypi.org/project/asyncio-storages-that-also-works-great-with-litestar-but-you-do-you/)
[![The Real Package](https://img.shields.io/badge/the%20real%20package-litestar--storages-blue)](https://pypi.org/project/litestar-storages/)

> *"We considered renaming it to 'asyncio-storages-that-also-works-great-with-litestar-but-you-do-you' but that didn't fit on the PyPI page."*
>
> — The litestar-storages docs, moments before we proved them wrong

## What is this?

This is a shim package that re-exports everything from [litestar-storages](https://pypi.org/project/litestar-storages/).

We created it because:
1. The name was "too long for the docs"
2. But NOT too long for PyPI (67 chars < 255 char limit)
3. And we thought that was hilarious

## Installation

```bash
# If you're feeling spicy
pip install asyncio-storages-that-also-works-great-with-litestar-but-you-do-you

# If you want to type less (recommended)
pip install litestar-storages
```

## Usage

```python
# This works
from asyncio_storages_that_also_works_great_with_litestar_but_you_do_you import S3Storage

# But honestly, just use this
from litestar_storages import S3Storage
```

## FAQ

**Q: Why does this exist?**
A: Because we could.

**Q: Should I use this in production?**
A: I mean... it works. But your future self will curse you when they have to type that import.

**Q: Is this a joke?**
A: Yes. But it's also a fully functional package that re-exports a real library.

**Q: Did you really publish this to PyPI?**
A: You're reading this, aren't you?

## The Real Package

For actual documentation, features, and sensible import paths, see:

- **PyPI**: [litestar-storages](https://pypi.org/project/litestar-storages/)
- **Docs**: [jacobcoffee.github.io/litestar-storages](https://jacobcoffee.github.io/litestar-storages/)
- **GitHub**: [JacobCoffee/litestar-storages](https://github.com/JacobCoffee/litestar-storages)

## License

MIT - Same as litestar-storages, because this literally just re-exports it.

---

*If you actually starred this repo because of the package name, we appreciate your sense of humor.*
