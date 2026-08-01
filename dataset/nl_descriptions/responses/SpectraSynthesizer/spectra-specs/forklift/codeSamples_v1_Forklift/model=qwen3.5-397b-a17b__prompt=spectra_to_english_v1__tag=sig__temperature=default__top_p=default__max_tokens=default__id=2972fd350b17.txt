

Specification name: Forklift

Environment variables:
- obstacle: {BLOCKED, CLEAR}

System variables:
- lMot: {STOP, FWD, BWD}
- rMot: {STOP, FWD, BWD}

The Forklift system controls the left and right motors based on the status of an obstacle sensor. At the start of operation, both the left motor (`lMot`) and the right motor (`rMot`) must be initialized to `STOP`. During operation, whenever the obstacle sensor (`obstacle`) indicates `BLOCKED`, the system must not drive both motors forward (`FWD`) simultaneously. Despite this restriction, the system is required to drive both motors forward (`FWD`) simultaneously infinitely often throughout its operation.

The environment is assumed to respond to backward movement. Specifically, whenever the system sets either the left motor (`lMot`) or the right motor (`rMot`) to backward (`BWD`), the environment must eventually set the obstacle status (`obstacle`) to `CLEAR`.