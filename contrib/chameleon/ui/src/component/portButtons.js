// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import React, { useState } from 'react';

import EdidButton from './edidButton';
import PortButton from './portButton';
import ResetButton from './resetButton';

import { PORT_STATE, PORT_LABELS } from '../consts/plugButtonConstants';

import './button.css';

const PortButtons = () => {
  const [plugState0, setPlugState0] = useState(PORT_STATE.UNPLUGGED);
  const [plugState1, setPlugState1] = useState(PORT_STATE.UNPLUGGED);
  const [plugState2, setPlugState2] = useState(PORT_STATE.UNPLUGGED);
  const [plugState3, setPlugState3] = useState(PORT_STATE.UNPLUGGED);

  const onResetButtonClicked = () => {
    setPlugState0(PORT_STATE.UNPLUGGED);
    setPlugState1(PORT_STATE.UNPLUGGED);
    setPlugState2(PORT_STATE.UNPLUGGED);
    setPlugState3(PORT_STATE.UNPLUGGED);
  };

  const renderPortButton = (className, label, portId, plugState, setPlugState) => {
    return (
      <div className={className}>
        <div className='edidButton'>
          <EdidButton portId={portId} />
        </div>
        <div>
          <PortButton
            label={label}
            portId={portId}
            plugState={plugState}
            setPlugState={setPlugState}
          />
        </div>
      </div>
    );
  };

  return (
    <div>
      <div className='row'>
        {renderPortButton('rowPortButton', PORT_LABELS.DP1, 0, plugState0, setPlugState0)}
        {renderPortButton('rowPortButtonReverse', PORT_LABELS.DP2, 1, plugState1, setPlugState1)}
      </div>
      <div className='row'>
        {renderPortButton('rowPortButton', PORT_LABELS.HDMI1, 2, plugState2, setPlugState2)}
        {renderPortButton('rowPortButtonReverse', PORT_LABELS.HDMI2, 3, plugState3, setPlugState3)}
      </div>
      <ResetButton onResetButtonClicked={onResetButtonClicked} />
    </div>
  );
};

export default PortButtons;
