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

public final class EventuallyResponseTest implements TestCase {
    private final String name;
    private final Map<String, String> when;
    private final Map<String, String> eventually;
    private final int withinSteps;
    private final List<Map<String, String>> trace;

    public EventuallyResponseTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "eventually_response");
        this.when = TestUtil.stringMap(config.get("when"));
        this.eventually = TestUtil.stringMap(config.get("eventually"));
        this.withinSteps = TestUtil.intValue(config.get("within_steps"), 10);
        this.trace = TestUtil.trace(config);
    }

    @Override
    public TestResult run(TestContext context) throws Exception {
        ControllerHarness harness = context.newHarness();
        List<Map<String, Object>> observed = new ArrayList<>();
        Integer deadline = when.isEmpty() ? withinSteps : null;

        for (int i = 0; i < trace.size(); i++) {
            StepResult step = harness.step(trace.get(i));
            observed.add(step.toJson());
            Map<String, String> combined = step.combined();
            // Start the bounded response window once the trigger valuation is observed.
            if (deadline == null && TestUtil.matches(combined, when)) {
                deadline = withinSteps;
            }
            if (deadline != null && TestUtil.matches(combined, eventually)) {
                return TestResult.pass(name, "eventually_response");
            }
            if (deadline != null) {
                deadline--;
                if (deadline < 0) {
                    return TestResult.fail(name, "eventually_response", "Expected response did not occur within " + withinSteps + " steps", observed);
                }
            }
        }
        return TestResult.fail(name, "eventually_response", "Expected response did not occur in provided trace", observed);
    }
}
