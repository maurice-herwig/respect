

Specification name: Minepump

Environment variables:
- highwater: boolean
- methane: boolean

System variables:
- pump: boolean

The Minepump system operates continuously to control a pump based on environmental conditions. The environment provides the boolean inputs `highwater` and `methane`, while the system controls the boolean output `pump`.

Regarding assumptions on the environment, it is assumed that at all times, if the variable `pump` is true, then the variable `highwater` must be false in the next step. This constrains the environment to ensure the high water level condition is cleared immediately following pump activation.

Regarding guarantees required from the system, the system must satisfy the following conditions at all times. First, if the variable `methane` is true, then the variable `pump` must be false in the next step. Second, if the variable `highwater` is true and the variable `methane` is false, then the variable `pump` must be true in the next step. These requirements ensure the pump activates to clear water when safe and deactivates when methane is detected.