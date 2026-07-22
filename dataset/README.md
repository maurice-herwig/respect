# Dataset Pipeline

This directory contains scripts for building and inspecting the ReSpect
evaluation dataset.

Workflow overview: [`dataset_workflow.svg`](dataset_workflow.svg)

Unless a section says otherwise, run commands from the repository root.

## Discovery

`discover_github_spectra.py` discovers public `.spectra` files through the
GitHub Search API. For each size window, it downloads discovered candidates,
runs Spectra synthesis, and stores only files for which a controller can be
synthesized.

Configure `.env` or the current shell with a GitHub token to avoid very small
unauthenticated rate limits:

```powershell
$env:GITHUB_TOKEN = "<token>"
```

Run discovery:

```powershell
python dataset\discover_github_spectra.py
```

Useful checks and options:

```powershell
python dataset\discover_github_spectra.py --dry-run
python dataset\discover_github_spectra.py --resume
python dataset\discover_github_spectra.py --min-size 1 --max-size 1000000
python dataset\discover_github_spectra.py --size-step 500
python dataset\discover_github_spectra.py --target-results-per-query 50
python dataset\discover_github_spectra.py --base-query "extension:spectra fork:false"
python dataset\discover_github_spectra.py --exclude-repo owner/repo
python dataset\discover_github_spectra.py --quiet
```

For especially dense Spectra ranges, lower `--target-results-per-query`:

```powershell
python dataset\discover_github_spectra.py --target-results-per-query 25 --size-step 500
```

GitHub Code Search has strict rate limits. By default, the discovery script
waits until GitHub's reset time when the limit is reached:

```powershell
python dataset\discover_github_spectra.py --rate-limit-mode wait
```

To fail immediately instead:

```powershell
python dataset\discover_github_spectra.py --rate-limit-mode fail
```

To include the current repository in search results:

```powershell
python dataset\discover_github_spectra.py --include-current-repo
```

To refresh older processed candidates:

```powershell
python dataset\discover_github_spectra.py --resume --refresh-before 2026-06-02T00:00:00Z
```

Accepted files are written to `dataset/accepted/`:

- `files/<owner>/<repo>/<original-path>.spectra`: accepted `.spectra` files
  grouped by GitHub repository and original path
- `accepted_manifest.jsonl`: metadata for accepted files only
- `processed_candidates.jsonl`: metadata for all processed candidates,
  including rejected files
- `last_run_manifest.json`: summary of the latest run

Downloaded candidates are written under `dataset/candidates/` while they are
being checked. Temporary synthesis output is written to `dataset/work/`.

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

Generate descriptions for the accepted dataset:

```powershell
python dataset\generate_nl_description.py
```

By default, the script processes only one accepted record per
`content_sha256`, so duplicate Spectra contents are skipped before generation.
If a successful description already exists for a duplicate file with the same
Spectra content, model, prompt, system prompt, and generation settings, the
current duplicate group is skipped as already generated.
To process every accepted record anyway:

```powershell
python dataset\generate_nl_description.py --no-dedupe-by-content
```

Use a specific prompt template from `prompts.py`:

```powershell
python dataset\generate_nl_description.py --prompt-name spectra_to_english_v1
```

To make later reconstruction runs use the exact original alphabet, include the
environment and system variable signature in the generated natural-language
description prompt:

```powershell
python dataset\generate_nl_description.py --include-signature
```

With this option, the prompt asks the model to include the exact variable names
and domains, grouped as environment-controlled inputs and system-controlled
outputs. Generated response filenames include the fixed `tag=sig` marker, and
`descriptions.jsonl` records `include_signature`, `signature_filename_tag`, and
`source_signature`.

Existing successful descriptions for the same Spectra content, model, prompt,
and explicit generation settings are skipped automatically. Use a timestamp to
refresh older descriptions:

```powershell
python dataset\generate_nl_description.py --refresh-before 2026-06-02T00:00:00Z
```

Use `--force` to regenerate all descriptions for the current configuration:

```powershell
python dataset\generate_nl_description.py --force
```

Optional logging:

```powershell
python dataset\generate_nl_description.py --log-level DEBUG --log-file dataset\nl_descriptions\generation.log
```

Run a single API test prompt:

```powershell
python dataset\generate_nl_description.py --prompt "Describe a traffic light controller in English."
python dataset\generate_nl_description.py --prompt-file prompt.txt
```

Pass generation parameters only when you want explicit overrides:

```powershell
python dataset\generate_nl_description.py --prompt-file prompt.txt --temperature 0.2 --top-p 1.0 --max-tokens 2000
```

Raw API responses are not stored by default. To keep them:

```powershell
python dataset\generate_nl_description.py --keep-raw-responses
```

Outputs are written to `dataset/nl_descriptions/`:

- `responses/<owner>/<repo>/<original-path-without-suffix>/<model-and-settings>.txt`
- `descriptions.jsonl`

The response file name includes the model, prompt name, explicit generation
settings, and a short configuration hash. This lets the dataset store multiple
natural-language descriptions for the same Spectra file.

## Accepted Dataset Duplicate Summary

`summarize_accepted_duplicates.py` summarizes how many accepted records have
distinct Spectra contents and how many records are duplicates by
`content_sha256`.

From the repository root:

```powershell
python dataset\summarize_accepted_duplicates.py
```

From this `dataset` directory, for example when an IDE uses `dataset` as the
working directory:

```powershell
python summarize_accepted_duplicates.py
```

Print fewer or more large duplicate groups:

```powershell
python dataset\summarize_accepted_duplicates.py --top 5
```

For machine-readable output:

```powershell
python dataset\summarize_accepted_duplicates.py --json
```

## Academic Cloud Models

The currently available models can be queried from Academic Cloud:

```powershell
curl -X POST `
  --url https://chat-ai.academiccloud.de/v1/models `
  --header "Accept: application/json" `
  --header "Authorization: Bearer <api_key>" `
  --header "Content-Type: application/json"
```

Example text/coding models from the GWDG documentation:

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
