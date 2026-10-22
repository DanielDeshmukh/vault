"""Explicit ``--target local|neon`` resolution for Phase-5 write scripts.

The Phase-5 reload once silently hit the wrong database: the shell lacked
``NEON_DATABASE_URL`` so the loader fell back to ``.env``'s local URL.
These scripts now refuse to run without an explicit target, print the
masked host before any write, and abort when the resolved host does not
match the requested target.
"""
from __future__ import annotations

import argparse
import os
import sys


def add_target_arg(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--target",
        choices=("local", "neon"),
        required=True,
        help="Postgres to use: 'local' (127.0.0.1) or 'neon'; no implicit default",
    )


def mask_url(url: str) -> str:
    """scheme://***@host/dbname -- credentials never printed."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        after = rest.split("@", 1)[1]
        return f"{scheme}://***@{after}"
    return "<unparseable-url>"


def resolve_target(target: str, *, env_loaded: bool = False) -> str:
    """Return the DB URL for ``target``, printing its masked host first.

    Aborts when the host does not match the requested target:
    ``neon`` requires NEON_DATABASE_URL whose host contains 'neon';
    ``local`` requires a DATABASE_URL that is NOT Neon-hosted.
    """
    if target == "neon":
        url = os.environ.get("NEON_DATABASE_URL", "")
        if not url:
            _abort("target=neon but NEON_DATABASE_URL is empty"
                   + ("" if env_loaded else " (.env not loaded?)"))
        if "neon" not in url.lower():
            _abort(f"target=neon but host is not Neon: {mask_url(url)}")
    else:
        url = os.environ.get("DATABASE_URL", "")
        if not url:
            _abort("target=local but DATABASE_URL is empty")
        if "neon" in url.lower():
            _abort(f"target=local but DATABASE_URL points at Neon: {mask_url(url)}")
    print(f"[target] {target} -> {mask_url(url)}", flush=True)
    return url


def _abort(msg: str) -> None:
    print(f"ABORT: {msg}", flush=True)
    sys.exit(2)
