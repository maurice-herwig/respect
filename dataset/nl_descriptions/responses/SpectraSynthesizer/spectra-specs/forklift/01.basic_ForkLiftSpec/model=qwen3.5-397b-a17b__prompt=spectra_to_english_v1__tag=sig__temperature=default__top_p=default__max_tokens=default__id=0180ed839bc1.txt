

Specification name: ForkLiftSpec

Environment variables:
- distance: { far, close }

System variables:
- command: { lift, drop, go, idle }

This specification describes a reactive system controlling a forklift. The environment controls the `distance` variable, indicating whether the forklift is `far` from or `close` to a target location. The system controls the `command` variable, issuing operational instructions such as `lift`, `drop`, `go`, or `idle`.

**Environment Assumptions**
The environment is assumed to update the `distance` variable according to the following rules:
- If the `distance` is `far` and the `command` is not `go`, the `distance` remains `far` in the next step.
- If the `command` is `go`, the `distance` becomes `close` in the next step.
- If the `distance` is `close` and the `command` is not `lift`, the `distance` remains `close` in the next step.
- If the `distance` is `close` and the `command` is `lift`, the `distance` becomes `far` in the next step.

**System Guarantees**
The system must satisfy the following requirements:
- **Initial Condition:** Initially, the `command` is set to `idle`.
- **Safety Requirements:**
  - The system must not issue a `lift` command when the `distance` is `far`.
  - The system must not issue a `go` command when the `distance` is `close`.
  - Whenever the system issues a `drop` command, it must be the case that a `lift` command occurred previously and no `drop` command occurred in the time since that `lift` command.
- **Liveness Requirements:**
  - The system must issue the `drop` command infinitely often.
  - The system must issue the `go` command infinitely often.