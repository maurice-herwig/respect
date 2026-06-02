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

The dataset script discovers public `.spectra` files through the GitHub Search API. For each size window, it downloads discovered candidates, checks whether Spectra can synthesize a controller, and stores only accepted files.

Run:

```powershell
python dataset\discover_github_spectra.py
```

Useful checks:

```powershell
python dataset\discover_github_spectra.py --dry-run
python dataset\discover_github_spectra.py --resume
```

Accepted files are written to `dataset/accepted/`. Temporary downloads and synthesis artifacts are written to `dataset/work/`, which is ignored by Git.
