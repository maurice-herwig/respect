

Specification name: ConvoyCarSpec

Environment variables:
- sense: Int(0..255)

System variables:
- mLeft: Int(0..4)
- mRight: Int(0..4)

**System Overview**
This specification defines the behavior of a convoy car controller. The system controls the left and right motor speeds (`mLeft` and `mRight`) based on the distance to the next car (`sense`). The system maintains internal modes for accelerating and slowing down to manage speed adjustments safely while ensuring the car drives straight.

**Environment Assumptions**
- **Initial Distance:** Initially, the sensor reading `sense` must be at least 20.

**System Guarantees**

*Initialization*
- Initially, the car is stopped, meaning both `mLeft` and `mRight` are 0.
- Initially, the system is neither in an `accelerating` mode nor a `slowingDown` mode.

*Safety Requirements*
- **No Turning:** The car must never turn. The values of `mLeft` and `mRight` must always be equal.
- **Speed Adjustment Limits:** 
  - When in `accelerating` mode, `mLeft` must increase by 1 in the next step, unless it is already at the maximum value of 4, in which case it remains 4.
  - When in `slowingDown` mode, `mLeft` must decrease by 1 in the next step, unless it is already at the minimum value of 0, in which case it remains 0.
  - Since `mLeft` must equal `mRight`, these constraints effectively govern the overall speed of the car.

*Control Logic*
The system tracks the previous sensor reading using an internal variable `lastDist`. Based on the current distance `sense` and the trend compared to `lastDist`, the system determines the mode for the next step:
- **Far From Next Car:** If `sense` is 30 or greater, the next state must be `accelerating`.
- **Too Close:** If `sense` is 20 or less, the next state must be `slowingDown`.
- **In Range:** If `sense` is strictly between 20 and 30:
  - If the distance is decreasing (`lastDist` > `sense`), the next state must be `slowingDown`.
  - If the distance is increasing (`lastDist` < `sense`), the next state must be `accelerating`.
  - If the distance is unchanged (`lastDist` = `sense`), the next state must neither be `accelerating` nor `slowingDown`.

*Liveness Requirements*
- **Convoy Progress:** Infinitely often, the system must reach a state where one of the following conditions holds:
  1. The distance is within the target range (strictly between 20 and 30).
  2. The distance is above the target range (30 or greater).
  3. The distance is below the target range (20 or less) and the car is stopped (both motors at 0).