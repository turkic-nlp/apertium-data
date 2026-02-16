#!/usr/bin/env python3
"""Compile Apertium FSTs from source repositories.

Reads a JSON config with language entries and compiles each repo using the
standard Apertium build flow. Outputs compiled artifacts per language:
  - *.automorf.hfst (required)
  - *.autogen.hfst (optional)
  - *.rlx.bin (optional)

Example:
  python scripts/compile_apertium.py --config languages.json --out dist --work build
  python scripts/compile_apertium.py --config languages.json --langs kaz,tur
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REQUIRED_TOOLS = ["git", "autoreconf", "make"]

LICENSE_CANDIDATES = [
    "COPYING",
    "LICENSE",
    "COPYING.LESSER",
    "COPYING.GPL",
]


@dataclass
class LanguageSpec:
    code: str
    name: str
    repo: str
    script: str
    quality: str
    ref: str | None = None


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def _check_tools() -> None:
    missing = []
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            missing.append(tool)
    if missing:
        raise RuntimeError(
            "Missing required build tools: " + ", ".join(missing)
        )


def _load_config(path: Path) -> list[LanguageSpec]:
    data = json.loads(path.read_text())
    langs = data.get("languages", [])
    specs = []
    for entry in langs:
        specs.append(
            LanguageSpec(
                code=entry["code"],
                name=entry.get("name", entry["code"]),
                repo=entry["repo"],
                script=entry["script"],
                quality=entry.get("quality", "unknown"),
                ref=entry.get("ref"),
            )
        )
    return specs


def _clone_repo(spec: LanguageSpec, work_dir: Path, clean: bool) -> Path:
    repo_dir = work_dir / f"apertium-{spec.code}"
    if repo_dir.exists() and clean:
        shutil.rmtree(repo_dir)
    if not repo_dir.exists():
        _run(["git", "clone", "--depth", "1", spec.repo, str(repo_dir)])
    if spec.ref:
        _run(["git", "checkout", spec.ref], cwd=repo_dir)
    return repo_dir


def _compile_repo(repo_dir: Path) -> None:
    try:
        _run(["autoreconf", "-fi"], cwd=repo_dir)
    except subprocess.CalledProcessError:
        _run(["./autogen.sh"], cwd=repo_dir)
    _run(["./configure"], cwd=repo_dir)
    jobs = str(os.cpu_count() or 2)
    _run(["make", "-j", jobs], cwd=repo_dir)


def _collect_outputs(repo_dir: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    patterns = ["*.automorf.hfst", "*.autogen.hfst", "*.rlx.bin", "*.rlx"]
    found: list[Path] = []
    for pattern in patterns:
        for path in repo_dir.rglob(pattern):
            target = out_dir / path.name
            shutil.copy2(path, target)
            found.append(target)
    return found


def _copy_license(repo_dir: Path, out_dir: Path, fallback: Path) -> None:
    for candidate in LICENSE_CANDIDATES:
        src = repo_dir / candidate
        if src.exists():
            shutil.copy2(src, out_dir / "LICENSE")
            return
    shutil.copy2(fallback, out_dir / "LICENSE")


def _write_metadata(spec: LanguageSpec, repo_dir: Path, out_dir: Path) -> None:
    commit = ""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_dir),
            check=True,
            capture_output=True,
            text=True,
        )
        commit = result.stdout.strip()
    except subprocess.CalledProcessError:
        commit = ""

    metadata = {
        "lang": spec.code,
        "name": spec.name,
        "script": spec.script,
        "quality": spec.quality,
        "source": spec.repo,
        "commit": commit,
        "compiled_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "license": "GPL-3.0-or-later",
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


def _filter_langs(specs: list[LanguageSpec], langs: set[str] | None) -> list[LanguageSpec]:
    if not langs:
        return specs
    return [spec for spec in specs if spec.code in langs]


def main(argv: Iterable[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="languages.json", help="Path to config JSON")
    parser.add_argument("--out", default="dist", help="Output directory")
    parser.add_argument("--work", default="build", help="Work directory")
    parser.add_argument("--langs", default="", help="Comma-separated language codes")
    parser.add_argument("--clean", action="store_true", help="Clean repos before build")
    args = parser.parse_args(list(argv))

    config_path = Path(args.config)
    out_dir = Path(args.out)
    work_dir = Path(args.work)

    _check_tools()

    specs = _load_config(config_path)
    lang_set = {code.strip() for code in args.langs.split(",") if code.strip()} or None
    specs = _filter_langs(specs, lang_set)

    if not specs:
        print("No languages selected.")
        return 1

    fallback_license = Path(__file__).resolve().parents[1] / "LICENSE"
    if not fallback_license.exists():
        raise FileNotFoundError(f"Missing fallback LICENSE at {fallback_license}")

    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    for spec in specs:
        print(f"\n=== {spec.code} ({spec.name}) ===")
        repo_dir = _clone_repo(spec, work_dir, args.clean)
        _compile_repo(repo_dir)

        lang_out = out_dir / spec.code
        found = _collect_outputs(repo_dir, lang_out)
        if not found:
            print(f"Warning: no output files found for {spec.code}")

        _copy_license(repo_dir, lang_out, fallback_license)
        _write_metadata(spec, repo_dir, lang_out)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
