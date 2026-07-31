

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- guard: Dim[2]

System variables:
- none

The EscapingGuard specification defines assumptions constraining the behavior of the environment. The environment controls the input variable `guard`, which is an array of two elements. Each element holds a value of type `Dim`, representing integers from 0 to D.

The environment must ensure that the values of `guard[0]` and `guard[1]` change gradually over time. Specifically, at each step, the next value of each element must be either equal to its current value, one greater than its current value, or one less than its current value. This requirement holds always throughout the system's operation.