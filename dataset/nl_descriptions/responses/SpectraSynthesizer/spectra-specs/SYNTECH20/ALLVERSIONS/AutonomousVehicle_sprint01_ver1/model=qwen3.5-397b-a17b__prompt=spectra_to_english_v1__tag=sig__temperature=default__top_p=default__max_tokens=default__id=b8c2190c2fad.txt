

Specification name: AutonomousVehicle

Environment variables:
- pedestrian: boolean
- crosswalk: boolean
- greenLight: boolean

System variables:
- speed: Int(0..10)

The AutonomousVehicle system controls the `speed` output based on environmental inputs. For the purposes of this specification, the system is defined as driving when `speed` is greater than 0 and slowing when `speed` is less than 5.

It is assumed that the environment will infinitely often provide a condition where `greenLight` is true and `pedestrian` is false.

The system must satisfy the following requirements:
1. **Safety:** At all times, if `pedestrian` is true or `greenLight` is false, the system must not be driving (meaning `speed` must be 0).
2. **Safety:** At all times, if `crosswalk` is true, the system must be slowing (meaning `speed` must be less than 5).
3. **Liveness:** Infinitely often, when `greenLight` is true and `pedestrian` is false, the system must be driving (meaning `speed` must be greater than 0).