package respect.controller_tests;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

public final class Exploration {
    private Exploration() {
    }

    public static List<List<Map<String, String>>> traces(Map<String, Object> config) {
        // All exploration modes return concrete input traces. Controller tests replay each trace
        // from a fresh initial controller state, so this remains a black-box executor strategy.
        String mode = TestUtil.stringValue(config.get("mode"), "trace");
        switch (mode) {
            case "trace":
                return List.of(TestUtil.trace(config));
            case "traces":
                return concreteTraces(config);
            case "random":
                return randomTraces(config);
            case "exhaustive":
                return exhaustiveTraces(config);
            default:
                throw new IllegalArgumentException("Unsupported exploration mode: " + mode);
        }
    }

    private static List<List<Map<String, String>>> concreteTraces(Map<String, Object> config) {
        List<List<Map<String, String>>> traces = new ArrayList<>();
        for (Object traceObject : Json.asArray(config.get("traces"), "traces")) {
            List<Map<String, String>> trace = new ArrayList<>();
            for (Object stepObject : Json.asArray(traceObject, "trace")) {
                trace.add(TestUtil.stringMap(stepObject));
            }
            traces.add(trace);
        }
        return traces;
    }

    private static List<List<Map<String, String>>> randomTraces(Map<String, Object> config) {
        Map<String, List<String>> env = TestUtil.stringListMap(config.get("env"), "env");
        int runs = TestUtil.intValue(config.get("runs"), 100);
        int maxDepth = TestUtil.intValue(config.get("max_depth"), 10);
        long seed = TestUtil.longValue(config.get("seed"), 1L);
        Random random = new Random(seed);

        // Random exploration is deterministic for a fixed seed, which keeps failed tests reproducible.
        List<String> variables = new ArrayList<>(env.keySet());
        List<List<Map<String, String>>> traces = new ArrayList<>();
        for (int run = 0; run < runs; run++) {
            List<Map<String, String>> trace = new ArrayList<>();
            for (int depth = 0; depth < maxDepth; depth++) {
                Map<String, String> step = new LinkedHashMap<>();
                for (String variable : variables) {
                    List<String> domain = env.get(variable);
                    step.put(variable, domain.get(random.nextInt(domain.size())));
                }
                trace.add(step);
            }
            traces.add(trace);
        }
        return traces;
    }

    private static List<List<Map<String, String>>> exhaustiveTraces(Map<String, Object> config) {
        Map<String, List<String>> env = TestUtil.stringListMap(config.get("env"), "env");
        int maxDepth = TestUtil.intValue(config.get("max_depth"), 6);
        int maxPaths = TestUtil.intValue(config.get("max_paths"), 10000);
        List<String> variables = new ArrayList<>(env.keySet());
        List<List<Map<String, String>>> traces = new ArrayList<>();
        // Exhaustive mode enumerates the bounded input-tree; max_paths prevents accidental blowups.
        buildExhaustiveTrace(env, variables, maxDepth, maxPaths, new ArrayList<>(), traces);
        return traces;
    }

    private static void buildExhaustiveTrace(
        Map<String, List<String>> env,
        List<String> variables,
        int maxDepth,
        int maxPaths,
        List<Map<String, String>> prefix,
        List<List<Map<String, String>>> traces
    ) {
        if (traces.size() >= maxPaths) {
            return;
        }
        if (prefix.size() == maxDepth) {
            traces.add(copyTrace(prefix));
            return;
        }
        // Extend the current prefix by every possible environment valuation for the next step.
        for (Map<String, String> valuation : valuations(env, variables)) {
            prefix.add(valuation);
            buildExhaustiveTrace(env, variables, maxDepth, maxPaths, prefix, traces);
            prefix.remove(prefix.size() - 1);
            if (traces.size() >= maxPaths) {
                return;
            }
        }
    }

    private static List<Map<String, String>> valuations(Map<String, List<String>> env, List<String> variables) {
        List<Map<String, String>> result = new ArrayList<>();
        // Build the Cartesian product of all declared environment domains for one time step.
        buildValuation(env, variables, 0, new LinkedHashMap<>(), result);
        return result;
    }

    private static void buildValuation(
        Map<String, List<String>> env,
        List<String> variables,
        int index,
        Map<String, String> current,
        List<Map<String, String>> result
    ) {
        if (index == variables.size()) {
            result.add(new LinkedHashMap<>(current));
            return;
        }
        String variable = variables.get(index);
        for (String value : env.get(variable)) {
            current.put(variable, value);
            buildValuation(env, variables, index + 1, current, result);
        }
        current.remove(variable);
    }

    private static List<Map<String, String>> copyTrace(List<Map<String, String>> trace) {
        List<Map<String, String>> copy = new ArrayList<>();
        for (Map<String, String> step : trace) {
            copy.add(new LinkedHashMap<>(step));
        }
        return copy;
    }
}
