// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import React from 'react';
import PropTypes from 'prop-types';

import './resetButton.css';

const ResetButton = ({ onResetButtonClicked }) => {
  return (
    <button className='resetButton' onClick={onResetButtonClicked}>
      Reset
    </button>
  );
};

ResetButton.propTypes = {
  onResetButtonClicked: PropTypes.func.isRequired,
};

export default ResetButton;
