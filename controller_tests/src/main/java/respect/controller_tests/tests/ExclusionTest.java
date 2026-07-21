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

public final class ExclusionTest implements TestCase {
    private final String name;
    private final Map<String, String> forbidden;
    private final List<List<Map<String, String>>> traces;

    public ExclusionTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "exclusion");
        this.forbidden = TestUtil.stringMap(config.get("forbidden"));
        this.traces = Exploration.traces(config);
    }

    @Override
    public TestResult run(TestContext context) throws Exception {
        for (int traceIndex = 0; traceIndex < traces.size(); traceIndex++) {
            ControllerHarness harness = context.newHarness();
            List<Map<String, Object>> observed = new ArrayList<>();
            List<Map<String, String>> trace = traces.get(traceIndex);
            for (int i = 0; i < trace.size(); i++) {
                StepResult step = harness.step(trace.get(i));
                observed.add(step.toJson());
                // Exclusion checks safety-style requirements: this valuation must never appear.
                if (TestUtil.matches(step.combined(), forbidden)) {
                    Map<String, String> combined = step.combined();
                    Map<String, Object> details = TestUtil.failureDetails("forbidden_valuation_reached");
                    details.put("trace_index", traceIndex);
                    details.put("step_index", i);
                    details.put("forbidden", forbidden);
                    details.put("actual_combined", combined);
                    details.put("matched_variables", TestUtil.matchedVariables(combined, forbidden));
                    return TestResult.fail(
                        name,
                        "exclusion",
                        "Forbidden valuation reached at trace " + traceIndex + ", step " + i,
                        observed,
                        details
                    );
                }
            }
        }
        return TestResult.pass(name, "exclusion");
    }
}
