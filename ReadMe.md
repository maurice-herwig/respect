# ReSpect

**Reconstructing Spectra Specifications**

## Setup

Create a local `.env` file from the example file:

```powershell
Copy-Item .env.example .env
```

Add a GitHub token to `.env`:

```text
GITHUB_TOKEN=your_github_token_here
```

The `.env` file is ignored by Git and should not be committed.

## GitHub Spectra Discovery

The first dataset step discovers public `.spectra` files through the GitHub Search API. It stores metadata only; file contents are not downloaded in this step.

Run:

```powershell
python dataset\discover_github_spectra.py
```

Useful checks:

```powershell
python dataset\discover_github_spectra.py --dry-run
python dataset\discover_github_spectra.py --resume
```

Discovery outputs are written to `dataset/discovery/`, which is ignored by Git.
