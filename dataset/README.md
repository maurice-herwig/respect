# Dataset Pipeline

This directory contains scripts for building the ReSpect evaluation dataset.

## Natural-Language Generation

`generate_nl_description.py` calls the Academic Cloud/GWD OpenAI-compatible
chat-completions API for accepted Spectra files. It sends one independent
request per file, with no chat history from previous files.

Configure `.env`:

```text
ACADEMIC_CLOUD_API_KEY=<token>
ACADEMIC_CLOUD_BASE_URL=https://chat-ai.academiccloud.de/v1
ACADEMIC_CLOUD_MODEL=meta-llama-3.1-8b-instruct
```

Useful model examples from the GWDG documentation:

```text
meta-llama-3.1-8b-instruct
llama-3.3-70b-instruct
qwen3-coder-30b-a3b-instruct
qwen3.5-27b
qwen3.5-122b-a10b
mistral-large-3-675b-instruct-2512
devstral-2-123b-instruct-2512
deepseek-r1-distill-llama-70b
```

The currently available models can be queried from Academic Cloud:

```bash
curl -X POST \
  --url https://chat-ai.academiccloud.de/v1/models \
  --header "Accept: application/json" \
  --header "Authorization: Bearer <api_key>" \
  --header "Content-Type: application/json"
```

Generate descriptions for the accepted dataset:

```bash
python dataset/generate_nl_description.py
```

Use a specific prompt template from `dataset/prompts.py`:

```bash
python dataset/generate_nl_description.py --prompt-name spectra_to_english_v1
```

Existing successful descriptions for the same Spectra content, model, prompt,
and explicit generation settings are skipped automatically. Use a timestamp to
refresh older descriptions:

```bash
python dataset/generate_nl_description.py --refresh-before 2026-06-02T00:00:00Z
```

Use `--force` to regenerate all descriptions for the current configuration:

```bash
python dataset/generate_nl_description.py --force
```

Run a single API test prompt:

```bash
python dataset/generate_nl_description.py --prompt "Describe a traffic light controller in English."
python dataset/generate_nl_description.py --prompt-file prompt.txt
```

If `--temperature`, `--top-p`, or `--max-tokens` are omitted, they are not sent
to the API and the Academic Cloud model defaults are used. Pass them only when
you want an explicit override:

```bash
python dataset/generate_nl_description.py --prompt-file prompt.txt --temperature 0.2 --top-p 1.0 --max-tokens 2000
```

Outputs are written to `dataset/nl_descriptions/`:

- `responses/<owner>/<repo>/<original-path-without-suffix>/<model-and-settings>.txt`: generated natural-language text, using the same repository/path structure as `dataset/accepted/files/`
- `raw_responses/<description_id>.json`: raw API response
- `descriptions.jsonl`: metadata including dataset_id, source Spectra path, model, optional generation overrides, timing, usage, prompt hashes, and response paths

The response file name includes the model, prompt name, explicit generation
settings, and a short configuration hash. This lets the dataset store multiple
natural-language descriptions for the same Spectra file.

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
python dataset/discover_github_spectra.py --exclude-repo owner/repo
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

- `files/<owner>/<repo>/<original-path>.spectra`: accepted `.spectra` files grouped by GitHub repository and original path
- `accepted_manifest.jsonl`: metadata for accepted files only
- `processed_candidates.jsonl`: metadata for all processed candidates, including rejected files
- `last_run_manifest.json`: summary of the latest run

Accepted manifest records include the GitHub search score as
`github_ranking_score` and repository license metadata:

- `license_found`
- `license_key`
- `license_name`
- `license_spdx_id`
- `license_url`
- `license_html_url`

Downloaded candidates are written under `dataset/candidates/` while they are being checked. After a candidate has a record in `processed_candidates.jsonl`, the downloaded candidate file is removed by default to save disk space. Use `--keep-candidate-files` to preserve these downloads. Temporary synthesis output is written to `dataset/work/` and removed after each candidate unless `--keep-controller-output` is enabled.

Resume behavior:

```bash
python dataset/discover_github_spectra.py --resume
```

With `--resume`, candidates listed in `processed_candidates.jsonl` are skipped entirely. If a candidate file still exists in `dataset/candidates/` because the previous run was interrupted before processing finished, the cached file is reused instead of downloading it again.

The script excludes `maurice-herwig/respect` by default and also automatically
excludes the current GitHub `origin` repository from search results. This
prevents an uploaded dataset from being downloaded from the same ReSpect
repository on later runs. Add more exclusions with:

```bash
python dataset/discover_github_spectra.py --exclude-repo owner/repo
```

To include the current repository anyway:

```bash
python dataset/discover_github_spectra.py --include-current-repo
```

To refresh older results, pass an ISO timestamp. Records processed before the
timestamp are ignored during resume and will be downloaded and checked again:

```bash
python dataset/discover_github_spectra.py --resume --refresh-before 2026-06-02T00:00:00Z
```

Timestamps without a timezone are interpreted as UTC:

```bash
python dataset/discover_github_spectra.py --resume --refresh-before 2026-06-02
```

Progress messages are printed to stderr during partitioning, downloads,
synthesis checks, accepted-file storage, and page fetching. Use `--quiet` to
disable them.
