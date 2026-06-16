package respect.controller_tests;

import java.nio.file.Path;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

public final class TestContext {
    private final String controllerDir;
    private final String specName;
    private final Path spectraFile;
    private final Set<String> outputVariables;

    private TestContext(String controllerDir, String specName, Path spectraFile, Set<String> outputVariables) {
        this.controllerDir = controllerDir;
        this.specName = specName;
        this.spectraFile = spectraFile;
        this.outputVariables = outputVariables;
    }

    public static TestContext fromPlan(Map<String, Object> plan) {
        String controllerDir = TestUtil.stringValue(plan.get("controller_dir"), null);
        String specName = TestUtil.stringValue(plan.get("spec_name"), null);
        Path spectraFile = plan.containsKey("spectra_file") ? Path.of(TestUtil.stringValue(plan.get("spectra_file"), null)) : null;
        Set<String> outputs = new LinkedHashSet<>();

        // Prefer explicit output metadata; it prevents reading env variables as controller outputs.
        Object explicitOutputs = plan.get("outputs");
        if (explicitOutputs != null) {
            outputs.addAll(TestUtil.stringList(explicitOutputs, "outputs"));
        }
        Object tests = plan.get("tests");
        if (tests instanceof Iterable<?>) {
            for (Object item : (Iterable<?>) tests) {
                if (item instanceof Map<?, ?>) {
                    Map<?, ?> test = (Map<?, ?>) item;
                    outputs.addAll(TestUtil.stringMap(test.get("sys")).keySet());
                }
            }
        }
        // Fallback for small hand-written plans without top-level outputs or variable_ownership tests.
        if (outputs.isEmpty() && tests instanceof Iterable<?>) {
            for (Object item : (Iterable<?>) tests) {
                if (item instanceof Map<?, ?>) {
                    Map<?, ?> test = (Map<?, ?>) item;
                    outputs.addAll(TestUtil.stringMap(test.get("expected")).keySet());
                    outputs.addAll(TestUtil.stringMap(test.get("forbidden")).keySet());
                    outputs.addAll(TestUtil.stringMap(test.get("then")).keySet());
                    outputs.addAll(TestUtil.stringMap(test.get("eventually")).keySet());
                }
            }
        }
        return new TestContext(controllerDir, specName, spectraFile, outputs);
    }

    public ControllerHarness newHarness() throws Exception {
        if (controllerDir == null || specName == null) {
            throw new IllegalArgumentException("controller_dir and spec_name are required for controller tests");
        }
        return new ControllerHarness(controllerDir, specName, outputVariables);
    }

    public Path spectraFile() {
        return spectraFile;
    }
}
