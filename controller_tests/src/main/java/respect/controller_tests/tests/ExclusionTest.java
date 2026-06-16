package respect.controller_tests.tests;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import respect.controller_tests.ControllerHarness;
import respect.controller_tests.StepResult;
import respect.controller_tests.TestCase;
import respect.controller_tests.TestContext;
import respect.controller_tests.TestResult;
import respect.controller_tests.TestUtil;

public final class ExclusionTest implements TestCase {
    private final String name;
    private final Map<String, String> forbidden;
    private final List<Map<String, String>> trace;

    public ExclusionTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "exclusion");
        this.forbidden = TestUtil.stringMap(config.get("forbidden"));
        this.trace = TestUtil.trace(config);
    }

    @Override
    public TestResult run(TestContext context) throws Exception {
        ControllerHarness harness = context.newHarness();
        List<Map<String, Object>> observed = new ArrayList<>();
        for (int i = 0; i < trace.size(); i++) {
            StepResult step = harness.step(trace.get(i));
            observed.add(step.toJson());
            // Exclusion checks safety-style requirements: this valuation must never appear.
            if (TestUtil.matches(step.combined(), forbidden)) {
                return TestResult.fail(name, "exclusion", "Forbidden valuation reached at step " + i, observed);
            }
        }
        return TestResult.pass(name, "exclusion");
    }
}
