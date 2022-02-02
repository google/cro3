load("@proto//chromiumos/test/api/v1/plan.proto", plan_pb = "chromiumos.test.api.v1")

build_metadata = testplan.get_build_metadata()
flat_configs = testplan.get_flat_config_list()
print('Got {} BuildMetadatas'.format(len(build_metadata.values)))
print('Got {} FlatConfigs'.format(len(flat_configs.values)))

def add_test_plans():
    for bm in list(build_metadata.values)[:10]:
        overlay_name = bm.build_target.portage_build_target.overlay_name
        testplan.add_hw_test_plan(
            plan_pb.HWTestPlan(
                id = plan_pb.HWTestPlan.TestPlanId(value=overlay_name)
            )
        )

add_test_plans()