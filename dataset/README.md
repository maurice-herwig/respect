# Dataset Pipeline

This directory contains scripts for building the ReSpect evaluation dataset.

## Discovery

`discover_github_spectra.py` discovers public `.spectra` files through the GitHub Search API. It only stores metadata returned by search; file contents are not downloaded in this step.

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

Outputs are written to `dataset/discovery/`:

- `github_spectra_files.jsonl`: one discovered file record per line
- `github_spectra_manifest.json`: query partitions and run metadata

Progress messages are printed to stderr during partitioning and page fetching.
Use `--quiet` to disable them.
