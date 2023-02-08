// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import React, { useState } from 'react';

import PortButton from './portButton';
import ResetButton from './resetButton';

import { PORT_STATE } from '../consts/plugButtonConstants';

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

  return (
    <div>
      <div>
        <PortButton label={'DP1'} portId={0} plugState={plugState0} setPlugState={setPlugState0} />
        <PortButton label={'DP2'} portId={1} plugState={plugState1} setPlugState={setPlugState1} />
      </div>
      <div>
        <PortButton
          label={'HDMI1'}
          portId={2}
          plugState={plugState2}
          setPlugState={setPlugState2}
        />
        <PortButton
          label={'HDMI2'}
          portId={3}
          plugState={plugState3}
          setPlugState={setPlugState3}
        />
      </div>
      <ResetButton onResetButtonClicked={onResetButtonClicked} />
    </div>
  );
};

export default PortButtons;
