

Specification name: Minepump

Environment variables:
- highwater: boolean
- methane: boolean

System variables:
- pump: boolean
- flag: boolean

The Minepump system manages a water pump based on water levels and methane presence. The environment controls the `highwater` and `methane` inputs, while the system controls the `pump` and `flag` outputs.

**Initial Conditions**
At the start of operation, there is no high water (`highwater` is false) and no methane detected (`methane` is false). The pump is initially off (`pump` is false).

**Environment Assumptions**
The environment behaves according to the following constraints:
1. If the pump runs continuously (it was on in the previous step and is on in the current step), the water level will drop such that `highwater` becomes false in the next step.
2. If the water level is high and the pump is not running effectively (either it was off in the previous step or it is off in the current step), the water level remains high (`highwater` stays true) in the next step.
3. Infinitely often, the methane level is absent for at least two consecutive steps (`methane` is false now and in the next step).

**System Guarantees**
The system must satisfy the following requirements:
1. Whenever there is high water and no methane, the pump must turn on in the next step.
2. Whenever methane is detected, the pump must turn off in the next step.
3. Whenever there is high water, the flag must be raised (`flag` is true).
4. The flag must be lowered (`flag` is false) infinitely often.