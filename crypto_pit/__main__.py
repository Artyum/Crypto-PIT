from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Crypto-PIT")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Ścieżka do pliku SQLite (domyślnie data/crypto_pit.db)",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Tylko wypisz rozliczenie lat (bez GUI)",
    )
    args = parser.parse_args()

    if args.cli:
        from crypto_pit.cli import run_cli

        run_cli(args.db)
        return

    from crypto_pit.gui.app import run_app

    run_app(args.db)


if __name__ == "__main__":
    main()
