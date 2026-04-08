#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys
import tabnanny

ROOT = pathlib.Path(__file__).resolve().parents[1]


def iter_python_files() -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for base in [ROOT / "src", ROOT / "tests", ROOT]:
        if not base.exists():
            continue
        if base == ROOT:
            candidates = [ROOT / "streamlit_app.py"]
        else:
            candidates = list(base.rglob("*.py"))
        for path in candidates:
            if path.exists() and path not in paths:
                paths.append(path)
    return paths


def main() -> int:
    bad_tabs: list[str] = []
    bad_indent: list[str] = []

    for path in iter_python_files():
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if "\t" in line:
                bad_tabs.append(f"{path.relative_to(ROOT)}:{line_no}")

        try:
            tabnanny.check(str(path))
        except tabnanny.NannyNag as nag:
            bad_indent.append(f"{path.relative_to(ROOT)}:{nag.get_lineno()} {nag.get_msg()}")

    if bad_tabs or bad_indent:
        print("Indentation verification failed.")
        if bad_tabs:
            print("Lines containing tab characters:")
            for item in bad_tabs:
                print(f"  - {item}")
        if bad_indent:
            print("Tabnanny indentation issues:")
            for item in bad_indent:
                print(f"  - {item}")
        return 1

    print("Indentation verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
