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

For Academic Cloud/GWD natural-language generation, add:

```text
ACADEMIC_CLOUD_API_KEY=your_academic_cloud_api_key_here
ACADEMIC_CLOUD_BASE_URL=https://chat-ai.academiccloud.de/v1
ACADEMIC_CLOUD_MODEL=meta-llama-3.1-8b-instruct
```

The GWDG/Academic Cloud API is OpenAI-compatible. Current model names can be
checked with:

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

## Natural-Language Description Generation

The natural-language generation script reads accepted Spectra files from `dataset/accepted/accepted_manifest.jsonl`, sends one independent Academic Cloud/GWD chat-completion request per file, and stores the English descriptions with metadata.

Make sure `.env` contains:

```text
ACADEMIC_CLOUD_API_KEY=your_academic_cloud_api_key_here
ACADEMIC_CLOUD_BASE_URL=https://chat-ai.academiccloud.de/v1
ACADEMIC_CLOUD_MODEL=the_model_you_want_to_use
```

Generate descriptions for the accepted Spectra dataset:

```powershell
python dataset\generate_nl_description.py
```

Each request is isolated: the script sends only the system prompt and the current file prompt, with no chat history from previous files.

Existing successful descriptions for the same Spectra content, model, prompt,
and explicit parameter settings are skipped automatically. To refresh older
descriptions:

```powershell
python dataset\generate_nl_description.py --refresh-before 2026-06-02T00:00:00Z
```

To regenerate everything for the current configuration:

```powershell
python dataset\generate_nl_description.py --force
```

Run a single API test prompt:

```powershell
python dataset\generate_nl_description.py --prompt "Describe a simple traffic light controller in English."
python dataset\generate_nl_description.py --prompt-file prompt.txt
```

If `--temperature`, `--top-p`, and `--max-tokens` are omitted, the Academic Cloud model defaults are used.

Outputs are written to:

```text
dataset/nl_descriptions/responses/<owner>/<repo>/<original-path-without-suffix>/<model-and-settings>.txt
dataset/nl_descriptions/raw_responses/
dataset/nl_descriptions/descriptions.jsonl
```

This allows multiple natural-language descriptions for the same Spectra file,
for example one file per model, prompt, temperature, `top_p`, and `max_tokens`
combination.
