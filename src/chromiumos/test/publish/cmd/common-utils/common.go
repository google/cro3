// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common_utils

import (
	"context"
	"fmt"
	"log"
	"os"
	"path"

	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/proto"
)

// GetValueBoolMap creates a reverse map of inputMap. Any value in inputMap will be a key in the returned map.
func GetValueBoolMap(inputMap map[string]string) map[string]bool {
	retMap := map[string]bool{}
	for _, v := range inputMap {
		retMap[v] = true
	}
	return retMap
}

// IsSubsetOf returns if smallerMap is a subset of biggerMap.
func IsSubsetOf(smallerMap map[string]bool, biggerMap map[string]bool) bool {
	if len(smallerMap) > len(biggerMap) {
		return false
	}

	for k, _ := range smallerMap {
		if _, ok := biggerMap[k]; !ok {
			return false
		}
	}

	return true
}

// MakeTempDir creates a temp directory at parentDirPath
func MakeTempDir(ctx context.Context, parentDirPath string, newDirName string) (string, error) {
	newDirPath, err := os.MkdirTemp(parentDirPath, newDirName)
	if err != nil {
		return "", fmt.Errorf("error during creating temp dir %q: %s", newDirName, err.Error())
	}
	return newDirPath, nil
}

// WriteProtoToJsonFile writes the provided proto to a json file
func WriteProtoToJsonFile(ctx context.Context, dirPath string, fileName string, inputProto proto.Message) (string, error) {
	protoFilePath := path.Join(dirPath, fileName)
	f, err := os.Create(protoFilePath)
	if err != nil {
		return "", fmt.Errorf("error during creating file %q: %s", fileName, err.Error())
	}
	defer f.Close()

	bytes, err := protojson.Marshal(inputProto)
	if err != nil {
		return "", fmt.Errorf("error during marshalling proto for %q: %s", fileName, err.Error())
	}

	_, err = f.Write(bytes)
	if err != nil {
		return "", fmt.Errorf("error during writing proto to file %q: %s", fileName, err.Error())
	}

	log.Printf("proto successfully written to file: %s", bytes)

	err = f.Close()
	if err != nil {
		return "", fmt.Errorf("error during closing file %q: %s", fileName, err.Error())
	}

	return protoFilePath, nil
}
