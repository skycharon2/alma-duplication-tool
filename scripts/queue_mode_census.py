"""Convenience entry point; install the project with python -m pip install -e ."""

from alma_duplicate.cli.queue_mode_census import main

if __name__ == "__main__":
    raise SystemExit(main())
