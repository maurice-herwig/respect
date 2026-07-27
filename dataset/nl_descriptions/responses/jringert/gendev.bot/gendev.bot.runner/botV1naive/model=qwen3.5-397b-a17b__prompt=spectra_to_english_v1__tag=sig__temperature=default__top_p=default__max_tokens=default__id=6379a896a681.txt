

Specification name: BotV1naive

Named domains:
- MotorCmd: {FWD, BWD, STP}

Environment variables:
- distance: Int(0..100)

System variables:
- leftM: MotorCmd
- rightM: MotorCmd

The system controls two motors via the output variables `leftM` and `rightM`. Each motor command must be selected from the set {FWD, BWD, STP}, representing forward, backward, and stop respectively. The environment provides an input variable `distance`, which is an integer value ranging from 0 to 100.

The specification defines the condition "forward" as occurring when both `leftM` and `rightM` are set to FWD simultaneously.

The system must satisfy the following guarantee regarding proximity safety: At all times, if the current `distance` value is less than or equal to 20, then in the immediately next state, the system must not be in the "forward" condition. This means that whenever the measured distance is 20 or less, the subsequent motor commands cannot have both `leftM` and `rightM` set to FWD.