package respect.controller_tests;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class ControllerTraceRunner {
    private ControllerTraceRunner() {
    }

    public static void main(String[] args) throws Exception {
        Arguments parsedArgs = Arguments.parse(args);
        Map<String, Object> plan = Json.asObject(Json.parse(Files.readString(parsedArgs.plan)), "trace plan");
        Map<String, Object> controller = Json.asObject(plan.get("controller"), "controller");
        String controllerDir = TestUtil.requiredString(controller, "controller_dir");
        String specName = TestUtil.requiredString(controller, "spec_name");
        Set<String> outputs = new LinkedHashSet<>(TestUtil.stringList(plan.get("outputs"), "outputs"));
        if (outputs.isEmpty()) {
            throw new IllegalArgumentException("outputs must contain at least one variable");
        }

        List<Object> traceResults = new ArrayList<>();
        List<List<Map<String, String>>> traces = Exploration.traces(plan);
        for (List<Map<String, String>> inputTrace : traces) {
            ControllerHarness harness = new ControllerHarness(controllerDir, specName, outputs);
            List<Object> steps = new ArrayList<>();
            try {
                for (Map<String, String> inputs : inputTrace) {
                    steps.add(harness.step(inputs).toJson());
                }
            } finally {
                harness.free();
            }
            traceResults.add(steps);
        }

        Map<String, Object> value = new LinkedHashMap<>();
        value.put("status", "success");
        value.put("total_traces", traces.size());
        value.put("traces", traceResults);
        String json = Json.stringify(value);
        if (parsedArgs.output != null) {
            Path parent = parsedArgs.output.toAbsolutePath().getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            Files.writeString(parsedArgs.output, json + System.lineSeparator());
        }
        System.out.println(json);
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
