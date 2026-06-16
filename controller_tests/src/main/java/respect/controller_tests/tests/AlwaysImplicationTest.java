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

public final class AlwaysImplicationTest implements TestCase {
    private final String name;
    private final Map<String, String> when;
    private final Map<String, String> then;
    private final List<Map<String, String>> trace;

    public AlwaysImplicationTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "always_implication");
        this.when = TestUtil.stringMap(config.get("when"));
        this.then = TestUtil.stringMap(config.get("then"));
        this.trace = TestUtil.trace(config);
    }

    @Override
    public TestResult run(TestContext context) throws Exception {
        ControllerHarness harness = context.newHarness();
        List<Map<String, Object>> observed = new ArrayList<>();
        for (int i = 0; i < trace.size(); i++) {
            StepResult step = harness.step(trace.get(i));
            observed.add(step.toJson());
            Map<String, String> combined = step.combined();
            // Safety implication: whenever the trigger holds, the consequence must hold immediately.
            if (TestUtil.matches(combined, when) && !TestUtil.matches(combined, then)) {
                return TestResult.fail(name, "always_implication", "Implication violated at step " + i, observed);
            }
        }
        return TestResult.pass(name, "always_implication");
    }
}
