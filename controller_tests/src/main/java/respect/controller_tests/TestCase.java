package respect.controller_tests;

public interface TestCase {
    TestResult run(TestContext context) throws Exception;
}
