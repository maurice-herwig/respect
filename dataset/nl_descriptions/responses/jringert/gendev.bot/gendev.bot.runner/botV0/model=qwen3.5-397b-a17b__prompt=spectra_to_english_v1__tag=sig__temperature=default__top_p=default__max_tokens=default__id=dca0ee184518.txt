

Specification name: BotV0

Named domains:
- MotorCmd: {FWD, BWD, STP}

Environment variables:
- none

System variables:
- leftM: MotorCmd
- rightM: MotorCmd

**Requirements Description**

The system controls two output variables, `leftM` and `rightM`, each representing a motor command. These variables take values from the MotorCmd domain, which consists of FWD, BWD, and STP. There are no environment-controlled input variables. The system must ensure that initially, both `leftM` and `rightM` are set to STP.