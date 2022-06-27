load("@proto//chromiumos/test/api/v1/plan.proto", plan_pb = "chromiumos.test.api.v1")
load("@proto//chromiumos/test/api/coverage_rule.proto", coverage_rule_pb = "chromiumos.test.api")
load("@proto//chromiumos/test/api/dut_attribute.proto", dut_attribute_pb = "chromiumos.test.api")
load("@proto//chromiumos/test/api/test_case.proto", test_case_pb = "chromiumos.test.api")
load("@proto//chromiumos/test/api/test_suite.proto", test_suite_pb = "chromiumos.test.api")

build_metadata = testplan.get_build_metadata()
config_bundle_list = testplan.get_config_bundle_list()
print("Got {} BuildMetadatas".format(len(build_metadata.values)))
print("Got {} ConfigBundles".format(len(config_bundle_list.values)))

def add_test_plans():
    for bm in build_metadata.values:
        overlay_name = bm.build_target.portage_build_target.overlay_name
        testplan.add_hw_test_plan(
            plan_pb.HWTestPlan(
                id = plan_pb.HWTestPlan.TestPlanId(value = overlay_name),
                coverage_rules = [
                    coverage_rule_pb.CoverageRule(
                        test_suites = [
                            test_suite_pb.TestSuite(
                                test_case_ids = test_case_pb.TestCaseIdList(
                                    test_case_ids = [
                                        test_case_pb.TestCase.Id(
                                            value = "suiteA",
                                        ),
                                    ],
                                ),
                            ),
                        ],
                        dut_targets = [
                            dut_attribute_pb.DutTarget(
                                criteria = [
                                    dut_attribute_pb.DutCriterion(
                                        attribute_id = dut_attribute_pb.DutAttribute.Id(
                                            value = "attr-program",
                                        ),
                                        values = [overlay_name],
                                    ),
                                    dut_attribute_pb.DutCriterion(
                                        attribute_id = dut_attribute_pb.DutAttribute.Id(
                                            value = "swarming-pool",
                                        ),
                                        values = ["TESTPOOL"],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        )

add_test_plans()
