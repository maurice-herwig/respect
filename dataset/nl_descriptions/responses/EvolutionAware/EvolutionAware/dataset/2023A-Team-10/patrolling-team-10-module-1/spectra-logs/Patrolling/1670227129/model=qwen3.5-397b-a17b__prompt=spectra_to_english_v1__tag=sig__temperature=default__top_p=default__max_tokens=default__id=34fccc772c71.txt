

Specification name: Patrolling

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Dim: Int(0..4)

Environment variables:
- isGoalBlocked: boolean[3]
- goals: Dim[3][2]

System variables:
- robotX: DimX
- robotY: DimY

The system controls the robot's position on a grid using the variables `robotX` and `robotY`, which represent coordinates within the defined dimensions where DX and DY are equal to 4. The environment provides the locations of three goals via the `goals` array and indicates the availability of each goal using the `isGoalBlocked` boolean array. Regarding environment behavior, the specification assumes that for each of the three goals, the blocked status fluctuates over time; specifically, the environment must indicate that each goal is blocked infinitely often and indicate that each goal is not blocked infinitely often.