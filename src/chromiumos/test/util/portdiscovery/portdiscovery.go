// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package portdiscovery hosts common code shared by CFT containerized services.
// It provides APIs to write service port number to a metadata file within the
// container that allows clients (e.g. cros-tool-runner) to look up the info.
// More info at go/cft-port-discovery
package portdiscovery

import (
	"errors"
	"fmt"
	"log"
	"os"
	"regexp"
	"time"
)

const (
	// Definitions of keys in the metadata file
	servicePort    = "SERVICE_PORT"
	serviceName    = "SERVICE_NAME"
	serviceVersion = "SERVICE_VERSION"
	startTime      = "# SERVICE_START_TIME" // Debug only, appears as comments.

	// File name of the metadata file
	metaFileName = ".cftmeta"
)

// Metadata represents the data to be written into the metadata file. The data
// will be translated into standardized key value pair and written into the file
// following the format of an env file. All values are in string format and will
// be wrapped with single quotes during the conversion.
// The metadata file is kept at a minimum level for port discovery only as more
// complicated and structured data could/should be surfaced through service end
// points.
// Future extensions may consider adding a Config object to control the behavior
// and a map of free formed key-value pair per container (not recommended unless
// absolutely necessary).
type Metadata struct {
	Port    string // Mandatory
	Name    string // Optional
	Version string // Optional
}

// Api is the interface of the portdiscovery utility.
type Api interface {
	// WriteMetadata writes metadata to a file based on Metadata.
	WriteMetadata(Metadata) error
	// GetPortFromAddress returns the port number of the given the address. The
	// address should be in the format of ".*:port".
	GetPortFromAddress(string) (string, error)
}

// PortDiscovery is an implementation of Api.
type PortDiscovery struct {
	Api
	Logger *log.Logger
}

func (p *PortDiscovery) WriteMetadata(metadata Metadata) error {
	p.getLogger().Printf("info: received metadata %v", metadata)
	if metadata.Port == "" {
		return errors.New("invalid metadata: Port is mandatory")
	}

	metaFile := p.getMetaFilePath()
	f, err := os.OpenFile(metaFile, os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0666)
	if err != nil {
		return err
	}
	defer f.Close()

	_, err = p.writeLine(f, servicePort, metadata.Port)
	if err != nil {
		return err
	}
	_, err = p.writeLine(f, serviceName, metadata.Name)
	if err != nil {
		return err
	}
	_, err = p.writeLine(f, serviceVersion, metadata.Version)
	if err != nil {
		return err
	}
	_, err = p.writeLine(f, startTime, time.Now().Format(time.RFC3339))
	if err != nil {
		return err
	}

	p.getLogger().Printf("info: persisted metadata to %s", metaFile)
	return nil
}

func (p *PortDiscovery) GetPortFromAddress(address string) (string, error) {
	r := regexp.MustCompile(`.*:(\d+)$`)
	match := r.FindStringSubmatch(address)
	if match == nil {
		p.getLogger().Printf("error: cannot apply pattern to address: %s", address)
		return "", errors.New(fmt.Sprintf("unable to get port from %s", address))
	}
	return match[1], nil
}

func (p *PortDiscovery) getLogger() *log.Logger {
	if p.Logger == nil {
		p.Logger = log.Default()
	}
	return p.Logger
}

// writeLine writes a single line to file when value is not empty.
// The format follows the syntax of environment variable declaration:
// KEY=value
// Note that value will always be single quoted.
func (p *PortDiscovery) writeLine(file *os.File, key string, value string) (int, error) {
	if value == "" {
		return 0, nil
	}
	return file.WriteString(fmt.Sprintf("%s='%s'\n", key, value))
}

// getHome returns the home directory path.
func (p *PortDiscovery) getHome() string {
	dirname, err := os.UserHomeDir()
	if err != nil {
		p.getLogger().Printf("warning: error when getting home dir: %s", err)
		return ""
	}
	return dirname
}

// getMetaFilePath returns the full path of metadata file.
func (p *PortDiscovery) getMetaFilePath() string {
	return fmt.Sprintf("%s/%s", p.getHome(), metaFileName)
}

// WriteServiceMetadata simplifies writing service metadata for all cft services. The
// service address should be in the format of ".*:port".
func WriteServiceMetadata(name string, serviceAddress string, logger *log.Logger) error {
	// Write port number to ~/.cftmeta for go/cft-port-discovery
	pdUtil := PortDiscovery{Logger: logger}
	servicePort, _ := pdUtil.GetPortFromAddress(serviceAddress)
	serviceMetadata := Metadata{
		Port: servicePort,
		Name: name,
	}
	err := pdUtil.WriteMetadata(serviceMetadata)
	return err
}
