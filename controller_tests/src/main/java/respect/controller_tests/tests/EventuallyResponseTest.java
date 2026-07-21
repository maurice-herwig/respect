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

public final class EventuallyResponseTest implements TestCase {
    private final String name;
    private final Map<String, String> when;
    private final Map<String, String> eventually;
    private final int withinSteps;
    private final boolean requireClosedObligations;
    private final List<List<Map<String, String>>> traces;

    public EventuallyResponseTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "eventually_response");
        this.when = TestUtil.stringMap(config.get("when"));
        this.eventually = TestUtil.stringMap(config.get("eventually"));
        this.withinSteps = TestUtil.intValue(config.get("within_steps"), 10);
        this.requireClosedObligations = TestUtil.booleanValue(config.get("require_closed_obligations"), false);
        this.traces = Exploration.traces(config);
    }

    @Override
    public TestResult run(TestContext context) throws Exception {
        boolean triggerObserved = false;
        for (int traceIndex = 0; traceIndex < traces.size(); traceIndex++) {
            ControllerHarness harness = context.newHarness();
            List<Map<String, Object>> observed = new ArrayList<>();
            Integer deadline = when.isEmpty() ? withinSteps : null;
            Integer triggerStep = deadline != null ? 0 : null;
            triggerObserved = triggerObserved || deadline != null;
            List<Map<String, String>> trace = traces.get(traceIndex);

            for (int i = 0; i < trace.size(); i++) {
                StepResult step = harness.step(trace.get(i));
                observed.add(step.toJson());
                Map<String, String> combined = step.combined();
                // Start the bounded response window once the trigger valuation is observed.
                if (deadline == null && TestUtil.matches(combined, when)) {
                    deadline = withinSteps;
                    triggerStep = i;
                    triggerObserved = true;
                }
                if (deadline != null && TestUtil.matches(combined, eventually)) {
                    deadline = null;
                    triggerStep = null;
                }
                if (deadline != null) {
                    deadline--;
                    if (deadline < 0) {
                        Map<String, Object> details = TestUtil.failureDetails("response_timeout");
                        details.put("trace_index", traceIndex);
                        details.put("trigger_step", triggerStep);
                        details.put("failed_at_step", i);
                        details.put("within_steps", withinSteps);
                        details.put("when", when);
                        details.put("eventually", eventually);
                        details.put("last_actual_combined", combined);
                        details.put("missing_or_different", TestUtil.missingOrDifferentVariables(combined, eventually));
                        return TestResult.fail(
                            name,
                            "eventually_response",
                            "Expected response did not occur within " + withinSteps + " steps at trace " + traceIndex,
                            observed,
                            details
                        );
                    }
                }
            }
            if (deadline != null && requireClosedObligations) {
                Map<String, Object> details = TestUtil.failureDetails("open_response_obligation");
                details.put("trace_index", traceIndex);
                details.put("trigger_step", triggerStep);
                details.put("within_steps", withinSteps);
                details.put("when", when);
                details.put("eventually", eventually);
                details.put("remaining_steps", deadline);
                return TestResult.fail(
                    name,
                    "eventually_response",
                    "Trace ended before expected response occurred at trace " + traceIndex,
                    observed,
                    details
                );
            }
        }
        if (!triggerObserved) {
            Map<String, Object> details = TestUtil.failureDetails("trigger_not_observed");
            details.put("when", when);
            details.put("eventually", eventually);
            details.put("traces_explored", traces.size());
            return TestResult.fail(name, "eventually_response", "Trigger valuation was not observed in any explored trace", null, details);
        }
        return TestResult.pass(name, "eventually_response");
    }
}
