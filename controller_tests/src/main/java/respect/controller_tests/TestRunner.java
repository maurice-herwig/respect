package respect.controller_tests;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class TestRunner {
    private TestRunner() {
    }

    public static void main(String[] args) throws Exception {
        Arguments parsedArgs = Arguments.parse(args);
        Map<String, Object> plan = Json.asObject(Json.parse(Files.readString(parsedArgs.plan)), "test plan");
        TestContext context = TestContext.fromPlan(plan);
        List<Object> testObjects = Json.asArray(plan.get("tests"), "tests");

        // Execute tests independently; each controller test gets a fresh executor via TestContext.
        List<Map<String, Object>> results = new ArrayList<>();
        int passed = 0;
        for (Object testObject : testObjects) {
            TestResult result = runOneTest(testObject, context);
            if (result.passed()) {
                passed++;
            }
            Map<String, Object> resultJson = result.toJson();
            if (testObject instanceof Map<?, ?>) {
                addMetadata(resultJson, Json.asObject(testObject, "test"));
            }
            results.add(resultJson);
        }

        // Keep stdout machine-readable so agents and batch scripts can parse the result directly.
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("status", passed == results.size() ? "passed" : "failed");
        summary.put("passed", passed);
        summary.put("failed", results.size() - passed);
        summary.put("total", results.size());
        summary.put("results", results);

        String json = Json.stringify(summary);
        if (parsedArgs.output != null) {
            Path parent = parsedArgs.output.toAbsolutePath().getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            Files.writeString(parsedArgs.output, json + System.lineSeparator());
        }
        System.out.println(json);
        if (passed != results.size()) {
            // Non-zero exit lets reconstruction scripts treat failed tests as actionable feedback.
            System.exit(1);
        }
    }

    private static TestResult runOneTest(Object testObject, TestContext context) {
        Map<String, Object> config;
        try {
            config = Json.asObject(testObject, "test");
        } catch (Exception exc) {
            Map<String, Object> details = TestUtil.failureDetails("invalid_test_plan_entry");
            details.put("exception_type", exc.getClass().getName());
            details.put("message", String.valueOf(exc.getMessage()));
            return TestResult.fail("invalid_test", "invalid_plan", "Test entry is not a JSON object", null, details);
        }

        try {
            String kind = TestUtil.stringValue(config.get("kind"), "missing_kind");
            String name = TestUtil.optionalName(config, kind);
            if (requiresRequirement(kind) && TestUtil.stringValue(config.get("requirement"), "").isBlank()) {
                Map<String, Object> details = TestUtil.failureDetails("missing_requirement");
                details.put("test_name", name);
                details.put("kind", kind);
                details.put("hint", "Add a requirement field that quotes or closely paraphrases the natural-language requirement justifying this test.");
                return TestResult.fail(name, kind, "Runtime test is missing requirement", null, details);
            }
            TestCase test = TestFactory.create(config);
            return test.run(context);
        } catch (Exception exc) {
            String kind = safeString(config.get("kind"), "invalid_kind");
            String name = safeString(config.get("name"), kind);
            Map<String, Object> details = TestUtil.failureDetails("test_execution_error");
            details.put("test_name", name);
            details.put("kind", kind);
            details.put("exception_type", exc.getClass().getName());
            details.put("message", String.valueOf(exc.getMessage()));
            return TestResult.fail(name, kind, "Test execution failed: " + exc.getClass().getSimpleName(), null, details);
        }
    }

    private static String safeString(Object value, String fallback) {
        try {
            return TestUtil.stringValue(value, fallback);
        } catch (Exception exc) {
            return fallback;
        }
    }

    private static boolean requiresRequirement(String kind) {
        return !"variable_ownership".equals(kind);
    }

    private static void addMetadata(Map<String, Object> resultJson, Map<String, Object> config) {
        Object requirement = config.get("requirement");
        if (requirement != null) {
            resultJson.put("requirement", TestUtil.stringValue(requirement, null));
        }
    }

    private static final class Arguments {
        private final Path plan;
        private final Path output;

        private Arguments(Path plan, Path output) {
            this.plan = plan;
            this.output = output;
        }

        static Arguments parse(String[] args) {
            Path plan = null;
            Path output = null;
            for (int i = 0; i < args.length; i++) {
                if ("--plan".equals(args[i]) && i + 1 < args.length) {
                    plan = Path.of(args[++i]);
                } else if ("--output".equals(args[i]) && i + 1 < args.length) {
                    output = Path.of(args[++i]);
                } else {
                    throw new IllegalArgumentException("Unknown or incomplete argument: " + args[i]);
                }
            }
            if (plan == null) {
                throw new IllegalArgumentException("Missing required --plan <file>");
            }
            return new Arguments(plan, output);
        }
    }
}
