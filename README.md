# apertium-data

Precompiled HFST finite-state transducers (FSTs) for Turkic languages, built
from the official Apertium source repositories.

This repository provides a simple build script that clones Apertium language
repos, compiles them with the HFST toolchain, and outputs:

- `*.automorf.hfst` (morphological analyzer)
- `*.autogen.hfst` (morphological generator, optional)
- `*.rlx.bin` (CG3 disambiguation, optional)

Outputs are meant to be hosted (e.g., GitHub Releases) and referenced by
`turkicnlp`'s model catalog.

## Installation

System packages required to compile Apertium data (Ubuntu/Debian):

```bash
sudo apt-get update
sudo apt-get install -y \
  hfst \
  lttoolbox \
  cg3 \
  autoconf \
  automake \
  libtool \
  pkg-config \
  git \
  make
```

Python (no external deps):

```bash
python --version  # Python 3.9+ recommended
```

## Usage

Edit `languages.json` if you want to add/remove languages or pin a git ref.

Compile all languages:

```bash
python scripts/compile_apertium.py --config languages.json --out dist --work build
```

Compile a subset:

```bash
python scripts/compile_apertium.py --config languages.json --langs kaz,tur
```

Outputs are written to `dist/<lang>/` with a `metadata.json` and `LICENSE`.

## CI (GitHub Actions)

Workflow: `.github/workflows/compile-fsts.yml`

Manual trigger (`workflow_dispatch`) inputs:
- `languages`: comma-separated language codes (empty = all from `languages.json`)
- `release_tag`: GitHub Release tag to create (e.g., `v1.0.0`)

The workflow builds each language in a matrix job, creates:
- `release/<lang>.apertium.fst.zip`
- `release/<lang>.apertium.fst.zip.sha256`
- `release/<lang>.catalog.json` (a catalog snippet with URL, checksum, script, source)

All artifacts are uploaded to the GitHub Release for the provided tag.

## License

Apertium language data is GPL-3.0-or-later. This repo includes the GPL-3.0
license and copies the upstream license into each output directory.
