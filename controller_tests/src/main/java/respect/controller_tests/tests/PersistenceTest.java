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

public final class PersistenceTest implements TestCase {
    private final String name;
    private final Map<String, String> when;
    private final Map<String, String> maintain;
    private final Map<String, String> until;
    private final List<List<Map<String, String>>> traces;

    public PersistenceTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "persistence");
        this.when = TestUtil.stringMap(config.get("when"));
        this.maintain = TestUtil.stringMap(config.get("maintain"));
        this.until = TestUtil.stringMap(config.get("until"));
        this.traces = Exploration.traces(config);
    }

    @Override
    public TestResult run(TestContext context) throws Exception {
        boolean triggerObserved = false;
        for (int traceIndex = 0; traceIndex < traces.size(); traceIndex++) {
            ControllerHarness harness = context.newHarness();
            List<Map<String, Object>> observed = new ArrayList<>();
            boolean active = false;
            Integer triggerStep = null;
            List<Map<String, String>> trace = traces.get(traceIndex);
            for (int i = 0; i < trace.size(); i++) {
                StepResult step = harness.step(trace.get(i));
                observed.add(step.toJson());
                Map<String, String> combined = step.combined();
                if (!active && TestUtil.matches(combined, when)) {
                    active = true;
                    triggerObserved = true;
                    triggerStep = i;
                }
                if (active && !until.isEmpty() && TestUtil.matches(combined, until)) {
                    active = false;
                    triggerStep = null;
                    continue;
                }
                if (active && !TestUtil.matches(combined, maintain)) {
                    Map<String, Object> details = TestUtil.failureDetails("persistence_violation");
                    details.put("trace_index", traceIndex);
                    details.put("trigger_step", triggerStep);
                    details.put("step_index", i);
                    details.put("when", when);
                    details.put("maintain", maintain);
                    details.put("until", until);
                    details.put("actual_combined", combined);
                    details.put("missing_or_different", TestUtil.missingOrDifferentVariables(combined, maintain));
                    return TestResult.fail(
                        name,
                        "persistence",
                        "Persistence condition was not maintained at trace " + traceIndex + ", step " + i,
                        observed,
                        details
                    );
                }
            }
        }
        if (!triggerObserved) {
            Map<String, Object> details = TestUtil.failureDetails("trigger_not_observed");
            details.put("when", when);
            details.put("maintain", maintain);
            details.put("traces_explored", traces.size());
            return TestResult.fail(name, "persistence", "Trigger valuation was not observed in any explored trace", null, details);
        }
        return TestResult.pass(name, "persistence");
    }
}
