package respect.controller_tests.tests;

import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

import respect.controller_tests.TestCase;
import respect.controller_tests.TestContext;
import respect.controller_tests.TestResult;
import respect.controller_tests.TestUtil;

public final class VariableOwnershipTest implements TestCase {
    private final String name;
    private final List<String> env;
    private final List<String> sys;

    public VariableOwnershipTest(Map<String, Object> config) {
        this.name = TestUtil.optionalName(config, "variable_ownership");
        this.env = TestUtil.stringList(config.get("env"), "env");
        this.sys = TestUtil.stringList(config.get("sys"), "sys");
    }

    @Override
    public TestResult run(TestContext context) throws Exception {
        if (context.spectraFile() == null) {
            return TestResult.fail(name, "variable_ownership", "spectra_file is required", null);
        }
        String source = Files.readString(context.spectraFile());
        List<String> missing = new ArrayList<>();
        for (String variable : env) {
            if (!declared(source, "env", variable)) {
                missing.add("env " + variable);
            }
        }
        for (String variable : sys) {
            if (!declared(source, "sys", variable)) {
                missing.add("sys " + variable);
            }
        }
        if (!missing.isEmpty()) {
            return TestResult.fail(name, "variable_ownership", "Missing or wrong ownership: " + missing, null);
        }
        return TestResult.pass(name, "variable_ownership");
    }

    private static boolean declared(String source, String owner, String variable) {
        // Handles simple declarations such as "env boolean carA;" and finite-domain declarations.
        String regex = "(?m)^\\s*" + Pattern.quote(owner) + "\\s+(?:[A-Za-z_][A-Za-z0-9_]*\\s+)?"
            + Pattern.quote(variable) + "\\s*(?:;|\\{|=)";
        return Pattern.compile(regex).matcher(source).find();
    }
}
