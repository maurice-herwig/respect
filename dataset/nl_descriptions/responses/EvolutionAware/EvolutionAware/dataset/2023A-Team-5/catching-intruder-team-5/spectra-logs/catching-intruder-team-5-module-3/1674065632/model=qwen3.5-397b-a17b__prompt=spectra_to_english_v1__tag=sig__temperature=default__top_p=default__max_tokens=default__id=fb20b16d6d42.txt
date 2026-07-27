

Specification name: Module3

Named domains:
- Dim: Int(0..D)

Environment variables:
- intruderX: Dim
- intruderY: Dim

System variables:
- robotX0: Dim
- robotY0: Dim
- robotX1: Dim
- robotY1: Dim

**Requirements Description**

The system controls the coordinates of two robots within a bounded grid while monitoring an intruder. All coordinate variables range over the domain Dim, which consists of integers from 0 to 7.

**Environment Assumptions**
The environment must adhere to the following safety constraint at all times: whenever the intruder's vertical coordinate `intruderY` equals 1, the intruder's horizontal coordinate `intruderX` must be either less than 2 or greater than 5.

**System Guarantees**
The system must ensure the following safety constraints hold at all times:
1. Whenever Robot 0's vertical coordinate `robotY0` equals 1, Robot 0's horizontal coordinate `robotX0` must be either less than 2 or greater than 5.
2. Whenever Robot 1's vertical coordinate `robotY1` equals 1, Robot 1's horizontal coordinate `robotX1` must be either less than 2 or greater than 5.