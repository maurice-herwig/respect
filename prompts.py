"""Prompt constants for ReSpect dataset generation scripts."""

DEFAULT_NL_DESCRIPTION_SYSTEM_PROMPT = (
    "You write clear, precise English natural-language descriptions for formal system specifications."
)

SPECTRA_TO_ENGLISH_V1 = """Spectra is a formal specification language for reactive systems. A Spectra specification 
describes an ongoing interaction between an environment and a system. Variables declared with `env` are controlled by 
the environment, while variables declared with `sys` are controlled by the system. Assumptions, usually written with 
`asm`, restrict the allowed behavior of the environment. Guarantees, usually written with `gar`, define the behavior 
that the system must satisfy whenever the environment satisfies the assumptions. Temporal operators such as 
`ini`, `alw`, `alwEv`, and `next` describe initial conditions, safety conditions that must always hold, liveness 
conditions that must happen infinitely often, and next-state relationships.

Task:
Translate the following Spectra specification into a clear English natural-language requirements description.

Instructions:
- Write the description the way a human would naturally describe the intended reactive-system behavior.
- Preserve the specified behavior as precisely as possible.
- Identify the environment-controlled inputs and system-controlled outputs.
- Explain the assumptions on the environment.
- Explain the guarantees required from the system.
- Describe initial conditions, safety requirements, liveness requirements, and next-state/update rules when they appear.
- Keep the description faithful to the specification; do not add behavior that is not stated or implied.
- Do not add meta-comments about missing parts of the specification, such as absent environment inputs, absent assumptions, or unspecified behavior beyond the stated requirements.
- If the specification only contains initial conditions or partial behavior, simply describe those stated requirements without emphasizing that other requirements are missing.
- Do not copy the Spectra code into the answer.
- Do not discuss your translation process.
- Write in concise but complete English prose.

Spectra specification:

```spectra
{spectra_code}
```
"""

PROMPTS = {
    "spectra_to_english_v1": SPECTRA_TO_ENGLISH_V1,
}
