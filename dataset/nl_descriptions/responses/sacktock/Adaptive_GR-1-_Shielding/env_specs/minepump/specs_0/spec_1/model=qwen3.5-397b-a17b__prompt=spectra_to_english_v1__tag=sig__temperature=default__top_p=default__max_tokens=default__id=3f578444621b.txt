

Specification name: Minepump

Environment variables:
- highwater: boolean
- methane: boolean

System variables:
- pump: boolean

The Minepump system controls the pump output based on the highwater and methane inputs. Initially, both highwater and methane are false, and the pump is false.

The system must satisfy the following guarantees: if highwater is true and methane is false, then pump must become true in the next step; if methane is true, then pump must become false in the next step.

The environment is subject to the following assumption: if pump was true in the previous step and is true in the current step, then highwater must be false in the next step.