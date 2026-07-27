

Specification name: RG

Environment variables:
- req: boolean
- cl: boolean

System variables:
- gr: boolean
- val: boolean

The system controls the boolean outputs `gr` and `val` based on the boolean inputs `req` and `cl` provided by the environment.

Regarding the environment, the input `req` must be false infinitely often. The input `cl` is initially false and must also be false infinitely often throughout the execution.

Regarding the system, two guarantees must be maintained. First, as a safety requirement, whenever `cl` is true, the output `val` must be false. Second, as a liveness requirement, the condition where both `gr` and `val` are true must occur infinitely often.