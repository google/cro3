// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import React from 'react';
import PropTypes from 'prop-types';

import {
  PORT_STATE,
  PORT_TYPE_TO_CLASSNAME,
  PORT_ID_TO_PORT_TYPE,
  STATE_TO_COLOR,
} from '../consts/plugButtonConstants';

import './button.css';

const PortButton = ({ label, portId, plugState, setPlugState }) => {
  const onButtonClicked = () => {
    setPlugState(plugState === PORT_STATE.UNPLUGGED ? PORT_STATE.PLUGGED : PORT_STATE.UNPLUGGED);
  };

  return (
    <button
      className={PORT_TYPE_TO_CLASSNAME[PORT_ID_TO_PORT_TYPE[portId]]}
      style={{ backgroundColor: STATE_TO_COLOR[plugState] }}
      onClick={onButtonClicked}>
      {label}
    </button>
  );
};

PortButton.propTypes = {
  label: PropTypes.string.isRequired,
  portId: PropTypes.number.isRequired,
  plugState: PropTypes.string.isRequired,
  setPlugState: PropTypes.func.isRequired,
};

export default PortButton;
