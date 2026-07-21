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

public final class MutualExclusionTest implements TestCase {
    private final String name;
    private final List<String> variables;
    private final String activeValue;
    private final List<List<Map<String, String>>> traces;

    public MutualExclusionTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "mutual_exclusion");
        this.variables = TestUtil.stringList(config.get("variables"), "variables");
        this.activeValue = TestUtil.stringValue(config.get("active_value"), "true");
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
                Map<String, String> combined = step.combined();
                List<String> active = activeVariables(combined);
                if (active.size() > 1) {
                    Map<String, Object> details = TestUtil.failureDetails("mutual_exclusion_violation");
                    details.put("trace_index", traceIndex);
                    details.put("step_index", i);
                    details.put("variables", variables);
                    details.put("active_value", activeValue);
                    details.put("active_variables", active);
                    details.put("actual_combined", combined);
                    return TestResult.fail(
                        name,
                        "mutual_exclusion",
                        "More than one mutually exclusive variable is active at trace " + traceIndex + ", step " + i,
                        observed,
                        details
                    );
                }
            }
        }
        return TestResult.pass(name, "mutual_exclusion");
    }

    private List<String> activeVariables(Map<String, String> combined) {
        List<String> active = new ArrayList<>();
        for (String variable : variables) {
            if (activeValue.equals(combined.get(variable))) {
                active.add(variable);
            }
        }
        return active;
    }
}
