// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import React, { useEffect } from 'react';

import PortButtons from './component/portButtons';

import xmlRpcMgr from './managers/xmlrpc';

const App = () => {
  // TODO(kenil): Checks if xmlrpc is working, will remove in future
  useEffect(() => {
    const fetchMacAddress = async () => {
      try {
        const value = await xmlRpcMgr.getMacAddress();
        console.log('Chameleon Mac address:', value);
      } catch (error) {
        console.error('Error:', error);
      }
    };

    fetchMacAddress();
  }, []);

  return (
    <div>
      <p>
        Welcome to <code>Chamelium Control Center</code>
      </p>
      <PortButtons />
    </div>
  );
};

export default App;
