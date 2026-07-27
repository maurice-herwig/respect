

Specification name: ForkLiftorig

Environment variables:
- distance: { far, close }

System variables:
- command: { lift, drop, go, idle }

The system controls a forklift operation by issuing commands based on the distance to a target. The environment reports the distance, while the system determines the command.

**Environment Assumptions**
The environment updates the `distance` variable according to the following rules:
- If the system issues an `idle` command, the distance remains unchanged in the next step (if it is `far`, it stays `far`; if it is `close`, it stays `close`).
- If the system issues a `go` command, the distance becomes `close` in the next step.
- If the distance is currently `close` and the system issues any command other than `lift`, the distance remains `close` in the next step.
- If the distance is currently `close` and the system issues a `lift` command, the distance changes to `far` in the next step.

**System Guarantees**
The system must satisfy the following requirements:
- Initially, the system sets the `command` to `lift`.
- Whenever the distance is `far`, the system must not issue a `drop` command in the next step.
- Whenever the distance is `close`, the system must not issue a `go` command in the next step.