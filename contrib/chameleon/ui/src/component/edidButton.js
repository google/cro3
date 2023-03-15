// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import React, { useState } from 'react';
import Modal from 'react-modal';
import PropTypes from 'prop-types';

import { PORT_ID_TO_PORT_TYPE } from '../consts/plugButtonConstants';

import './edidButton.css';

Modal.setAppElement('#root');

const EdidButton = ({ portId }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedEdid, setSelectedEdid] = useState('');
  const [customText, setCustomText] = useState('');

  const dpEdidOptions = [
    { value: 'HP1234D', label: 'HP 1234D (monitor with 4k and 144Hz)' },
    { value: 'LENOVO1234D', label: 'ThinkVision 1234D (monitor with 4k and 75Hz)' },
    { value: 'DELL1234D', label: 'DELL 1234D (monitor with 4k and 90Hz)' },
    { value: 'ASUS1234D', label: 'ASUS 1234D (monitor with 4k and 60Hz)' },
  ];

  const hdmiEdidOptions = [
    { value: 'HP1234H', label: 'HP 1234H (monitor with 4k and 144Hz)' },
    { value: 'LENOVO1234H', label: 'ThinkVision 1234H (monitor with 4k and 75Hz)' },
    { value: 'DELL1234H', label: 'DELL 1234H (monitor with 4k and 90Hz)' },
    { value: 'ASUS1234H', label: 'ASUS 1234H (monitor with 4k and 60Hz)' },
  ];

  const edidOptions = PORT_ID_TO_PORT_TYPE[portId] == 'DP' ? dpEdidOptions : hdmiEdidOptions;

  const handleEdidChange = (event) => {
    setSelectedEdid(event.target.value);
  };

  const handleEdidSave = () => {
    // Todo: Apply EDID options to actual hardware
    console.log(`EDID for Port ${portId}: Option - ${selectedEdid}, Custom Text - ${customText}`);
    setIsModalOpen(false);
  };

  const renderSelectionModal = () => {
    return (
      <Modal
        isOpen={isModalOpen}
        onRequestClose={() => setIsModalOpen(false)}
        className='modal'
        overlayClassName='overlay'>
        <div>
          <h2>Set EDID</h2>
          <div>
            {edidOptions.map((option, index) => (
              <label key={index} className='radioLabel'>
                <input
                  type='radio'
                  value={option.value}
                  checked={selectedEdid === option.value}
                  onChange={handleEdidChange}
                />
                {option.label}
              </label>
            ))}
            <label className='radioLabel'>
              <input
                type='radio'
                value='customEdidText'
                checked={selectedEdid === 'customEdidText'}
                onChange={handleEdidChange}
              />
              Custom Edid
            </label>
          </div>
          {selectedEdid === 'customEdidText' && (
            <textarea
              placeholder='Custom Edid'
              className='customTextField'
              onChange={(e) => setCustomText(e.target.value)}
            />
          )}
          <div>
            <button className='cancelButton' onClick={() => setIsModalOpen(false)}>
              Cancel
            </button>
            <button className='saveButton' onClick={handleEdidSave}>
              Save
            </button>
          </div>
        </div>
      </Modal>
    );
  };

  const renderSetEdidButton = () => {
    return (
      <button className='edidButtons' onClick={() => setIsModalOpen(true)}>
        Set EDID
      </button>
    );
  };

  return (
    <div className='edidButtonContainer'>
      {renderSetEdidButton()}
      {renderSelectionModal()}
    </div>
  );
};

EdidButton.propTypes = {
  portId: PropTypes.number.isRequired,
};

export default EdidButton;
