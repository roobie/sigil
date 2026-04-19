from importlib.metadata import version as _pkg_version, PackageNotFoundError

# Source of truth is pyproject.toml (baked into dist-info at install time).
# Guard covers the "running from an uninstalled source checkout" case
# (e.g. `PYTHONPATH=src python -c "import sigil"`).
try:
    __version__ = _pkg_version("sigil")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"

