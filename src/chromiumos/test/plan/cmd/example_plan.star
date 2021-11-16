build_metadata = testplan.get_build_metadata()
flat_configs = testplan.get_flat_config_list()
print('Got {} BuildMetadatas'.format(len(build_metadata.values)))
print('Got {} FlatConfigs'.format(len(flat_configs.values)))