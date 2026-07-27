

Specification name: Minepump

Environment variables:
- highwater: boolean
- methane: boolean

System variables:
- pump: boolean

The Minepump system controls a pump based on environmental water levels and methane presence. The environment provides the inputs `highwater` and `methane`, while the system controls the output `pump`.

Regarding environmental behavior, it is assumed that if the `pump` was true in the previous step, then `highwater` must be false in the next step.

The system must satisfy the following guarantees at all times:
1. If `methane` is false and `highwater` is true, then `pump` must be true in the next step.
2. If `methane` is true, then `pump` must be false in the next step.