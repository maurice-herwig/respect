# Dataset Pipeline

This directory contains scripts for building the ReSpect evaluation dataset.

## Discovery

`discover_github_spectra.py` discovers public `.spectra` files through the GitHub Search API. For each size window, it downloads discovered candidates, runs Spectra synthesis, and stores only files for which a controller can be synthesized.

Run with a GitHub token to avoid very small unauthenticated rate limits:

```bash
$env:GITHUB_TOKEN = "<token>"
python dataset/discover_github_spectra.py
```

Useful options:

```bash
python dataset/discover_github_spectra.py --dry-run
python dataset/discover_github_spectra.py --resume
python dataset/discover_github_spectra.py --min-size 1 --max-size 1000000
python dataset/discover_github_spectra.py --size-step 500
python dataset/discover_github_spectra.py --target-results-per-query 50
python dataset/discover_github_spectra.py --base-query "extension:spectra fork:false"
python dataset/discover_github_spectra.py --quiet
```

The discovery script partitions code-search requests by file size. The default
`--size-step 1000` is the maximum adaptive window width. After each query, the
script reads GitHub's `total_count` and adjusts the next size window:

- dense windows become smaller, down to `--min-size-step 1`
- sparse windows can grow back up to `--size-step`
- windows with more than `--max-results-per-query 500` results are recursively split before fetching pages
- each size window is downloaded and tested before the next size window is queried, so synthesis time naturally spaces out API calls

For especially dense Spectra ranges, lower `--target-results-per-query`, for example:

```bash
python dataset/discover_github_spectra.py --target-results-per-query 25 --size-step 500
```

## Rate Limits

GitHub Code Search has strict rate limits. By default, the discovery script waits
until GitHub's reset time when the limit is reached:

```bash
python dataset/discover_github_spectra.py --rate-limit-mode wait
```

To fail immediately instead:

```bash
python dataset/discover_github_spectra.py --rate-limit-mode fail
```

If the script waits often, use less aggressive partitioning, for example:

```bash
python dataset/discover_github_spectra.py --target-results-per-query 100 --size-step 1000
```

Accepted files are written to `dataset/accepted/`:

- `files/`: accepted `.spectra` files
- `accepted_manifest.jsonl`: metadata for accepted files only
- `last_run_manifest.json`: summary of the latest run

Temporary downloads and controller outputs are written to `dataset/work/` and removed after rejected candidates. Use `--keep-controller-output` to preserve controller artifacts for accepted files under `dataset/accepted/controllers/`.

Progress messages are printed to stderr during partitioning and page fetching.
Use `--quiet` to disable them.
