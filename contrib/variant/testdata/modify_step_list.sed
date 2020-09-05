# Replace all of the steps between EMERGE and CLEAN_UP with an ABORT so
# that generated CLs will not be uploaded to gerrit.
s/(step_names.EMERGE,)\n.*\n(.*)(step_names.CLEAN_UP)/\1\n\2step_names.ABORT,\n\2\3/
# Remove the FW_BUILD_CONFIG step.
s/step_names.FW_BUILD_CONFIG,//