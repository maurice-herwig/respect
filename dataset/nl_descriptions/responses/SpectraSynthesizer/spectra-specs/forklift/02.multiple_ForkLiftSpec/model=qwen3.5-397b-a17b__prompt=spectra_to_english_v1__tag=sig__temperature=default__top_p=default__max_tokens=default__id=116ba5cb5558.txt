

Specification name: ForkLiftSpec

Environment variables:
- sense: { clear, blocked }

System variables:
- command: { lift, drop, go, idle, turn }
- loaded: boolean

**Requirements Description**

This specification defines the behavior of a fork lift system interacting with its environment. The environment controls the `sense` variable, indicating whether the path is `clear` or `blocked`. The system controls the `command` variable, selecting actions such as `lift`, `drop`, `go`, `idle`, or `turn`, and the `loaded` boolean variable, indicating whether the fork is carrying a load.

**Environment Assumptions**
The environment behaves according to the following rules regarding the `sense` variable:
1.  If `sense` is `blocked` and the system does not issue a `turn` or `lift` command, `sense` remains `blocked` in the next step.
2.  If the system issues a `go` command, `sense` becomes `blocked` in the next step.
3.  If the system issues a `turn` or `lift` command, `sense` becomes `clear` in the next step.

**System Guarantees**
The system must satisfy the following requirements:

*Initial Conditions*
1.  Initially, the `command` is `idle` and `loaded` is false.

*State Updates*
2.  If the `command` is `lift`, `loaded` becomes true in the next step.
3.  If the `command` is `drop`, `loaded` becomes false in the next step.
4.  If the `command` is neither `drop` nor `lift`, the value of `loaded` remains unchanged in the next step.

*Safety Constraints*
5.  The system must not issue a `lift` command if `loaded` is true.
6.  The system must not issue a `drop` command if `loaded` is false.
7.  If `sense` is `clear`, the system must not issue a `drop` or `lift` command.
8.  If `sense` is `blocked`, the system must not issue a `go` command.

*Liveness Requirements*
9.  The system must issue the `drop` command infinitely often during operation.