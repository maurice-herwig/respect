# ReSpect

**Reconstructing Spectra Specifications**

## Setup

Install Spot for omega-automata and HOA operations. Use the LRDE/EPITA Spot
package from conda-forge in a supported Linux/macOS environment.

On Windows, use WSL2 because the conda-forge Spot package does not currently
provide a native Windows build. From an administrator PowerShell, install
Ubuntu if WSL is not already available:

```powershell
wsl --install -d Ubuntu
```

Restart Windows if prompted, then open Ubuntu and create your Linux user. Inside
Ubuntu, update packages and install basic tools:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates
```

Install Miniforge, which is the conda-forge based Conda distribution:

```bash
curl -L -o Miniforge3-Linux-x86_64.sh \
  https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh
```

When the installer asks whether it should initialize Conda, answer `yes`. Close
and reopen Ubuntu, then create a dedicated environment for Spot-based
evaluation:

```bash
conda create -n respect-spot python=3.12 conda-forge::spot
conda activate respect-spot
python -c "import spot; print(spot.version())"
```

If `conda` is not found after reopening Ubuntu, initialize Miniforge manually:

```bash
~/miniforge3/bin/conda init bash
exec bash
```

If `~/miniforge3/bin/conda` does not exist, rerun the Miniforge installer above.

Do not use `pip install spot`; the PyPI package with that name is not the Spot
omega-automata library used by this project.

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

Optional logging:

```powershell
python dataset\generate_nl_description.py --log-level DEBUG --log-file dataset\nl_descriptions\generation.log
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
dataset/nl_descriptions/descriptions.jsonl
```

This allows multiple natural-language descriptions for the same Spectra file,
for example one file per model, prompt, temperature, `top_p`, and `max_tokens`
combination.

Raw API responses are not stored by default. To keep them:

```powershell
python dataset\generate_nl_description.py --keep-raw-responses
```

## Skill-Based Reconstruction Experiments

After natural-language descriptions have been generated, run a selected agent
skill once per description from the repository root:

```powershell
python experiments\reconstruct_with_skill.py --skill respect-method-2 --limit 15
```

If your IDE starts the process with `experiments` as the working directory, use
the script name without the leading folder:

```powershell
python reconstruct_with_skill.py --skill respect-method-2 --limit 4
```

Remove `--dry-run` to start real agent processes. Experiment outputs are written
to `experiments/runs/`, which is ignored by Git.

The default agent command is
`codex --ask-for-approval never exec --ephemeral --sandbox danger-full-access -`,
so each description is processed in a fresh Codex process without persisted
session files while allowing the skill to access repository files and run the
local Spectra CLI workflow. The full-access sandbox setting is used because the
nested Windows workspace sandbox can fail before local validation commands start.

If the agent reports a final `spectra_file`, it is copied into the mirrored run
directory alongside the prompt and captured agent output. For example:

```text
dataset/nl_descriptions/responses/A/B/C.txt
experiments/runs/A/B/C/respect-method-2/respect-method-2.spectra
```

Run artifacts such as `agent_prompt.txt`, `agent_stdout.txt`, and
`agent_stderr.txt` are stored under:

```text
experiments/runs/A/B/C/respect-method-2/
```
