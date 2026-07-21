package respect.controller_tests.tests;

import java.util.List;
import java.util.Map;

import respect.controller_tests.ControllerHarness;
import respect.controller_tests.StepResult;
import respect.controller_tests.TestCase;
import respect.controller_tests.TestContext;
import respect.controller_tests.TestResult;
import respect.controller_tests.TestUtil;

public final class InitialConditionTest implements TestCase {
    private final String name;
    private final Map<String, String> inputs;
    private final Map<String, String> expected;

    public InitialConditionTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "initial_condition");
        this.inputs = TestUtil.stringMap(config.get("inputs"));
        this.expected = TestUtil.stringMap(config.get("expected"));
    }

    @Override
    public TestResult run(TestContext context) throws Exception {
        ControllerHarness harness = context.newHarness();
        StepResult step = harness.step(inputs);
        if (!TestUtil.matches(step.combined(), expected)) {
            Map<String, String> combined = step.combined();
            Map<String, Object> details = TestUtil.failureDetails("initial_condition_mismatch");
            details.put("inputs", inputs);
            details.put("expected", expected);
            details.put("actual_combined", combined);
            details.put("missing_or_different", TestUtil.missingOrDifferentVariables(combined, expected));
            return TestResult.fail(
                name,
                "initial_condition",
                "Initial condition did not match expected valuation",
                List.of(step.toJson()),
                details
            );
        }
        return TestResult.pass(name, "initial_condition");
    }
}
