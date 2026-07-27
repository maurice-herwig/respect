

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)
- guardDim: Int(0..6)

Environment variables:
- guardX: guardDim
- guardY: guardDim

System variables:
- robotX: Dim
- robotY: Dim

The system controls a robot navigating a two-dimensional grid defined by the domain Dim, where the constant D equals 7. The environment provides input variables representing guard positions, while the system determines the robot's coordinates via the variables robotX and robotY.

Initially, the robot starts at the position where robotX is 7 and robotY is 0.

Regarding movement safety, the robot's position must update gradually. At every step, the value of robotX and the value of robotY may either remain the same, increase by exactly one, or decrease by exactly one relative to their current values.

The system must ensure collision avoidance by never allowing the robot to occupy specific obstacle coordinates. The robot is prohibited from being at positions (2, 2), (2, 3), (2, 4), or (2, 5) at any time.

Additionally, the system must satisfy liveness requirements by visiting three specific target locations infinitely often during operation. The robot must infinitely often reach target T1 at coordinates (0, 0), target T2 at coordinates (7, 7), and target T3 at coordinates (0, 7).