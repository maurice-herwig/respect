package respect.controller_tests.tests;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import respect.controller_tests.ControllerHarness;
import respect.controller_tests.Exploration;
import respect.controller_tests.StepResult;
import respect.controller_tests.TestCase;
import respect.controller_tests.TestContext;
import respect.controller_tests.TestResult;
import respect.controller_tests.TestUtil;

public final class ResponseAbsenceTest implements TestCase {
    private final String name;
    private final Map<String, String> when;
    private final Map<String, String> absent;
    private final int forSteps;
    private final List<List<Map<String, String>>> traces;

    public ResponseAbsenceTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "response_absence");
        this.when = TestUtil.stringMap(config.get("when"));
        this.absent = TestUtil.stringMap(config.get("absent"));
        this.forSteps = TestUtil.intValue(config.get("for_steps"), 1);
        this.traces = Exploration.traces(config);
    }

    @Override
    public TestResult run(TestContext context) throws Exception {
        boolean triggerObserved = false;
        for (int traceIndex = 0; traceIndex < traces.size(); traceIndex++) {
            ControllerHarness harness = context.newHarness();
            List<Map<String, Object>> observed = new ArrayList<>();
            int remaining = 0;
            Integer triggerStep = null;
            List<Map<String, String>> trace = traces.get(traceIndex);
            for (int i = 0; i < trace.size(); i++) {
                StepResult step = harness.step(trace.get(i));
                observed.add(step.toJson());
                Map<String, String> combined = step.combined();
                if (TestUtil.matches(combined, when)) {
                    remaining = forSteps;
                    triggerStep = i;
                    triggerObserved = true;
                }
                if (remaining > 0 && TestUtil.matches(combined, absent)) {
                    Map<String, Object> details = TestUtil.failureDetails("response_absence_violation");
                    details.put("trace_index", traceIndex);
                    details.put("trigger_step", triggerStep);
                    details.put("step_index", i);
                    details.put("for_steps", forSteps);
                    details.put("when", when);
                    details.put("absent", absent);
                    details.put("actual_combined", combined);
                    details.put("matched_variables", TestUtil.matchedVariables(combined, absent));
                    return TestResult.fail(
                        name,
                        "response_absence",
                        "Forbidden response occurred during absence window at trace " + traceIndex + ", step " + i,
                        observed,
                        details
                    );
                }
                if (remaining > 0) {
                    remaining--;
                }
            }
        }
        if (!triggerObserved) {
            Map<String, Object> details = TestUtil.failureDetails("trigger_not_observed");
            details.put("when", when);
            details.put("absent", absent);
            details.put("traces_explored", traces.size());
            return TestResult.fail(name, "response_absence", "Trigger valuation was not observed in any explored trace", null, details);
        }
        return TestResult.pass(name, "response_absence");
    }
}
