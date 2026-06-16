package respect.controller_tests;

import java.util.LinkedHashMap;
import java.util.Map;

public final class StepResult {
    private final Map<String, String> inputs;
    private final Map<String, String> outputs;

    public StepResult(Map<String, String> inputs, Map<String, String> outputs) {
        this.inputs = new LinkedHashMap<>(inputs);
        this.outputs = new LinkedHashMap<>(outputs);
    }

    public Map<String, String> inputs() {
        return inputs;
    }

    public Map<String, String> outputs() {
        return outputs;
    }

    public Map<String, String> combined() {
        Map<String, String> combined = new LinkedHashMap<>();
        combined.putAll(inputs);
        combined.putAll(outputs);
        return combined;
    }

    public Map<String, Object> toJson() {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("inputs", inputs);
        value.put("outputs", outputs);
        return value;
    }
}
