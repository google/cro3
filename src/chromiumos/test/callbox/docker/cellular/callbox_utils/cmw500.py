# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: skip-file

from enum import Enum
import time

from . import cmw500_iperf_measurement as perf
from .. import abstract_inst


LTE_ATTACH_RESP = 'ATT'
LTE_CONN_RESP = 'CONN'
LTE_IDLE_RESP = 'IDLE'
LTE_PSWITCHED_ON_RESP = 'ON'
LTE_PSWITCHED_OFF_RESP = 'OFF'

STATE_CHANGE_TIMEOUT = 20


class LteState(Enum):
    """LTE ON and OFF"""
    LTE_ON = 'ON'
    LTE_OFF = 'OFF'


class BtsNumber(Enum):
    """Base station Identifiers."""
    BTS1 = 'PCC'
    BTS2 = 'SCC1'
    BTS3 = 'SCC2'
    BTS4 = 'SCC3'
    BTS5 = 'SCC4'
    BTS6 = 'SCC6'
    BTS7 = 'SCC7'


class LteBandwidth(Enum):
    """Supported LTE bandwidths."""
    BANDWIDTH_1MHz = 'B014'
    BANDWIDTH_3MHz = 'B030'
    BANDWIDTH_5MHz = 'B050'
    BANDWIDTH_10MHz = 'B100'
    BANDWIDTH_15MHz = 'B150'
    BANDWIDTH_20MHz = 'B200'


class DuplexMode(Enum):
    """Duplex Modes"""
    FDD = 'FDD'
    TDD = 'TDD'


class SchedulingMode(Enum):
    """Supported scheduling modes."""
    RMC = 'RMC'
    USERDEFINEDCH = 'UDCHannels'


class TransmissionModes(Enum):
    """Supported transmission modes."""
    TM1 = 'TM1'
    TM2 = 'TM2'
    TM3 = 'TM3'
    TM4 = 'TM4'
    TM7 = 'TM7'
    TM8 = 'TM8'
    TM9 = 'TM9'


class UseCarrierSpecific(Enum):
    """Enable or disable carrier specific."""
    UCS_ON = 'ON'
    UCS_OFF = 'OFF'


class RbPosition(Enum):
    """Supported RB positions."""
    LOW = 'LOW'
    HIGH = 'HIGH'
    P5 = 'P5'
    P10 = 'P10'
    P23 = 'P23'
    P35 = 'P35'
    P48 = 'P48'


class ModulationType(Enum):
    """Supported Modulation Types."""
    QPSK = 'QPSK'
    Q16 = 'Q16'
    Q64 = 'Q64'
    Q256 = 'Q256'


class DciFormat(Enum):
    """Support DCI Formats for MIMOs"""
    D1 = 'D1'
    D1A = 'D1A'
    D1B = 'D1B'
    D2 = 'D2'
    D2A = 'D2A'
    D2B = 'D2B'
    D2C = 'D2C'


class MimoModes(Enum):
    """MIMO Modes dl antennas"""
    MIMO1x1 = 'ONE'
    MIMO2x2 = 'TWO'
    MIMO4x4 = 'FOUR'


class MimoScenario(Enum):
    """Supported mimo scenarios"""
    SCEN1x1 = 'SCELl:FLEXible SUA1,RF1C,RX1,RF1C,TX1'
    SCEN2x2 = 'TRO:FLEXible SUA1,RF1C,RX1,RF1C,TX1,RF3C,TX2'
    SCEN4x4 = 'FRO FLEXible SUA1,RF1C,RX1,RF1C,TX1,RF3C,TX2,RF2C,TX3,RF4C,TX4'


class RrcState(Enum):
    """States to enable/disable rrc."""
    RRC_ON = 'ON'
    RRC_OFF = 'OFF'


class MacPadding(Enum):
    """Enables/Disables Mac Padding."""
    ON = 'ON'
    OFF = 'OFF'


class ConnectionType(Enum):
    """Supported Connection Types."""
    TEST = 'TESTmode'
    DAU = 'DAPPlication'


class RepetitionMode(Enum):
    """Specifies LTE Measurement Repetition Mode."""
    SINGLESHOT = 'SINGleshot'
    CONTINUOUS = 'CONTinuous'


class TpcPowerControl(Enum):
    """Specifies Up Link power control types."""
    MIN_POWER = 'MINPower'
    MAX_POWER = 'MAXPower'
    CONSTANT = 'CONStant'
    SINGLE = 'SINGle'
    UDSINGLE = 'UDSingle'
    UDCONTINUOUS = 'UDContinuous'
    ALTERNATE = 'ALT0'
    CLOSED_LOOP = 'CLOop'
    RP_CONTROL = 'RPControl'
    FLEX_POWER = 'FULPower'


class ReducedPdcch(Enum):
    """Enables/disables the reduction of PDCCH resources."""
    ON = 'ON'
    OFF = 'OFF'


class Cmw500(abstract_inst.SocketInstrument):
    """ Base class for interfacing with the CMW500 Callbox device """

    def __init__(self, ip_addr, port, logger):
        """Init method to setup variables for controllers.

        Args:
              ip_addr: Controller's ip address.
              port: Port
        """
        super(Cmw500, self).__init__(ip_addr, port, logger)
        self._connect_socket()
        self._send('*CLS')
        self._send('*ESE 0;*SRE 0')
        self._send('*CLS')
        self._send('*ESE 1;*SRE 4')
        self._send('SYST:DISP:UPD ON')

    def switch_lte_signalling(self, state):
        """ Turns LTE signalling ON/OFF.

        Args:
              state: an instance of LteState indicating the state to which LTE
                signal has to be set.
        """
        if not isinstance(state, LteState):
            raise ValueError('state should be the instance of LteState.')

        state = state.value

        cmd = 'SOURce:LTE:SIGN:CELL:STATe {}'.format(state)
        self.send_and_recv(cmd)

        time_elapsed = 0
        while time_elapsed < STATE_CHANGE_TIMEOUT:
            response = self.send_and_recv('SOURce:LTE:SIGN:CELL:STATe:ALL?')

            if response == state + ',ADJ':
                self._logger.info('LTE signalling is now {}.'.format(state))
                break

            # Wait for a second and increase time count by one
            time.sleep(1)
            time_elapsed += 1
        else:
            raise CmwError('Failed to turn {} LTE signalling.'.format(state))

    def enable_packet_switching(self):
        """Enable packet switching in call box."""
        self.send_and_recv('CALL:LTE:SIGN:PSWitched:ACTion CONNect')
        self.wait_for_pswitched_state()

    def disable_packet_switching(self):
        """Disable packet switching in call box."""
        self.send_and_recv('CALL:LTE:SIGN:PSWitched:ACTion DISConnect')
        self.wait_for_pswitched_state()

    @property
    def use_carrier_specific(self):
        """Gets current status of carrier specific duplex configuration."""
        return self.send_and_recv('CONFigure:LTE:SIGN:DMODe:UCSPECific?')

    @use_carrier_specific.setter
    def use_carrier_specific(self, state):
        """Sets the carrier specific duplex configuration.

        Args:
            state: ON/OFF UCS configuration.
        """
        cmd = 'CONFigure:LTE:SIGN:DMODe:UCSPECific {}'.format(state)
        self.send_and_recv(cmd)

    def send_and_recv(self, cmd):
        """Send and recv the status of the command.

        Args:
            cmd: Command to send.

        Returns:
            status: returns the status of the command sent.
        """

        self._send(cmd)
        if '?' in cmd:
            status = self._recv()
            return status

    def configure_mimo_settings(self, mimo):
        """Sets the mimo scenario for the test.

        Args:
            mimo: mimo scenario to set.
        """
        cmd = 'ROUTe:LTE:SIGN:SCENario:{}'.format(mimo.value)
        self.send_and_recv(cmd)

    def wait_for_pswitched_state(self, timeout=10):
        """Wait until pswitched state.

        Args:
            timeout: timeout for lte pswitched state.

        Raises:
            CmwError on timeout.
        """
        while timeout > 0:
            state = self.send_and_recv('FETCh:LTE:SIGN:PSWitched:STATe?')
            if state == LTE_PSWITCHED_ON_RESP:
                self._logger.debug('Connection to setup initiated.')
                break
            elif state == LTE_PSWITCHED_OFF_RESP:
                self._logger.debug('Connection to setup detached.')
                break

            # Wait for a second and decrease count by one
            time.sleep(1)
            timeout -= 1
        else:
            raise CmwError('Failure in setting up/detaching connection')

    def wait_for_attached_state(self, timeout=120):
        """Attach the controller with device.

        Args:
            timeout: timeout for phone to get attached.

        Raises:
            CmwError on time out.
        """
        while timeout > 0:
            state = self.send_and_recv('FETCh:LTE:SIGN:PSWitched:STATe?')

            if state == LTE_ATTACH_RESP:
                self._logger.debug('Call box attached with device')
                break

            # Wait for a second and decrease count by one
            time.sleep(1)
            timeout -= 1
        else:
            raise CmwError('Device could not be attached')

    def wait_for_rrc_state(self, state, timeout=120):
        """ Waits until a certain RRC state is set.

        Args:
            state: the RRC state that is being waited for.
            timeout: timeout for phone to be in connected state.

        Raises:
            CmwError on time out.
        """
        if state not in [LTE_CONN_RESP, LTE_IDLE_RESP]:
            raise ValueError(
                    'The allowed values for state are {} and {}.'.format(
                            LTE_CONN_RESP, LTE_IDLE_RESP))

        while timeout > 0:
            new_state = self.send_and_recv('SENSe:LTE:SIGN:RRCState?')
            if new_state == state:
                self._logger.debug('The RRC state is {}.'.format(new_state))
                break

            # Wait for a second and decrease count by one
            time.sleep(1)
            timeout -= 1
        else:
            raise CmwError('Timeout before RRC state was {}.'.format(state))

    def reset(self):
        """System level reset"""
        self.send_and_recv('*RST; *OPC')

    @property
    def get_instrument_id(self):
        """Gets instrument identification number"""
        return self.send_and_recv('*IDN?')

    def disconnect(self):
        """Disconnect controller from device and switch to local mode."""
        self.switch_lte_signalling(LteState.LTE_OFF)
        self.close_remote_mode()
        self._close_socket()

    def close_remote_mode(self):
        """Exits remote mode to local mode."""
        self.send_and_recv('&GTL')

    def detach(self):
        """Detach callbox and controller."""
        self.send_and_recv('CALL:LTE:SIGN:PSWitched:ACTion DETach')

    @property
    def rrc_connection(self):
        """Gets the RRC connection state."""
        return self.send_and_recv('CONFigure:LTE:SIGN:CONNection:KRRC?')

    @rrc_connection.setter
    def rrc_connection(self, state):
        """Selects whether the RRC connection is kept or released after attach.

        Args:
            mode: RRC State ON/OFF.
        """
        if not isinstance(state, RrcState):
            raise ValueError('state should be the instance of RrcState.')

        cmd = 'CONFigure:LTE:SIGN:CONNection:KRRC {}'.format(state.value)
        self.send_and_recv(cmd)

    @property
    def rrc_connection_timer(self):
        """Gets the inactivity timeout for disabled rrc connection."""
        return self.send_and_recv('CONFigure:LTE:SIGN:CONNection:RITimer?')

    @rrc_connection_timer.setter
    def rrc_connection_timer(self, time_in_secs):
        """Sets the inactivity timeout for disabled rrc connection. By default
        the timeout is set to 5.

        Args:
            time_in_secs: timeout of inactivity in rrc connection.
        """
        cmd = 'CONFigure:LTE:SIGN:CONNection:RITimer {}'.format(time_in_secs)
        self.send_and_recv(cmd)

    @property
    def dl_mac_padding(self):
        """Gets the state of mac padding."""
        return self.send_and_recv('CONFigure:LTE:SIGN:CONNection:DLPadding?')

    @dl_mac_padding.setter
    def dl_mac_padding(self, state):
        """Enables/Disables downlink padding at the mac layer.

        Args:
            state: ON/OFF
        """
        cmd = 'CONFigure:LTE:SIGN:CONNection:DLPadding {}'.format(state.value)
        self.send_and_recv(cmd)

    @property
    def connection_type(self):
        """Gets the connection type applied in callbox."""
        return self.send_and_recv('CONFigure:LTE:SIGN:CONNection:CTYPe?')

    @connection_type.setter
    def connection_type(self, ctype):
        """Sets the connection type to be applied.

        Args:
            ctype: Connection type.
        """
        cmd = 'CONFigure:LTE:SIGN:CONNection:CTYPe {}'.format(ctype.value)
        self.send_and_recv(cmd)

    def get_base_station(self, bts_num=BtsNumber.BTS1):
        """Gets the base station object based on bts num. By default
        bts_num set to PCC

        Args:
            bts_num: base station identifier

        Returns:
            base station object.
        """
        return BaseStation(self, bts_num)

    def init_lte_measurement(self):
        """Gets the class object for lte measurement which can be used to
        initiate measurements.

        Returns:
            lte measurement object.
        """
        return LteMeasurement(self)

    def init_perf_measurement(self):
        """Gets the class object for Iperf measurements which can be used to
        configure and initiate measurements.

        Returns:
            Iperf measurement object.
        """
        return perf.Cmw500IperfMeasurement(self)

    def set_sms(self, sms_message):
        """Sets the SMS message to be sent by the callbox."""
        self.send_and_recv('CONFigure:LTE:SIGN:SMS:OUTGoing:INTernal "%s"' % sms_message)

    def send_sms(self):
        """Sends the SMS message."""
        self.send_and_recv('CALL:LTE:SIGN:PSWitched:ACTion SMS; *OPC?')
        timeout = time.time() + STATE_CHANGE_TIMEOUT
        while "SUCC" != self.send_and_recv('SENSe:LTE:SIGN:SMS:OUTGoing:INFO:LMSent?'):
            if time.time() > timeout:
                raise CmwError("SENSe:LTE:SIGN:SMS:OUTGoing:INFO:LMSent? never returns status 'SUCC' instead got (%s)" % self.send_and_recv('SENSe:LTE:SIGN:SMS:OUTGoing:INFO:LMSent?'))
            time.sleep(2)


class BaseStation(object):
    """Class to interact with different base stations"""

    def __init__(self, cmw, bts_num):
        if not isinstance(bts_num, BtsNumber):
            raise ValueError('bts_num should be an instance of BtsNumber.')
        self._bts = bts_num.value
        self._cmw = cmw

    @property
    def duplex_mode(self):
        """Gets current duplex of cell."""
        cmd = 'CONFigure:LTE:SIGN:{}:DMODe?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @duplex_mode.setter
    def duplex_mode(self, mode):
        """Sets the Duplex mode of cell.

        Args:
            mode: String indicating FDD or TDD.
        """
        if not isinstance(mode, DuplexMode):
            raise ValueError('mode should be an instance of DuplexMode.')

        cmd = 'CONFigure:LTE:SIGN:{}:DMODe {}'.format(self._bts, mode.value)
        self._cmw.send_and_recv(cmd)

    @property
    def band(self):
        """Gets the current band of cell."""
        cmd = 'CONFigure:LTE:SIGN:{}:BAND?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @band.setter
    def band(self, band):
        """Sets the Band of cell.

        Args:
            band: band of cell.
        """
        cmd = 'CONFigure:LTE:SIGN:{}:BAND {}'.format(self._bts, band)
        self._cmw.send_and_recv(cmd)

    @property
    def dl_channel(self):
        """Gets the downlink channel of cell."""
        cmd = 'CONFigure:LTE:SIGN:RFSettings:{}:CHANnel:DL?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @dl_channel.setter
    def dl_channel(self, channel):
        """Sets the downlink channel number of cell.

        Args:
            channel: downlink channel number of cell.
        """
        cmd = 'CONFigure:LTE:SIGN:RFSettings:{}:CHANnel:DL {}'.format(
                self._bts, channel)
        self._cmw.send_and_recv(cmd)

    @property
    def ul_channel(self):
        """Gets the uplink channel of cell."""
        cmd = 'CONFigure:LTE:SIGN:RFSettings:{}:CHANnel:UL?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @ul_channel.setter
    def ul_channel(self, channel):
        """Sets the up link channel number of cell.

        Args:
            channel: up link channel number of cell.
        """
        cmd = 'CONFigure:LTE:SIGN:RFSettings:{}:CHANnel:UL {}'.format(
                self._bts, channel)
        self._cmw.send_and_recv(cmd)

    @property
    def bandwidth(self):
        """Get the channel bandwidth of the cell."""
        cmd = 'CONFigure:LTE:SIGN:CELL:BANDwidth:{}:DL?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @bandwidth.setter
    def bandwidth(self, bandwidth):
        """Sets the channel bandwidth of the cell.

        Args:
            bandwidth: channel bandwidth of cell.
        """
        if not isinstance(bandwidth, LteBandwidth):
            raise ValueError('bandwidth should be an instance of '
                             'LteBandwidth.')
        cmd = 'CONFigure:LTE:SIGN:CELL:BANDwidth:{}:DL {}'.format(
                self._bts, bandwidth.value)
        self._cmw.send_and_recv(cmd)

    @property
    def ul_frequency(self):
        """Get the uplink frequency of the cell."""
        cmd = 'CONFigure:LTE:SIGN:RFSettings:{}:CHANnel:UL? MHZ'.format(
                self._bts)
        return self._cmw.send_and_recv(cmd)

    @ul_frequency.setter
    def ul_frequency(self, freq):
        """Get the uplink frequency of the cell.

        Args:
            freq: uplink frequency of the cell.
        """
        cmd = 'CONFigure:LTE:SIGN:RFSettings:{}:CHANnel:UL {} MHZ'.format(
                self._bts, freq)
        self._cmw.send_and_recv(cmd)

    @property
    def dl_frequency(self):
        """Get the downlink frequency of the cell"""
        cmd = 'CONFigure:LTE:SIGN:RFSettings:{}:CHANnel:DL? MHZ'.format(
                self._bts)
        return self._cmw.send_and_recv(cmd)

    @dl_frequency.setter
    def dl_frequency(self, freq):
        """Get the downlink frequency of the cell.

        Args:
            freq: downlink frequency of the cell.
        """
        cmd = 'CONFigure:LTE:SIGN:RFSettings:{}:CHANnel:DL {} MHZ'.format(
                self._bts, freq)
        self._cmw.send_and_recv(cmd)

    @property
    def transmode(self):
        """Gets the TM of cell."""
        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:TRANsmission?'.format(
                self._bts)
        return self._cmw.send_and_recv(cmd)

    @transmode.setter
    def transmode(self, tm_mode):
        """Sets the TM of cell.

        Args:
            tm_mode: TM of cell.
        """
        if not isinstance(tm_mode, TransmissionModes):
            raise ValueError('tm_mode should be an instance of '
                             'Transmission modes.')

        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:TRANsmission {}'.format(
                self._bts, tm_mode.value)
        self._cmw.send_and_recv(cmd)

    @property
    def downlink_power_level(self):
        """Gets RSPRE level."""
        cmd = 'CONFigure:LTE:SIGN:DL:{}:RSEPre:LEVel?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @downlink_power_level.setter
    def downlink_power_level(self, pwlevel):
        """Modifies RSPRE level.

        Args:
            pwlevel: power level in dBm.
        """
        cmd = 'CONFigure:LTE:SIGN:DL:{}:RSEPre:LEVel {}'.format(
                self._bts, pwlevel)
        self._cmw.send_and_recv(cmd)

    @property
    def uplink_power_control(self):
        """Gets open loop nominal power directly."""
        cmd = 'CONFigure:LTE:SIGN:UL:{}:PUSCh:OLNPower?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @uplink_power_control.setter
    def uplink_power_control(self, ul_power):
        """Sets open loop nominal power directly.

        Args:
            ul_power: uplink power level.
        """
        cmd = 'CONFigure:LTE:SIGN:UL:{}:PUSCh:OLNPower {}'.format(
                self._bts, ul_power)
        self._cmw.send_and_recv(cmd)

    @property
    def uldl_configuration(self):
        """Gets uldl configuration of the cell."""
        cmd = 'CONFigure:LTE:SIGN:CELL:{}:ULDL?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @uldl_configuration.setter
    def uldl_configuration(self, uldl):
        """Sets the ul-dl configuration.

        Args:
            uldl: Configuration value ranging from 0 to 6.
        """
        if uldl not in range(0, 7):
            raise ValueError('uldl configuration value should be between'
                             ' 0 and 6 inclusive.')

        cmd = 'CONFigure:LTE:SIGN:CELL:{}:ULDL {}'.format(self._bts, uldl)
        self._cmw.send_and_recv(cmd)

    @property
    def tdd_special_subframe(self):
        """Gets special subframe of the cell."""
        cmd = 'CONFigure:LTE:SIGN:CELL:{}:SSUBframe?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @tdd_special_subframe.setter
    def tdd_special_subframe(self, sframe):
        """Sets the tdd special subframe of the cell.

        Args:
            sframe: Integer value ranging from 1 to 9.
        """
        if sframe not in range(0, 10):
            raise ValueError('tdd special subframe should be between 0 and 9'
                             ' inclusive.')

        cmd = 'CONFigure:LTE:SIGN:CELL:{}:SSUBframe {}'.format(
                self._bts, sframe)
        self._cmw.send_and_recv(cmd)

    @property
    def scheduling_mode(self):
        """Gets the current scheduling mode."""
        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:STYPe?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @scheduling_mode.setter
    def scheduling_mode(self, mode):
        """Sets the scheduling type for the cell.

        Args:
            mode: Selects the channel mode to be scheduled.
        """
        if not isinstance(mode, SchedulingMode):
            raise ValueError('mode should be the instance of scheduling mode.')

        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:STYPe {}'.format(
                self._bts, mode.value)
        self._cmw.send_and_recv(cmd)

    @property
    def rb_configuration_dl(self):
        """Gets rmc's rb configuration for down link. This function returns
        Number of Resource blocks, Resource block position and Modulation type.
        """
        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:{}:DL?'.format(
                self._bts, self.scheduling_mode)
        return self._cmw.send_and_recv(cmd)

    @rb_configuration_dl.setter
    def rb_configuration_dl(self, rb_config):
        """Sets the rb configuration for down link for scheduling type.

        Args:
            rb_config: Tuple containing Number of resource blocks, resource
            block position and modulation type.

        Raises:
            ValueError: If tuple unpacking fails.
        """
        if self.scheduling_mode == 'RMC':
            rb, rb_pos, modulation = rb_config

            cmd = ('CONFigure:LTE:SIGN:CONNection:{}:RMC:DL {},{},'
                   '{}'.format(self._bts, rb, rb_pos, modulation))
            self._cmw.send_and_recv(cmd)

        elif self.scheduling_mode == 'UDCH':
            rb, start_rb, modulation, tbs = rb_config

            self.validate_rb(rb)

            if not isinstance(modulation, ModulationType):
                raise ValueError('Modulation should be of type '
                                 'ModulationType.')

            cmd = ('CONFigure:LTE:SIGN:CONNection:{}:UDCHannels:DL {},{},'
                   '{},{}'.format(self._bts, rb, start_rb, modulation.value,
                                  tbs))
            self._cmw.send_and_recv(cmd)

    @property
    def rb_configuration_ul(self):
        """Gets rb configuration for up link. This function returns
        Number of Resource blocks, Resource block position and Modulation type.
        """
        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:{}:UL?'.format(
                self._bts, self.scheduling_mode)
        return self._cmw.send_and_recv(cmd)

    @rb_configuration_ul.setter
    def rb_configuration_ul(self, rb_config):
        """Sets the rb configuration for down link for scheduling mode.

        Args:
            rb_config: Tuple containing Number of resource blocks, resource
            block position and modulation type.

        Raises:
            ValueError: If tuple unpacking fails.
        """
        if self.scheduling_mode == 'RMC':
            rb, rb_pos, modulation = rb_config

            cmd = ('CONFigure:LTE:SIGN:CONNection:{}:RMC:UL {},{},'
                   '{}'.format(self._bts, rb, rb_pos, modulation))
            self._cmw.send_and_recv(cmd)

        elif self.scheduling_mode == 'UDCH':
            rb, start_rb, modulation, tbs = rb_config

            self.validate_rb(rb)

            if not isinstance(modulation, ModulationType):
                raise ValueError('Modulation should be of type '
                                 'ModulationType.')
            cmd = ('CONFigure:LTE:SIGN:CONNection:{}:UDCHannels:UL {},{},'
                   '{},{}'.format(self._bts, rb, start_rb, modulation.value,
                                  tbs))
            self._cmw.send_and_recv(cmd)

    def validate_rb(self, rb):
        """Validates if rb is within the limits for bandwidth set.

        Args:
            rb: No. of resource blocks.

        Raises:
            ValueError if rb out of range.
        """
        bandwidth = self.bandwidth

        if bandwidth == LteBandwidth.BANDWIDTH_1MHz.value:
            if not 0 <= rb <= 6:
                raise ValueError('RB should be between 0 to 6 inclusive'
                                 ' for 1.4Mhz.')
        elif bandwidth == LteBandwidth.BANDWIDTH_3MHz.value:
            if not 0 <= rb <= 10:
                raise ValueError('RB should be between 0 to 10 inclusive'
                                 ' for 3 Mhz.')
        elif bandwidth == LteBandwidth.BANDWIDTH_5MHz.value:
            if not 0 <= rb <= 25:
                raise ValueError('RB should be between 0 to 25 inclusive'
                                 ' for 5 Mhz.')
        elif bandwidth == LteBandwidth.BANDWIDTH_10MHz.value:
            if not 0 <= rb <= 50:
                raise ValueError('RB should be between 0 to 50 inclusive'
                                 ' for 10 Mhz.')
        elif bandwidth == LteBandwidth.BANDWIDTH_15MHz.value:
            if not 0 <= rb <= 75:
                raise ValueError('RB should be between 0 to 75 inclusive'
                                 ' for 15 Mhz.')
        elif bandwidth == LteBandwidth.BANDWIDTH_20MHz.value:
            if not 0 <= rb <= 100:
                raise ValueError('RB should be between 0 to 100 inclusive'
                                 ' for 20 Mhz.')

    @property
    def rb_position_dl(self):
        """Gets the position of the allocated down link resource blocks within
        the channel band-width.
        """
        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:RMC:RBPosition:DL?'.format(
                self._bts)
        return self._cmw.send_and_recv(cmd)

    @rb_position_dl.setter
    def rb_position_dl(self, rbpos):
        """Selects the position of the allocated down link resource blocks
        within the channel band-width

        Args:
            rbpos: position of resource blocks.
        """
        if not isinstance(rbpos, RbPosition):
            raise ValueError('rbpos should be the instance of RbPosition.')

        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:RMC:RBPosition:DL {}'.format(
                self._bts, rbpos.value)
        self._cmw.send_and_recv(cmd)

    @property
    def rb_position_ul(self):
        """Gets the position of the allocated up link resource blocks within
        the channel band-width.
        """
        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:RMC:RBPosition:UL?'.format(
                self._bts)
        return self._cmw.send_and_recv(cmd)

    @rb_position_ul.setter
    def rb_position_ul(self, rbpos):
        """Selects the position of the allocated up link resource blocks
        within the channel band-width.

        Args:
            rbpos: position of resource blocks.
        """
        if not isinstance(rbpos, RbPosition):
            raise ValueError('rbpos should be the instance of RbPosition.')

        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:RMC:RBPosition:UL {}'.format(
                self._bts, rbpos.value)
        self._cmw.send_and_recv(cmd)

    @property
    def dci_format(self):
        """Gets the downlink control information (DCI) format."""
        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:DCIFormat?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @dci_format.setter
    def dci_format(self, dci_format):
        """Selects the downlink control information (DCI) format.

        Args:
            dci_format: supported dci.
        """
        if not isinstance(dci_format, DciFormat):
            raise ValueError('dci_format should be the instance of DciFormat.')

        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:DCIFormat {}'.format(
                self._bts, dci_format)
        self._cmw.send_and_recv(cmd)

    @property
    def dl_antenna(self):
        """Gets dl antenna count of cell."""
        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:NENBantennas?'.format(
                self._bts)
        return self._cmw.send_and_recv(cmd)

    @dl_antenna.setter
    def dl_antenna(self, num_antenna):
        """Sets the dl antenna count of cell.

        Args:
            num_antenna: Count of number of dl antennas to use.
        """
        if not isinstance(num_antenna, MimoModes):
            raise ValueError('num_antenna should be an instance of MimoModes.')
        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:NENBantennas {}'.format(
                self._bts, num_antenna.value)
        self._cmw.send_and_recv(cmd)

    @property
    def reduced_pdcch(self):
        """Gets the reduction of PDCCH resources state."""
        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:PDCCh:RPDCch?'.format(
                self._bts)
        return self._cmw.send_and_recv(cmd)

    @reduced_pdcch.setter
    def reduced_pdcch(self, state):
        """Sets the reduction of PDCCH resources state.

        Args:
            state: ON/OFF.
        """
        cmd = 'CONFigure:LTE:SIGN:CONNection:{}:PDCCh:RPDCch {}'.format(
                self._bts, state.value)
        self._cmw.send_and_recv(cmd)

    def tpc_power_control(self, set_type):
        """Set and execute the Up Link Power Control via TPC.

        Args:
            set_type: Type of tpc power control.
        """

        if not isinstance(set_type, TpcPowerControl):
            raise ValueError('set_type should be the instance of '
                             'TpCPowerControl.')
        cmd = 'CONFigure:LTE:SIGN:UL:{}:PUSCh:TPC:SET {}'.format(
                self._bts, set_type.value)
        self._cmw.send_and_recv(cmd)
        cmd = 'CONFigure:LTE:SIGN:UL:{}:PUSCh:TPC:PEXecute'.format(self._bts)
        self._cmw.send_and_recv(cmd)

    @property
    def tpc_closed_loop_target_power(self):
        """Gets the target powers for power control with the TPC setup."""
        cmd = 'CONFigure:LTE:SIGN:UL:{}:PUSCh:TPC:CLTPower?'.format(self._bts)
        return self._cmw.send_and_recv(cmd)

    @tpc_closed_loop_target_power.setter
    def tpc_closed_loop_target_power(self, cltpower):
        """Sets the target powers for power control with the TPC setup.

        Args:
            tpower: Target power.
        """
        cmd = 'CONFigure:LTE:SIGN:UL:{}:PUSCh:TPC:CLTPower {}'.format(
                self._bts, cltpower)
        self._cmw.send_and_recv(cmd)

    @property
    def drx_connected_mode(self):
        """ Gets the Connected DRX LTE cell parameter

        Args:
            None

        Returns:
            DRX connected mode (OFF, AUTO, MANUAL)
        """
        raise NotImplementedError()

    @drx_connected_mode.setter
    def drx_connected_mode(self, mode):
        """  Sets the Connected DRX LTE cell parameter

        Args:
            mode: DRX Connected mode

        Returns:
            None
        """
        raise NotImplementedError()

    @property
    def drx_on_duration_timer(self):
        """ Gets the amount of PDCCH subframes to wait for data after
            waking up from a DRX cycle

        Args:
            None

        Returns:
            DRX mode duration timer
        """
        raise NotImplementedError()

    @drx_on_duration_timer.setter
    def drx_on_duration_timer(self, time):
        """ Sets the amount of PDCCH subframes to wait for data after
            waking up from a DRX cycle

        Args:
            timer: Length of interval to wait for user data to be transmitted

        Returns:
            None
        """
        raise NotImplementedError()

    @property
    def drx_inactivity_timer(self):
        """ Gets the number of PDCCH subframes to wait before entering DRX mode

        Args:
            None

        Returns:
            DRX mode inactivity timer
        """
        raise NotImplementedError()

    @drx_inactivity_timer.setter
    def drx_inactivity_timer(self, time):
        """ Sets the number of PDCCH subframes to wait before entering DRX mode

        Args:
            timer: Length of the interval to wait

        Returns:
            None
        """
        raise NotImplementedError()

    @property
    def drx_retransmission_timer(self):
        """ Gets the number of consecutive PDCCH subframes to wait
        for retransmission

        Args:
            None

        Returns:
            Number of PDCCH subframes to wait for retransmission
        """
        raise NotImplementedError()

    @drx_retransmission_timer.setter
    def drx_retransmission_timer(self, time):
        """ Sets the number of consecutive PDCCH subframes to wait
        for retransmission

        Args:
            time: Number of PDCCH subframes to wait
            for retransmission

        Returns:
            None
        """
        raise NotImplementedError()

    @property
    def drx_long_cycle(self):
        """ Gets the amount of subframes representing a DRX long cycle

        Args:
            None

        Returns:
            The amount of subframes representing one long DRX cycle.
            One cycle consists of DRX sleep + DRX on duration
        """
        raise NotImplementedError()

    @drx_long_cycle.setter
    def drx_long_cycle(self, time):
        """ Sets the amount of subframes representing a DRX long cycle

        Args:
            long_cycle: The amount of subframes representing one long DRX cycle.
                One cycle consists of DRX sleep + DRX on duration

        Returns:
            None
        """
        raise NotImplementedError()

    @property
    def drx_long_cycle_offset(self):
        """ Gets the offset used to determine long cycle starting
        subframe

        Args:
            None

        Returns:
            Long cycle offset
        """
        raise NotImplementedError()

    @drx_long_cycle_offset.setter
    def drx_long_cycle_offset(self, offset):
        """ Sets the offset used to determine long cycle starting
        subframe

        Args:
            offset: Number in range 0...(long cycle - 1)
        """
        raise NotImplementedError()


class LteMeasurement(object):
    """ Class for measuring LTE performance """

    def __init__(self, cmw):
        self._cmw = cmw

    def intitilize_measurement(self):
        """Initialize measurement modules."""
        self._cmw.send_and_recv('INIT:LTE:MEAS:MEValuation')

    @property
    def measurement_repetition(self):
        """Returns the measurement repetition mode that has been set."""
        return self._cmw.send_and_recv(
                'CONFigure:LTE:MEAS:MEValuation:REPetition?')

    @measurement_repetition.setter
    def measurement_repetition(self, mode):
        """Sets the mode for measuring power levels.

        Args:
            mode: Single shot/continuous.
        """
        if not isinstance(mode, RepetitionMode):
            raise ValueError('mode should be the instance of Repetition Mode')

        cmd = 'CONFigure:LTE:MEAS:MEValuation:REPetition {}'.format(mode.value)
        self._cmw.send_and_recv(cmd)

    @property
    def query_measurement_state(self):
        """Returns the states and sub states of measurement."""
        return self._cmw.send_and_recv('FETCh:LTE:MEAS:MEValuation:STATe:ALL?')

    @property
    def measure_tx_power(self):
        """Return the current Tx power measurement."""
        return self._cmw.send_and_recv(
                'FETCh:LTE:MEAS:MEValuation:PMONitor:AVERage?')

    def stop_measurement(self):
        """Stops the on-going measurement.
        This function call does not free up resources allocated for
        measurement. Instead it moves from RUN to RDY state.
        """
        self._cmw.send_and_recv('STOP:LTE:MEAS:MEValuation')

    def abort_measurement(self):
        """Aborts the measurement abruptly.
        This function call will free up the resources allocated for
        measurement and all the results will be wiped off.
        """
        self._cmw.send_and_recv('ABORt:LTE:MEAS:MEValuation')


class CmwError(Exception):
    """Class to raise exceptions related to cmw."""
