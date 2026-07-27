

Specification name: Blink5

Environment variables:
- atStation: boolean

System variables:
- light: boolean

The system controls a light signal based on station presence. The environment controls the boolean input `atStation`, which indicates whether the system is at a station. The system controls the boolean output `light`.

A blink is defined as a change in the value of `light` between the current state and the next state. The system maintains an internal counter named `blinks` that ranges from 0 to 5. Initially, the `blinks` counter is set to 0.

The counter behavior is defined as follows:
- The counter increments when `atStation` is true and a blink occurs.
- The counter resets to 0 when `atStation` is false.
- The counter saturates at 5 and does not overflow.

The system must satisfy the following guarantee: At all times, if `atStation` is true and the `blinks` counter is less than 5, the system must toggle the `light` in the next state. This requires the system to generate blinks continuously while at the station until the counter reaches 5.