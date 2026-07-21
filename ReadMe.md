# ReSpect

**Reconstructing Spectra Specifications**

ReSpect is a pipeline for studying how Spectra specifications can be
reconstructed from natural-language requirements. The repository collects
realizable `.spectra` files, generates English descriptions for them, runs
agent-based reconstruction experiments, and summarizes the results.

## Repository Layout

- `dataset/`: Build and inspect the evaluation dataset. This includes GitHub
  discovery of `.spectra` files, natural-language description generation, and
  duplicate statistics. See [`dataset/README.md`](dataset/README.md).
- `experiments/`: Run reconstruction experiments by invoking a selected Codex
  skill once per generated description. See
  [`experiments/README.md`](experiments/README.md).
- `evaluation/`: Summarize reconstruction results and run evaluation utilities.
  See [`evaluation/README.md`](evaluation/README.md).
- `assets/`: Example Spectra specifications and diagrams used for explanation
  and development. See [`assets/examples/README.md`](assets/examples/README.md).
- `.agents/skills/respect-method-3.1/`: Codex skill used for the reconstruction
  condition. It generates Spectra with grammar guidance, validates with
  `spectra-cli.jar`, repairs CLI-reported syntax and realizability issues,
  synthesizes a controller when realizable, and runs NL-guided controller tests.
- `.agents/skills/respect-method-cross-broker/`: Codex skill used for the
  cross-agent reconstruction condition. It uses grammar-guided CLI validation,
  counter-strategy diagnostics, synthesis, and peer disagreement feedback from
  `experiments/cross_broker.py`.

## Environment

Create a local `.env` file from `.env.example` and add the credentials needed
for the scripts you run:

```text
GITHUB_TOKEN=your_github_token_here
ACADEMIC_CLOUD_API_KEY=your_academic_cloud_api_key_here
ACADEMIC_CLOUD_BASE_URL=https://chat-ai.academiccloud.de/v1
ACADEMIC_CLOUD_MODEL=meta-llama-3.1-8b-instruct
```

`GITHUB_TOKEN` is used by dataset discovery. The Academic Cloud/GWDG settings
are used by natural-language description generation. The `.env` file is ignored
by Git and should not be committed.

## Spot Setup

Some evaluation code depends on Spot for omega-automata and HOA operations. Use
the LRDE/EPITA Spot package from conda-forge in a supported Linux/macOS
environment. On Windows, use WSL2 because the conda-forge Spot package does not
currently provide a native Windows build.

Do not use `pip install spot`; the PyPI package with that name is not the Spot
omega-automata library used by this project.

## Typical Workflow

1. Use `dataset/` to discover or inspect accepted Spectra specifications.
2. Use `dataset/` to generate natural-language descriptions.
3. Use `experiments/` to reconstruct Spectra from those descriptions.
4. Use `evaluation/` to summarize the reconstruction outcomes.

The concrete commands live in the README of the corresponding subdirectory.
