package respect.controller_tests;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

import tau.smlab.syntech.controller.executor.ControllerExecutor;
import tau.smlab.syntech.games.controller.jits.BasicJitController;

public final class ControllerHarness {
    private final ControllerExecutor executor;
    private final Set<String> outputVariables;
    private boolean initialized;

    public ControllerHarness(String controllerDir, String specName, Set<String> outputVariables) throws Exception {
        // The Syntech executor expects the synthesized JIT folder and the original spec name.
        this.executor = new ControllerExecutor(new BasicJitController(), controllerDir, specName);
        this.outputVariables = outputVariables;
        this.initialized = false;
    }

    public StepResult step(Map<String, String> inputs) throws Exception {
        // The first controller interaction must use initState; later steps use updateState.
        if (!initialized) {
            executor.initState(inputs);
            initialized = true;
        } else {
            executor.updateState(inputs);
        }

        // Only read outputs requested by the test plan, because env variables are supplied as inputs.
        Map<String, String> outputs = new LinkedHashMap<>();
        for (String output : outputVariables) {
            outputs.put(output, executor.getCurrValue(output));
        }
        return new StepResult(inputs, outputs);
    }
}
