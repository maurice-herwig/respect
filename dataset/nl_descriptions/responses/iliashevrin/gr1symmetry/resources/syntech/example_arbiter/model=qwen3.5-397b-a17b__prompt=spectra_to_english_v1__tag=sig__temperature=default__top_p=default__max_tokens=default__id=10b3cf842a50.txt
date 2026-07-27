

Specification name: SymmetryExample

Environment variables:
- request: boolean[N]

System variables:
- grant: boolean[N]

The system functions as an arbiter managing access for three clients, indexed 0 to 2. The environment controls the `request` array, indicating when each client seeks access. The system controls the `grant` array, indicating when each client is allowed access.

**Environment Assumptions**
1.  **Request Persistence:** For any client index `i`, if the client is waiting (meaning `request[i]` is true and `grant[i]` is false), the environment must keep `request[i]` true in the next step.
2.  **Eventual Release:** For any client index `i`, the client does not hold the resource forever. Infinitely often, it is not the case that both `request[i]` and `grant[i]` are true simultaneously.

**System Guarantees**
1.  **Mutual Exclusion:** At any time, at most one client may be granted. For any distinct indices `i` and `j`, it is never the case that both `grant[i]` and `grant[j]` are true simultaneously.
2.  **Grant Persistence:** For any client index `i`, if the client is currently holding the resource (both `request[i]` and `grant[i]` are true), the system must ensure `grant[i]` remains true in the next step.
3.  **Eventual Grant:** For any client index `i`, the client does not wait forever. Infinitely often, it is not the case that the client is waiting (meaning `request[i]` is true and `grant[i]` is false).
4.  **Priority:** Client 0 has priority over clients 1 and 2. For any client index `i` from 1 to 2, if `grant[i]` becomes true (transitioning from false to true), then client 0 must not be waiting at that time.