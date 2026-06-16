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
            Map<String, Object> config = Json.asObject(testObject, "test");
            TestCase test = TestFactory.create(config);
            TestResult result = test.run(context);
            if (result.passed()) {
                passed++;
            }
            results.add(result.toJson());
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
