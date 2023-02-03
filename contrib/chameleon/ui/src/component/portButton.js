// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import React, { useState } from 'react';
import PropTypes from 'prop-types';

import './button.css';

const PortState = {
  PLUGGED: 'plugged',
  UNPLUGGED: 'unplugged',
  DISCONNECTED: 'disconnected',
};

const stateToColor = {
  [PortState.PLUGGED]: 'green',
  [PortState.UNPLUGGED]: 'red',
  [PortState.DISCONNECTED]: 'gray',
};

const portIdToPortType = {
  0: 'dp',
  1: 'dp',
  2: 'hdmi',
  3: 'hdmi',
};

const portTypeToClassName = {
  dp: 'dpPortButton',
  hdmi: 'hdmiPortButton',
};

const PortButton = ({ label, portId }) => {
  const [plugState, setPlugState] = useState(PortState.UNPLUGGED);

  const onButtonClicked = () => {
    setPlugState(plugState === PortState.UNPLUGGED ? PortState.PLUGGED : PortState.UNPLUGGED);
  };

  return (
    <button
      className={portTypeToClassName[portIdToPortType[portId]]}
      style={{ backgroundColor: stateToColor[plugState] }}
      onClick={onButtonClicked}>
      {label}
    </button>
  );
};

PortButton.propTypes = {
  label: PropTypes.string.isRequired,
  portId: PropTypes.number.isRequired,
};

export default PortButton;
