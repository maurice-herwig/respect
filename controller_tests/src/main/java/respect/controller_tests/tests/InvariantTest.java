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

public final class InvariantTest implements TestCase {
    private final String name;
    private final Map<String, String> condition;
    private final List<List<Map<String, String>>> traces;

    public InvariantTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "invariant");
        this.condition = TestUtil.stringMap(config.get("condition"));
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
                if (!TestUtil.matches(combined, condition)) {
                    Map<String, Object> details = TestUtil.failureDetails("invariant_violation");
                    details.put("trace_index", traceIndex);
                    details.put("step_index", i);
                    details.put("condition", condition);
                    details.put("actual_combined", combined);
                    details.put("missing_or_different", TestUtil.missingOrDifferentVariables(combined, condition));
                    return TestResult.fail(
                        name,
                        "invariant",
                        "Invariant violated at trace " + traceIndex + ", step " + i,
                        observed,
                        details
                    );
                }
            }
        }
        return TestResult.pass(name, "invariant");
    }
}
