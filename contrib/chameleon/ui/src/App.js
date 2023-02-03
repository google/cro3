// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import React from 'react';

import PortButton from './component/portButton';

const App = () => {
  return (
    <div>
      <p>
        Welcome to <code>Chamelium Control Center</code>
      </p>
      <div>
        <PortButton label={'DP1'} portId={0} />
        <PortButton label={'DP2'} portId={1} />
      </div>
      <div>
        <PortButton label={'HDMI1'} portId={2} />
        <PortButton label={'HDMI2'} portId={3} />
      </div>
    </div>
  );
};

export default App;
