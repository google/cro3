// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package device implements utilities to extract device information.
package device

import (
	"errors"
	"fmt"
	"net"
	"strconv"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
	labapi "go.chromium.org/chromiumos/config/go/test/lab/api"
)

// DutInfo stores
type DutInfo struct {
	Addr                string   // The address of the DUT.
	Role                string   // The role of the DUT.
	Servo               string   // The address of the servo.
	DutServer           string   // The address of the dutServer.
	LibsServer          string   // The address of the libsServer.
	ProvisionServer     string   // The address of the provision server
	Board               string   // The board of the DUT
	Model               string   // The model of the DUT
	ServoHostname       string   // The hostname of the Servo paired with the DUT
	ServoPort           string   // The port of the Servo paired with the DUT
	ServoSerial         string   // The serial of the Servo paired with the DUT
	ChameleonAudio      bool     // If the DUT has a ChameleonAudio peripheral
	ChamelonPresent     bool     // If the DUT has a Chameleon peripheral
	ChamelonPeriphsList []string // The list of Chameleon peripherals
	AtrusAudio          bool     // If the DUT has a AtrusAudio label
	TouchMimo           bool     // If the DUT has a TouchMimo label
	CameraboxFacing     string   // The direction the camerabox is facing, ie "front" or "back"
	CableList           []string // The list of cables attached
	CarrierList         []string // the list of carriers
	HwIDList            []string // HwIDlist
	Sku                 string
	Phase               string
	BTPeers             int
	CacheServer         string
	HWID                string
}

// joinHostAndPort joins host and port to a single address.
// Example 1: "127.0.0.1" "" -> "127.0.0.1".
// Example 2: "0:0:0:0:0:ffff:7f00:1" "2" -> "[0:0:0:0:0:ffff:7f00:1]:2".
// Example 3: "0:0:0:0:0:ffff:7f00:1" "" -> 0:0:0:0:0:ffff:7f00:1"
func joinHostAndPort(endpoint *labapi.IpEndpoint) string {
	if endpoint.Port == 0 {
		return endpoint.Address
	}
	return net.JoinHostPort(endpoint.Address, strconv.Itoa(int(endpoint.Port)))
}

// Address returns the address of a DUT.
// TODO: Remove this after no test drivers are using this.
func Address(device *api.CrosTestRequest_Device) (string, error) {
	if device == nil {
		return "", errors.New("requested device is nil")
	}
	dut := device.Dut
	if dut == nil {
		return "", errors.New("DUT is nil")
	}
	chromeOS := dut.GetChromeos()
	if chromeOS == nil {
		return "", fmt.Errorf("DUT does not have end point information: %v", dut)
	}
	return joinHostAndPort(chromeOS.Ssh), nil

}

// FillDUTInfo extraction DUT information from a device.
func FillDUTInfo(device *api.CrosTestRequest_Device, role string) (*DutInfo, error) {
	if device == nil {
		return nil, errors.New("requested device is nil")
	}
	dut := device.Dut
	if dut == nil {
		return nil, errors.New("DUT is nil")
	}
	chromeOS := dut.GetChromeos()
	if chromeOS == nil {
		return nil, fmt.Errorf("DUT does not have end point information: %v", dut)
	}

	cacheInfo := dut.GetCacheServer()

	addr := joinHostAndPort(chromeOS.Ssh)

	// Servo address.
	var servo string
	var servoHostname string
	var servoPort string
	var servoSerial string
	if chromeOS.Servo != nil && chromeOS.Servo.ServodAddress != nil {
		servo = joinHostAndPort(chromeOS.Servo.ServodAddress)
		servoHostname = strings.ToLower(chromeOS.Servo.ServodAddress.Address)
		servoPort = fmt.Sprintf("%v", chromeOS.Servo.ServodAddress.Port)
		servoSerial = chromeOS.Servo.Serial
	}

	// DUT Server address.
	var dutServer string
	if device.DutServer != nil {
		dutServer = joinHostAndPort(device.DutServer)
	}
	// DUT Server address.
	var libsServer string
	if device.LibsServer != nil {
		libsServer = joinHostAndPort(device.LibsServer)
	}
	// Provision server address.
	var provisionServer string
	if device.ProvisionServer != nil {
		provisionServer = joinHostAndPort(device.ProvisionServer)
	}
	var board string
	var model string
	if chromeOS.DutModel != nil {
		board = chromeOS.DutModel.BuildTarget
		model = chromeOS.DutModel.ModelName
	}

	// - Chameleon

	var chameleonAudio bool
	var chamelonPresent bool
	var chamelonPeriphsList []string
	if chromeOS.Chameleon != nil {
		if chromeOS.Chameleon.AudioBoard {
			chameleonAudio = true
		}

		if len(chromeOS.Chameleon.Peripherals) > 0 {
			chamelonPresent = true
			for _, v := range chromeOS.Chameleon.Peripherals {
				lv := "chameleon:" + strings.ToLower(v.String())
				chamelonPeriphsList = append(chamelonPeriphsList, lv)
			}
		}
	}

	var atrusAudio bool
	if audio := chromeOS.Audio; audio != nil {
		if audio.Atrus {
			atrusAudio = true
		}
	}

	var touchMimo bool
	if touch := chromeOS.Touch; touch != nil {
		if touch.Mimo {
			touchMimo = true
		}
	}

	var cameraboxFacing string
	if camerabox := chromeOS.Camerabox; camerabox != nil {
		facing := camerabox.Facing
		cameraboxFacing = strings.ToLower(facing.String())
	}

	var cableList []string
	if cables := chromeOS.Cables; len(cables) > 0 {
		for _, v := range cables {
			// TODO: Figure out why this proto has an empty space at end
			// eg. USBAUDIO is returning "USBAUDIO "
			cableList = append(cableList, strings.Trim(strings.ToLower(v.String()), " "))
		}
	}

	var carriers []string
	if car := chromeOS.Cellular; car != nil {
		if len(car.Operators) > 0 {
			for _, v := range car.Operators {
				lv := "carrier:" + strings.ToLower(v.String())
				carriers = append(carriers, lv)

			}

		}
	}

	var hwids []string
	if hwid := chromeOS.HwidComponent; len(hwid) > 0 {
		for _, v := range hwid {
			// TODO: Figure out why this proto has an empty space at end
			// eg. USBAUDIO is returning "USBAUDIO "
			lv := "hwid_component:" + strings.ToLower(v)
			hwids = append(hwids, lv)
		}
	}

	sku := chromeOS.Sku

	var phase string
	phase = strings.ToUpper(chromeOS.Phase.String())

	hwid := string(chromeOS.Hwid)

	btpeers := 0
	if peers := chromeOS.BluetoothPeers; len(peers) > 0 {
		for _, v := range peers {
			state := v.State
			if strings.ToLower(state.String()) == "working" {
				btpeers++
			}
		}
	}

	cacheServer := ""
	if cacheInfo != nil {
		cacheServer = fmt.Sprintf("%v:%v", cacheInfo.GetAddress().Address, cacheInfo.GetAddress().Port)

	}

	return &DutInfo{
		Addr:                addr,
		Role:                role,
		Servo:               servo,
		DutServer:           dutServer,
		LibsServer:          libsServer,
		ProvisionServer:     provisionServer,
		Board:               board,
		Model:               model,
		ServoHostname:       servoHostname,
		ServoPort:           servoPort,
		ServoSerial:         servoSerial,
		ChameleonAudio:      chameleonAudio,
		ChamelonPresent:     chamelonPresent,
		ChamelonPeriphsList: chamelonPeriphsList,
		AtrusAudio:          atrusAudio,
		TouchMimo:           touchMimo,
		CameraboxFacing:     cameraboxFacing,
		CableList:           cableList,
		CarrierList:         carriers,
		HwIDList:            hwids,
		Sku:                 sku,
		Phase:               phase,
		BTPeers:             btpeers,
		CacheServer:         cacheServer,
		HWID:                hwid,
	}, nil
}
