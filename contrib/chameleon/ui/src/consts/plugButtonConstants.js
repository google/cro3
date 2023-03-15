// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

export const PORT_STATE = {
  PLUGGED: 'plugged',
  UNPLUGGED: 'unplugged',
  DISCONNECTED: 'disconnected',
};

export const STATE_TO_COLOR = {
  [PORT_STATE.PLUGGED]: 'green',
  [PORT_STATE.UNPLUGGED]: 'red',
  [PORT_STATE.DISCONNECTED]: 'gray',
};

export const PORT_ID_TO_PORT_TYPE = {
  0: 'DP',
  1: 'DP',
  2: 'HDMI',
  3: 'HDMI',
};

export const PORT_LABELS = {
  DP1: 'DP1',
  DP2: 'DP2',
  HDMI1: 'HDMI1',
  HDMI2: 'HDMI2',
};

export const PORT_TYPE_TO_CLASSNAME = {
  DP: 'dpPortButton',
  HDMI: 'hdmiPortButton',
};
