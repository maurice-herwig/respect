

Specification name: TrafficE2

Environment variables:
- cara: boolean
- carb: boolean
- emergency: boolean

System variables:
- greena: boolean
- greenb: boolean

The system controls two traffic light signals, `greena` and `greenb`, based on environment inputs indicating car presence (`cara`, `carb`) and an `emergency` signal.

**Environment Assumptions**
The environment must adhere to the following constraints regarding car signals and the emergency status:
1.  **Car A Presence:** Whenever `greena` is false, `cara` must be true in the immediately following step.
2.  **Car B Presence:** Whenever `greenb` is false and `emergency` is false, `carb` must be true in the immediately following step.
3.  **Car A Movement:** If `emergency` is false, `cara` is true, and `greena` is true, then `cara` must become false in the immediately following step.
4.  **Car B Movement:** If `emergency` is false, `carb` is true, and `greenb` is true, then `carb` must become false in the immediately following step.

**System Guarantees**
The system must satisfy the following requirements whenever the environment satisfies the assumptions:
1.  **Mutual Exclusion:** It is always the case that either `greena` is false or `greenb` is false. The system must never set both `greena` and `greenb` to true simultaneously.
2.  **Response to Car A:** Whenever `cara` is true, `greena` must eventually become true. The system tracks requests from `cara` and ensures `greena` is asserted to clear the request.
3.  **Response to Car B:** Whenever `carb` is true, `greenb` must eventually become true. The system tracks requests from `carb` and ensures `greenb` is asserted to clear the request.

**Initial Conditions**
Upon system start, the internal logic governing the response to car requests is initialized to a ready state, prepared to detect and respond to incoming car signals.