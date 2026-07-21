package respect.controller_tests.tests;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import respect.controller_tests.ControllerHarness;
import respect.controller_tests.Json;
import respect.controller_tests.StepResult;
import respect.controller_tests.TestCase;
import respect.controller_tests.TestContext;
import respect.controller_tests.TestResult;
import respect.controller_tests.TestUtil;

public final class StateSequenceTest implements TestCase {
    private final String name;
    private final List<Map<String, String>> trace;
    private final List<Map<String, String>> expect;

    public StateSequenceTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "state_sequence");
        this.trace = TestUtil.trace(config);
        this.expect = parseExpect(config.get("expect"));
    }

    @Override
    public TestResult run(TestContext context) throws Exception {
        if (trace.size() != expect.size()) {
            Map<String, Object> details = TestUtil.failureDetails("state_sequence_length_mismatch");
            details.put("trace_length", trace.size());
            details.put("expect_length", expect.size());
            return TestResult.fail(name, "state_sequence", "Trace and expect lengths differ", null, details);
        }
        ControllerHarness harness = context.newHarness();
        List<Map<String, Object>> observed = new ArrayList<>();
        for (int i = 0; i < trace.size(); i++) {
            StepResult step = harness.step(trace.get(i));
            observed.add(step.toJson());
            Map<String, String> combined = step.combined();
            Map<String, String> expected = expect.get(i);
            if (!TestUtil.matches(combined, expected)) {
                Map<String, Object> details = TestUtil.failureDetails("state_sequence_mismatch");
                details.put("step_index", i);
                details.put("expected", expected);
                details.put("actual_combined", combined);
                details.put("missing_or_different", TestUtil.missingOrDifferentVariables(combined, expected));
                return TestResult.fail(
                    name,
                    "state_sequence",
                    "Expected sequence valuation did not match at step " + i,
                    observed,
                    details
                );
            }
        }
        return TestResult.pass(name, "state_sequence");
    }

    private static List<Map<String, String>> parseExpect(Object value) {
        List<Map<String, String>> result = new ArrayList<>();
        for (Object item : Json.asArray(value, "expect")) {
            result.add(TestUtil.stringMap(item));
        }
        return result;
    }
}
