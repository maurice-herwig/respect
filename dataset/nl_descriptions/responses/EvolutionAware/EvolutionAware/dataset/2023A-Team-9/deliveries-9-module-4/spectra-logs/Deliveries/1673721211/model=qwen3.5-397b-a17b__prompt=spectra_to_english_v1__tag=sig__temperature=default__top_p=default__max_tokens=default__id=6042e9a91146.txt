

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- elevator: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY
- elevatorAndGround0: boolean
- elevatorAndGround1: boolean

**Requirements Description**

The system controls the coordinates of two robots (Robot 0 and Robot 1) and two boolean status flags, while the environment controls the position of an elevator. The system must satisfy the following initial conditions and behavioral guarantees:

**Initial Conditions**
Upon system initialization, both `elevatorAndGround0` and `elevatorAndGround1` are false.

**Behavioral Guarantees**
The system must update the boolean status flags based on the vertical movement of the robots according to these rules:

1.  **Setting `elevatorAndGround0`:** If Robot 0 transitions to a Y-coordinate of 5 from a current Y-coordinate less than 5, then `elevatorAndGround0` must become true in the next state.
2.  **Holding `elevatorAndGround0`:** If Robot 1 does not transition to a Y-coordinate of 5 from a current Y-coordinate less than 5, then `elevatorAndGround0` must retain its current value in the next state.
3.  **Setting `elevatorAndGround1`:** If Robot 1 transitions to a Y-coordinate of 5 from a current Y-coordinate less than 5, then `elevatorAndGround1` must become true in the next state.
4.  **Holding `elevatorAndGround1`:** If Robot 0 does not transition to a Y-coordinate of 5 from a current Y-coordinate less than 5, then `elevatorAndGround1` must retain its current value in the next state.