

Specification name: TrafficE2

Environment variables:
- carA: boolean
- carB: boolean

System variables:
- greenA: boolean
- greenB: boolean

The system controls the boolean outputs `greenA` and `greenB` in response to the boolean inputs `carA` and `carB` provided by the environment. It is assumed that the environment will set the input `carA` to true infinitely often over time. Likewise, the environment must set the input `carB` to true infinitely often.

The system must ensure that the outputs `greenA` and `greenB` are never true simultaneously. Additionally, the system must guarantee that the output `greenA` becomes true infinitely often. Finally, the system must guarantee that the output `greenB` becomes true infinitely often.