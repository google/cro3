// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

const Client = require('react-native-xmlrpc');

const HOST_URL = 'http://localhost:9992';

class XmlRpcMgr {
  client = null;

  constructor() {
    this.client = new Client(HOST_URL);
  }

  async getMacAddress() {
    return new Promise((resolve, reject) => {
      this.client.call('GetMacAddress', null, (error, value) => {
        if (error) {
          reject(error);
        } else {
          resolve(value);
        }
      });
    });
  }
}

const xmlRpcMgr = new XmlRpcMgr();

export default xmlRpcMgr;
