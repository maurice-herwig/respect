

Specification name: TrafficE2

Environment variables:
- carA: boolean
- carB: boolean
- emergency: boolean

System variables:
- greenA: boolean
- greenB: boolean

This specification defines a traffic light controller managing two lanes, A and B, subject to an emergency signal.

**Initial Conditions**
At the start of operation, no cars are present in either lane, no emergency is active, and both traffic lights are not green.

**Environment Assumptions**
The environment controls the presence of cars and the emergency status. Cars in lane A and cars in lane B appear infinitely often. The emergency status clears infinitely often. Regarding vehicle movement, if a car is present in a lane while that lane's light is not green, the car remains present in the next step. If a car is present in a lane while that lane's light is green, the car departs in the next step.

**System Guarantees**
The system controls the green light status for each lane. The system must ensure that light A and light B are never green simultaneously. If an emergency occurs, both lights must not be green. Additionally, the system must ensure that light A becomes green infinitely often and light B becomes green infinitely often.