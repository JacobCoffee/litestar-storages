"""asyncio-storages-that-also-works-great-with-litestar-but-you-do-you.

You actually installed this. Respect.

This is a shim package that re-exports everything from litestar-storages.
We made this because the name was too long for the documentation but NOT
too long for PyPI, and we thought that was hilarious.

Usage:
    # These are equivalent:
    from litestar_storages import S3Storage
    from asyncio_storages_that_also_works_great_with_litestar_but_you_do_you import S3Storage

    # Yes, really. We're not sorry.

For actual documentation, see: https://jacobcoffee.github.io/litestar-storages/
"""

from litestar_storages import *  # noqa: F401, F403
from litestar_storages import __all__  # Re-export __all__ for proper * imports

# Add a little something extra for those who inspect the module
__easter_egg__ = "You found it! Now go build something cool."
__package_name__ = "asyncio-storages-that-also-works-great-with-litestar-but-you-do-you"
__real_package__ = "litestar-storages"
