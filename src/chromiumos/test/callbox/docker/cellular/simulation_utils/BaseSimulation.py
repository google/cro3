# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(b/254347891): unify formatting and ignore specific lints in callbox libraries
# pylint: skip-file

from enum import Enum
import time

from cellular import cellular_simulator
import numpy as np


class BaseSimulation(object):
    """ Base class for cellular connectivity simulations.

    Classes that inherit from this base class implement different simulation
    setups. The base class contains methods that are common to all simulation
    configurations.

    """

    NUM_UL_CAL_READS = 3
    NUM_DL_CAL_READS = 5
    MAX_BTS_INPUT_POWER = 30
    MAX_PHONE_OUTPUT_POWER = 23
    UL_MIN_POWER = -60.0

    # Keys to obtain settings from the test_config dictionary.
    KEY_CALIBRATION = "calibration"
    KEY_ATTACH_RETRIES = "attach_retries"
    KEY_ATTACH_TIMEOUT = "attach_timeout"

    # Filepath to the config files stored in the Anritsu callbox. Needs to be
    # formatted to replace {} with either A or B depending on the model.
    CALLBOX_PATH_FORMAT_STR = 'C:\\Users\\MD8475{}\\Documents\\DAN_configs\\'

    # Time in seconds to wait for the phone to settle
    # after attaching to the base station.
    SETTLING_TIME = 10

    # Default time in seconds to wait for the phone to attach to the basestation
    # after toggling airplane mode. This setting can be changed with the
    # KEY_ATTACH_TIMEOUT keyword in the test configuration file.
    DEFAULT_ATTACH_TIMEOUT = 120

    # The default number of attach retries. This setting can be changed with
    # the KEY_ATTACH_RETRIES keyword in the test configuration file.
    DEFAULT_ATTACH_RETRIES = 3

    # These two dictionaries allow to map from a string to a signal level and
    # have to be overridden by the simulations inheriting from this class.
    UPLINK_SIGNAL_LEVEL_DICTIONARY = {}
    DOWNLINK_SIGNAL_LEVEL_DICTIONARY = {}

    # Units for downlink signal level. This variable has to be overridden by
    # the simulations inheriting from this class.
    DOWNLINK_SIGNAL_LEVEL_UNITS = None

    class BtsConfig(object):
        """ Base station configuration class. This class is only a container for
        base station parameters and should not interact with the instrument
        controller.

        Attributes:
            output_power: a float indicating the required signal level at the
                instrument's output.
            input_level: a float indicating the required signal level at the
                instrument's input.
        """

        def __init__(self):
            """ Initialize the base station config by setting all its
            parameters to None. """
            self.output_power = None
            self.input_power = None
            self.band = None

        def incorporate(self, new_config):
            """ Incorporates a different configuration by replacing the current
            values with the new ones for all the parameters different to None.
            """
            for attr, value in vars(new_config).items():
                if value is not None:
                    setattr(self, attr, value)

    def __init__(self, simulator, log, dut, test_config, calibration_table):
        """ Initializes the Simulation object.

        Keeps a reference to the callbox, log and dut handlers and
        initializes the class attributes.

        Args:
            simulator: a cellular simulator controller
            log: a logger handle
            dut: a device handler implementing BaseCellularDut
            test_config: test configuration obtained from the config file
            calibration_table: a dictionary containing path losses for
                different bands.
        """

        self.simulator = simulator
        self.log = log
        self.dut = dut
        self.calibration_table = calibration_table

        # Turn calibration on or off depending on the test config value. If the
        # key is not present, set to False by default
        if self.KEY_CALIBRATION not in test_config:
            self.log.warning('The {} key is not set in the testbed '
                             'parameters. Setting to off by default. To '
                             'turn calibration on, include the key with '
                             'a true/false value.'.format(
                                 self.KEY_CALIBRATION))

        self.calibration_required = test_config.get(self.KEY_CALIBRATION,
                                                    False)

        # Obtain the allowed number of retries from the test configs
        if self.KEY_ATTACH_RETRIES not in test_config:
            self.log.warning('The {} key is not set in the testbed '
                             'parameters. Setting to {} by default.'.format(
                                 self.KEY_ATTACH_RETRIES,
                                 self.DEFAULT_ATTACH_RETRIES))

        self.attach_retries = test_config.get(self.KEY_ATTACH_RETRIES,
                                              self.DEFAULT_ATTACH_RETRIES)

        # Obtain the attach timeout from the test configs
        if self.KEY_ATTACH_TIMEOUT not in test_config:
            self.log.warning('The {} key is not set in the testbed '
                             'parameters. Setting to {} by default.'.format(
                                 self.KEY_ATTACH_TIMEOUT,
                                 self.DEFAULT_ATTACH_TIMEOUT))

        self.attach_timeout = test_config.get(self.KEY_ATTACH_TIMEOUT,
                                              self.DEFAULT_ATTACH_TIMEOUT)

        # Configuration object for the primary base station
        self.primary_config = self.BtsConfig()

        # Store the current calibrated band
        self.current_calibrated_band = None

        # Path loss measured during calibration
        self.dl_path_loss = None
        self.ul_path_loss = None

        # Target signal levels obtained during configuration
        self.sim_dl_power = None
        self.sim_ul_power = None

        # Stores RRC status change timer
        self.rrc_sc_timer = None

        # Set to default APN
        log.info("Configuring APN.")
        self.dut.set_apn('test', 'test')

        # Enable roaming on the phone
        self.dut.toggle_data_roaming(True)

        # Make sure airplane mode is on so the phone won't attach right away
        self.dut.toggle_airplane_mode(True)

        # Wait for airplane mode setting to propagate
        # TODO @latware b/186880504 change this to a poll_for_condition (Q3 21)
        time.sleep(2)

        # Prepare the simulator for this simulation setup
        self.setup_simulator()

    def setup_simulator(self):
        """ Do initial configuration in the simulator. """
        raise NotImplementedError()

    def attach(self):
        """ Attach the phone to the basestation.

        Sets a good signal level, toggles airplane mode
        and waits for the phone to attach.

        Returns:
            True if the phone was able to attach, False if not.
        """

        # Turn on airplane mode
        self.dut.toggle_airplane_mode(True)

        # Wait for airplane mode setting to propagate
        # TODO @latware b/186880504 change this to a poll_for_condition (Q3 21)
        time.sleep(2)

        # Provide a good signal power for the phone to attach easily
        new_config = self.BtsConfig()
        new_config.input_power = -10
        new_config.output_power = -30
        self.simulator.configure_bts(new_config)
        self.primary_config.incorporate(new_config)

        # Try to attach the phone.
        for i in range(self.attach_retries):

            try:

                # Turn off airplane mode
                self.dut.toggle_airplane_mode(False)

                # Wait for the phone to attach.
                self.simulator.wait_until_attached(timeout=self.attach_timeout)

            except cellular_simulator.CellularSimulatorError:

                # The phone failed to attach
                self.log.info(
                    "UE failed to attach on attempt number {}.".format(i + 1))

                # Turn airplane mode on to prepare the phone for a retry.
                self.dut.toggle_airplane_mode(True)

                # Wait for APM to propagate
                # TODO @latware b/186880504 change this to a poll_for_condition (Q3 21)
                time.sleep(3)

                # Retry
                if i < self.attach_retries - 1:
                    continue
                else:
                    return False

            else:
                # The phone attached successfully.
                # TODO @latware b/186880504 change this to a poll_for_condition (Q3 21)
                time.sleep(self.SETTLING_TIME)
                self.log.info("UE attached to the callbox.")
                break

        return True

    def detach(self):
        """ Detach the phone from the basestation.

        Turns airplane mode and resets basestation.
        """

        # Set the DUT to airplane mode so it doesn't see the
        # cellular network going off
        self.dut.toggle_airplane_mode(True)

        # Wait for APM to propagate
        # TODO @latware b/186880504 change this to a poll_for_condition (Q3 21)
        time.sleep(2)

        # Power off basestation
        self.simulator.detach()

    def stop(self):
        """  Detach phone from the basestation by stopping the simulation.

        Stop the simulation and turn airplane mode on. """

        # Set the DUT to airplane mode so it doesn't see the
        # cellular network going off
        self.dut.toggle_airplane_mode(True)

        # Wait for APM to propagate
        # TODO @latware b/186880504 change this to a poll_for_condition (Q3 21)
        time.sleep(2)

        # Stop the simulation
        self.simulator.stop()

    def start(self):
        """ Start the simulation by attaching the phone and setting the
        required DL and UL power.

        Note that this refers to starting the simulated testing environment
        and not to starting the signaling on the cellular instruments,
        which might have been done earlier depending on the cellular
        instrument controller implementation. """

        if not self.attach():
            raise RuntimeError('Could not attach to base station.')

        # Starts IP traffic while changing this setting to force the UE to be
        # in Communication state, as UL power cannot be set in Idle state
        self.start_traffic_for_calibration()

        self.simulator.wait_until_communication_state()

        # Set uplink power to a minimum before going to the actual desired
        # value. This avoid inconsistencies produced by the hysteresis in the
        # PA switching points.
        self.log.info('Setting UL power to -30 dBm before going to the '
                      'requested value to avoid incosistencies caused by '
                      'hysteresis.')
        self.set_uplink_tx_power(-30)

        # Set signal levels obtained from the test parameters
        self.set_downlink_rx_power(self.sim_dl_power)
        self.set_uplink_tx_power(self.sim_ul_power)

        # Verify signal level
        try:
            rx_power, tx_power = self.dut.get_rx_tx_power_levels()

            if not tx_power or not rx_power[0]:
                raise RuntimeError('The method return invalid Tx/Rx values.')

            self.log.info('Signal level reported by the DUT in dBm: Tx = {}, '
                          'Rx = {}.'.format(tx_power, rx_power))

            if abs(self.sim_ul_power - tx_power) > 1:
                self.log.warning('Tx power at the UE is off by more than 1 dB')

        except RuntimeError as e:
            self.log.error('Could not verify Rx / Tx levels: %s.' % e)

        # Stop IP traffic after setting the UL power level
        self.stop_traffic_for_calibration()

    def parse_parameters(self, parameters):
        """ Configures simulation using a list of parameters.

        Consumes parameters from a list.
        Children classes need to call this method first.

        Args:
            parameters: list of parameters
        """

        raise NotImplementedError()

    def consume_parameter(self, parameters, parameter_name, num_values=0):
        """ Parses a parameter from a list.

        Allows to parse the parameter list. Will delete parameters from the
        list after consuming them to ensure that they are not used twice.

        Args:
            parameters: list of parameters
            parameter_name: keyword to look up in the list
            num_values: number of arguments following the
                parameter name in the list
        Returns:
            A list containing the parameter name and the following num_values
            arguments
        """

        try:
            i = parameters.index(parameter_name)
        except ValueError:
            # parameter_name is not set
            return []

        return_list = []

        try:
            for j in range(num_values + 1):
                return_list.append(parameters.pop(i))
        except IndexError:
            raise ValueError(
                "Parameter {} has to be followed by {} values.".format(
                    parameter_name, num_values))

        return return_list

    def set_uplink_tx_power(self, signal_level):
        """ Configure the uplink tx power level

        Args:
            signal_level: calibrated tx power in dBm
        """
        new_config = self.BtsConfig()
        new_config.input_power = self.calibrated_uplink_tx_power(
            self.primary_config, signal_level)
        self.simulator.configure_bts(new_config)
        self.primary_config.incorporate(new_config)

    def set_downlink_rx_power(self, signal_level):
        """ Configure the downlink rx power level

        Args:
            signal_level: calibrated rx power in dBm
        """
        new_config = self.BtsConfig()
        new_config.output_power = self.calibrated_downlink_rx_power(
            self.primary_config, signal_level)
        self.simulator.configure_bts(new_config)
        self.primary_config.incorporate(new_config)

    def get_uplink_tx_power(self):
        """ Returns the uplink tx power level

        Returns:
            calibrated tx power in dBm
        """
        return self.primary_config.input_power

    def get_downlink_rx_power(self):
        """ Returns the downlink tx power level

        Returns:
            calibrated rx power in dBm
        """
        return self.primary_config.output_power

    def get_uplink_power_from_parameters(self, parameters):
        """ Reads uplink power from a list of parameters. """

        values = self.consume_parameter(parameters, self.PARAM_UL_PW, 1)

        if values:
            if values[1] in self.UPLINK_SIGNAL_LEVEL_DICTIONARY:
                return self.UPLINK_SIGNAL_LEVEL_DICTIONARY[values[1]]
            else:
                if values[1][0] == 'n':
                    # Treat the 'n' character as a negative sign
                    return -float(values[1][1:])
                else:
                    return float(values[1])

        # If the method got to this point it is because PARAM_UL_PW was not
        # included in the test parameters or the provided value was invalid.
        raise ValueError(
            "The test name needs to include parameter {} followed by the "
            "desired uplink power expressed by an integer number in dBm "
            "or by one the following values: {}. To indicate negative "
            "values, use the letter n instead of - sign.".format(
                self.PARAM_UL_PW,
                list(self.UPLINK_SIGNAL_LEVEL_DICTIONARY.keys())))

    def get_downlink_power_from_parameters(self, parameters):
        """ Reads downlink power from a list of parameters. """

        values = self.consume_parameter(parameters, self.PARAM_DL_PW, 1)

        if values:
            if values[1] in self.DOWNLINK_SIGNAL_LEVEL_DICTIONARY:
                return self.DOWNLINK_SIGNAL_LEVEL_DICTIONARY[values[1]]
            else:
                if values[1][0] == 'n':
                    # Treat the 'n' character as a negative sign
                    return -float(values[1][1:])
                else:
                    return float(values[1])

        else:
            # Use default value
            power = self.DOWNLINK_SIGNAL_LEVEL_DICTIONARY['excellent']
            self.log.info("No DL signal level value was indicated in the test "
                          "parameters. Using default value of {} {}.".format(
                              power, self.DOWNLINK_SIGNAL_LEVEL_UNITS))
            return power

    def calibrated_downlink_rx_power(self, bts_config, signal_level):
        """ Calculates the power level at the instrument's output in order to
        obtain the required rx power level at the DUT's input.

        If calibration values are not available, returns the uncalibrated signal
        level.

        Args:
            bts_config: the current configuration at the base station. derived
                classes implementations can use this object to indicate power as
                spectral power density or in other units.
            signal_level: desired downlink received power, can be either a
                key value pair, an int or a float
        """

        # Obtain power value if the provided signal_level is a key value pair
        if isinstance(signal_level, Enum):
            power = signal_level.value
        else:
            power = signal_level

        # Try to use measured path loss value. If this was not set, it will
        # throw an TypeError exception
        try:
            calibrated_power = round(power + self.dl_path_loss, 1)
            if calibrated_power > self.simulator.MAX_DL_POWER:
                self.log.warning(
                    "Cannot achieve phone DL Rx power of {} dBm. Requested TX "
                    "power of {} dBm exceeds callbox limit!".format(
                        power, calibrated_power))
                calibrated_power = self.simulator.MAX_DL_POWER
                self.log.warning(
                    "Setting callbox Tx power to max possible ({} dBm)".format(
                        calibrated_power))

            self.log.info(
                "Requested phone DL Rx power of {} dBm, setting callbox Tx "
                "power at {} dBm".format(power, calibrated_power))
            # Power has to be a natural number so calibration wont be exact.
            # Inform the actual received power after rounding.
            self.log.info(
                "Phone downlink received power is {0:.2f} dBm".format(
                    calibrated_power - self.dl_path_loss))
            return calibrated_power
        except TypeError:
            self.log.info("Phone downlink received power set to {} (link is "
                          "uncalibrated).".format(round(power)))
            return round(power, 1)

    def calibrated_uplink_tx_power(self, bts_config, signal_level):
        """ Calculates the power level at the instrument's input in order to
        obtain the required tx power level at the DUT's output.

        If calibration values are not available, returns the uncalibrated signal
        level.

        Args:
            bts_config: the current configuration at the base station. derived
                classes implementations can use this object to indicate power as
                spectral power density or in other units.
            signal_level: desired uplink transmitted power, can be either a
                key value pair, an int or a float
        """

        # Obtain power value if the provided signal_level is a key value pair
        if isinstance(signal_level, Enum):
            power = signal_level.value
        else:
            power = signal_level

        # Try to use measured path loss value. If this was not set, it will
        # throw an TypeError exception
        try:
            calibrated_power = round(power - self.ul_path_loss, 1)
            if calibrated_power < self.UL_MIN_POWER:
                self.log.warning(
                    "Cannot achieve phone UL Tx power of {} dBm. Requested UL "
                    "power of {} dBm exceeds callbox limit!".format(
                        power, calibrated_power))
                calibrated_power = self.UL_MIN_POWER
                self.log.warning(
                    "Setting UL Tx power to min possible ({} dBm)".format(
                        calibrated_power))

            self.log.info(
                "Requested phone UL Tx power of {} dBm, setting callbox Rx "
                "power at {} dBm".format(power, calibrated_power))
            # Power has to be a natural number so calibration wont be exact.
            # Inform the actual transmitted power after rounding.
            self.log.info(
                "Phone uplink transmitted power is {0:.2f} dBm".format(
                    calibrated_power + self.ul_path_loss))
            return calibrated_power
        except TypeError:
            self.log.info("Phone uplink transmitted power set to {} (link is "
                          "uncalibrated).".format(round(power)))
            return round(power, 1)

    def calibrate(self, band):
        """ Calculates UL and DL path loss if it wasn't done before.

        The should be already set to the required band before calling this
        method.

        Args:
            band: the band that is currently being calibrated.
        """

        if self.dl_path_loss and self.ul_path_loss:
            self.log.info("Measurements are already calibrated.")

        # Attach the phone to the base station
        if not self.attach():
            self.log.info(
                "Skipping calibration because the phone failed to attach.")
            return

        # If downlink or uplink were not yet calibrated, do it now
        if not self.dl_path_loss:
            self.dl_path_loss = self.downlink_calibration()
        if not self.ul_path_loss:
            self.ul_path_loss = self.uplink_calibration()

        # Detach after calibrating
        self.detach()
        # TODO @latware b/186880504 change this to a poll_for_condition (Q3 21)
        time.sleep(2)

    def start_traffic_for_calibration(self):
        """
            Starts UDP IP traffic before running calibration. Uses APN_1
            configured in the phone.
        """
        self.simulator.start_data_traffic()

    def stop_traffic_for_calibration(self):
        """
            Stops IP traffic after calibration.
        """
        self.simulator.stop_data_traffic()

    def downlink_calibration(self, rat=None, power_units_conversion_func=None):
        """ Computes downlink path loss and returns the calibration value

        The DUT needs to be attached to the base station before calling this
        method.

        Args:
            rat: desired RAT to calibrate (matching the label reported by
                the phone)
            power_units_conversion_func: a function to convert the units
                reported by the phone to dBm. needs to take two arguments: the
                reported signal level and bts. use None if no conversion is
                needed.
        Returns:
            Downlink calibration value and measured DL power.
        """

        # Check if this parameter was set. Child classes may need to override
        # this class passing the necessary parameters.
        if not rat:
            raise ValueError(
                "The parameter 'rat' has to indicate the RAT being used as "
                "reported by the phone.")

        # Save initial output level to restore it after calibration
        restoration_config = self.BtsConfig()
        restoration_config.output_power = self.primary_config.output_power

        # Set BTS to a good output level to minimize measurement error
        new_config = self.BtsConfig()
        new_config.output_power = self.simulator.MAX_DL_POWER - 5
        self.simulator.configure_bts(new_config)

        # Starting IP traffic
        self.start_traffic_for_calibration()

        down_power_measured = []
        for i in range(0, self.NUM_DL_CAL_READS):
            # For some reason, the RSRP gets updated on Screen ON event
            signal_strength = self.dut.get_telephony_signal_strength()
            down_power_measured.append(signal_strength[rat])
            # TODO @latware b/186880504 change this to a poll_for_condition (Q3 21)
            time.sleep(5)

        # Stop IP traffic
        self.stop_traffic_for_calibration()

        # Reset bts to original settings
        self.simulator.configure_bts(restoration_config)
        # TODO @latware b/186880504 change this to a poll_for_condition (Q3 21)
        time.sleep(2)

        # Calculate the mean of the measurements
        reported_asu_power = np.nanmean(down_power_measured)

        # Convert from RSRP to signal power
        if power_units_conversion_func:
            avg_down_power = power_units_conversion_func(
                reported_asu_power, self.primary_config)
        else:
            avg_down_power = reported_asu_power

        # Calculate Path Loss
        dl_target_power = self.simulator.MAX_DL_POWER - 5
        down_call_path_loss = dl_target_power - avg_down_power

        # Validate the result
        if not 0 < down_call_path_loss < 100:
            raise RuntimeError(
                "Downlink calibration failed. The calculated path loss value "
                "was {} dBm.".format(down_call_path_loss))

        self.log.info(
            "Measured downlink path loss: {} dB".format(down_call_path_loss))

        return down_call_path_loss

    def uplink_calibration(self):
        """ Computes uplink path loss and returns the calibration value

        The DUT needs to be attached to the base station before calling this
        method.

        Returns:
            Uplink calibration value and measured UL power
        """

        # Save initial input level to restore it after calibration
        restoration_config = self.BtsConfig()
        restoration_config.input_power = self.primary_config.input_power

        # Set BTS1 to maximum input allowed in order to perform
        # uplink calibration
        target_power = self.MAX_PHONE_OUTPUT_POWER
        new_config = self.BtsConfig()
        new_config.input_power = self.MAX_BTS_INPUT_POWER
        self.simulator.configure_bts(new_config)

        # Start IP traffic
        self.start_traffic_for_calibration()

        up_power_per_chain = []
        # Get the number of chains
        cmd = 'MONITOR? UL_PUSCH'
        uplink_meas_power = self.anritsu.send_query(cmd)
        str_power_chain = uplink_meas_power.split(',')
        num_chains = len(str_power_chain)
        for ichain in range(0, num_chains):
            up_power_per_chain.append([])

        for i in range(0, self.NUM_UL_CAL_READS):
            uplink_meas_power = self.anritsu.send_query(cmd)
            str_power_chain = uplink_meas_power.split(',')

            for ichain in range(0, num_chains):
                if (str_power_chain[ichain] == 'DEACTIVE'):
                    up_power_per_chain[ichain].append(float('nan'))
                else:
                    up_power_per_chain[ichain].append(
                        float(str_power_chain[ichain]))

            # TODO @latware b/186880504 change this to a poll_for_condition (Q3 21)
            time.sleep(3)

        # Stop IP traffic
        self.stop_traffic_for_calibration()

        # Reset bts to original settings
        self.simulator.configure_bts(restoration_config)
        # TODO @latware b/186880504 change this to a poll_for_condition (Q3 21)
        time.sleep(2)

        # Phone only supports 1x1 Uplink so always chain 0
        avg_up_power = np.nanmean(up_power_per_chain[0])
        if np.isnan(avg_up_power):
            raise RuntimeError(
                "Calibration failed because the callbox reported the chain to "
                "be deactive.")

        up_call_path_loss = target_power - avg_up_power

        # Validate the result
        if not 0 < up_call_path_loss < 100:
            raise RuntimeError(
                "Uplink calibration failed. The calculated path loss value "
                "was {} dBm.".format(up_call_path_loss))

        self.log.info(
            "Measured uplink path loss: {} dB".format(up_call_path_loss))

        return up_call_path_loss

    def load_pathloss_if_required(self):
        """ If calibration is required, try to obtain the pathloss values from
        the calibration table and measure them if they are not available. """
        # Invalidate the previous values
        self.dl_path_loss = None
        self.ul_path_loss = None

        # Load the new ones
        if self.calibration_required:
            band = self.primary_config.band

            # Try loading the path loss values from the calibration table. If
            # they are not available, use the automated calibration procedure.
            try:
                self.dl_path_loss = self.calibration_table[band]["dl"]
                self.ul_path_loss = self.calibration_table[band]["ul"]
            except KeyError:
                self.calibrate(band)

            # Complete the calibration table with the new values to be used in
            # the next tests.
            if band not in self.calibration_table:
                self.calibration_table[band] = {}

            if "dl" not in self.calibration_table[band] and self.dl_path_loss:
                self.calibration_table[band]["dl"] = self.dl_path_loss

            if "ul" not in self.calibration_table[band] and self.ul_path_loss:
                self.calibration_table[band]["ul"] = self.ul_path_loss

    def maximum_downlink_throughput(self):
        """ Calculates maximum achievable downlink throughput in the current
        simulation state.

        Because thoughput is dependent on the RAT, this method needs to be
        implemented by children classes.

        Returns:
            Maximum throughput in mbps
        """
        raise NotImplementedError()

    def maximum_uplink_throughput(self):
        """ Calculates maximum achievable downlink throughput in the current
        simulation state.

        Because thoughput is dependent on the RAT, this method needs to be
        implemented by children classes.

        Returns:
            Maximum throughput in mbps
        """
        raise NotImplementedError()

    def send_sms(self, sms_message):
        """ Sends the set SMS message. """
        raise NotImplementedError()
