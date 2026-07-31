

Specification name: ForkLiftSpec

Environment variables:
- distance: { far, close }

System variables:
- command: { lift, drop, go, idle }

The system controls the `command` output based on the `distance` input provided by the environment. The behavior of the system and the environment is constrained by the following requirements.

**Environment Assumptions**
The environment must adhere to the following rules regarding changes in `distance`:
- Whenever the `command` is `idle`, the `distance` must remain unchanged in the next step.
- Whenever the `command` is `go`, the `distance` must become `close` in the next step.
- Whenever the `distance` is `close`:
  - If the `command` is not `lift`, the `distance` must remain `close` in the next step.
  - If the `command` is `lift`, the `distance` must change to `far` in the next step.

**System Guarantees**
The system must satisfy the following conditions:
- **Initial Condition:** Initially, the `command` must be `lift`.
- **Safety Requirements:**
  - Whenever the `distance` is `far`, the `command` in the next step must not be `drop`.
  - Whenever the `distance` is `close`, the `command` in the next step must not be `go`.
- **Liveness Requirements:**
  - The `command` must be `drop` infinitely often.
  - The `command` must be `go` infinitely often.