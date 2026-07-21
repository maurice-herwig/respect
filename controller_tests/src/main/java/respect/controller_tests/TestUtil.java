package respect.controller_tests;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class TestUtil {
    private TestUtil() {
    }

    public static String requiredString(Map<String, Object> object, String key) {
        String value = stringValue(object.get(key), null);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Missing required string field: " + key);
        }
        return value;
    }

    public static String optionalName(Map<String, Object> object, String fallback) {
        return stringValue(object.get("name"), fallback);
    }

    public static String stringValue(Object value, String fallback) {
        if (value == null) {
            return fallback;
        }
        if (value instanceof Boolean || value instanceof Number || value instanceof String) {
            return String.valueOf(value);
        }
        throw new IllegalArgumentException("Expected scalar value, got: " + value);
    }

    public static int intValue(Object value, int fallback) {
        if (value == null) {
            return fallback;
        }
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        return Integer.parseInt(String.valueOf(value));
    }

    public static long longValue(Object value, long fallback) {
        if (value == null) {
            return fallback;
        }
        if (value instanceof Number) {
            return ((Number) value).longValue();
        }
        return Long.parseLong(String.valueOf(value));
    }

    public static boolean booleanValue(Object value, boolean fallback) {
        if (value == null) {
            return fallback;
        }
        if (value instanceof Boolean) {
            return (Boolean) value;
        }
        return Boolean.parseBoolean(String.valueOf(value));
    }

    public static List<String> stringList(Object value, String label) {
        List<String> result = new ArrayList<>();
        if (value == null) {
            return result;
        }
        for (Object item : Json.asArray(value, label)) {
            result.add(stringValue(item, null));
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, String> stringMap(Object value) {
        Map<String, String> result = new LinkedHashMap<>();
        if (value == null) {
            return result;
        }
        if (value instanceof List<?>) {
            for (Object item : (List<Object>) value) {
                result.put(stringValue(item, null), "");
            }
            return result;
        }
        Map<String, Object> object = Json.asObject(value, "map");
        for (Map.Entry<String, Object> entry : object.entrySet()) {
            result.put(entry.getKey(), stringValue(entry.getValue(), null));
        }
        return result;
    }

    public static Map<String, List<String>> stringListMap(Object value, String label) {
        Map<String, List<String>> result = new LinkedHashMap<>();
        Map<String, Object> object = Json.asObject(value, label);
        for (Map.Entry<String, Object> entry : object.entrySet()) {
            List<String> values = stringList(entry.getValue(), label + "." + entry.getKey());
            if (values.isEmpty()) {
                throw new IllegalArgumentException("Empty domain for " + entry.getKey());
            }
            result.put(entry.getKey(), values);
        }
        if (result.isEmpty()) {
            throw new IllegalArgumentException(label + " must contain at least one variable");
        }
        return result;
    }

    public static List<Map<String, String>> trace(Map<String, Object> config) {
        Object value = config.get("trace");
        if (value == null) {
            value = config.get("inputs");
        }
        List<Map<String, String>> trace = new ArrayList<>();
        if (value == null) {
            Map<String, String> initial = stringMap(config.get("initial_inputs"));
            if (!initial.isEmpty()) {
                trace.add(initial);
            }
            return trace;
        }
        for (Object item : Json.asArray(value, "trace")) {
            trace.add(stringMap(item));
        }
        return trace;
    }

    public static boolean matches(Map<String, String> actual, Map<String, String> expected) {
        for (Map.Entry<String, String> entry : expected.entrySet()) {
            String actualValue = actual.get(entry.getKey());
            if (!entry.getValue().equals(actualValue)) {
                return false;
            }
        }
        return true;
    }

    public static List<String> matchedVariables(Map<String, String> actual, Map<String, String> expected) {
        List<String> result = new ArrayList<>();
        for (Map.Entry<String, String> entry : expected.entrySet()) {
            if (entry.getValue().equals(actual.get(entry.getKey()))) {
                result.add(entry.getKey());
            }
        }
        return result;
    }

    public static List<String> missingOrDifferentVariables(Map<String, String> actual, Map<String, String> expected) {
        List<String> result = new ArrayList<>();
        for (Map.Entry<String, String> entry : expected.entrySet()) {
            String actualValue = actual.get(entry.getKey());
            if (!entry.getValue().equals(actualValue)) {
                result.add(entry.getKey());
            }
        }
        return result;
    }

    public static Map<String, Object> failureDetails(String failureCode) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("failure_code", failureCode);
        return details;
    }
}
