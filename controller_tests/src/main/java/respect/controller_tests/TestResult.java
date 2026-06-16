package respect.controller_tests;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class TestResult {
    private final String name;
    private final String kind;
    private final boolean passed;
    private final String reason;
    private final List<Map<String, Object>> trace;

    private TestResult(String name, String kind, boolean passed, String reason, List<Map<String, Object>> trace) {
        this.name = name;
        this.kind = kind;
        this.passed = passed;
        this.reason = reason;
        this.trace = trace;
    }

    public static TestResult pass(String name, String kind) {
        return new TestResult(name, kind, true, null, null);
    }

    public static TestResult fail(String name, String kind, String reason, List<Map<String, Object>> trace) {
        return new TestResult(name, kind, false, reason, trace);
    }

    public boolean passed() {
        return passed;
    }

    public Map<String, Object> toJson() {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("name", name);
        value.put("kind", kind);
        value.put("passed", passed);
        if (reason != null) {
            value.put("reason", reason);
        }
        if (trace != null) {
            value.put("trace", trace);
        }
        return value;
    }
}
