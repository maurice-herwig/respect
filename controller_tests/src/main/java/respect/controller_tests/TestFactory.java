package respect.controller_tests;

import java.util.Map;

import respect.controller_tests.tests.AlwaysImplicationTest;
import respect.controller_tests.tests.EventuallyResponseTest;
import respect.controller_tests.tests.ExclusionTest;
import respect.controller_tests.tests.InitialConditionTest;
import respect.controller_tests.tests.InvariantTest;
import respect.controller_tests.tests.MutualExclusionTest;
import respect.controller_tests.tests.OneHotTest;
import respect.controller_tests.tests.PersistenceTest;
import respect.controller_tests.tests.ResponseAbsenceTest;
import respect.controller_tests.tests.StateSequenceTest;
import respect.controller_tests.tests.VariableOwnershipTest;

public final class TestFactory {
    private TestFactory() {
    }

    public static TestCase create(Map<String, Object> config) {
        String kind = TestUtil.requiredString(config, "kind");
        switch (kind) {
            case "variable_ownership":
                return new VariableOwnershipTest(config);
            case "initial_condition":
                return new InitialConditionTest(config);
            case "exclusion":
                return new ExclusionTest(config);
            case "always_implication":
                return new AlwaysImplicationTest(config);
            case "eventually_response":
                return new EventuallyResponseTest(config);
            case "mutual_exclusion":
                return new MutualExclusionTest(config);
            case "one_hot":
                return new OneHotTest(config);
            case "invariant":
                return new InvariantTest(config);
            case "state_sequence":
                return new StateSequenceTest(config);
            case "persistence":
                return new PersistenceTest(config);
            case "response_absence":
                return new ResponseAbsenceTest(config);
            default:
                throw new IllegalArgumentException("Unsupported test kind: " + kind);
        }
    }
}
