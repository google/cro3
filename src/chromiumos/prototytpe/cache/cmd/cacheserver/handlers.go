// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"

	"golang.org/x/sys/unix"
)

const (
	sourceURLKey        = "source_url"
	downloadPrefix      = "/download/"
	downloadLocalPrefix = "/download-local/"
)

type HttpHandlers struct {
	cache *Cache
}

// InstantiateHandlers creates the caching layer, sets up the HTTP handlers,
// and sets it so the cache gets destroyed on sigterm (i.e.: deletes files)
func InstantiateHandlers(port int, cacheLocation string) error {
	cache, err := MakeCache(cacheLocation)
	if err != nil {
		return fmt.Errorf("could not create cache, %w", err)
	}
	defer cache.Close()

	// Clean up on SIGINT and SIGTERM
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, unix.SIGTERM)
	go func() {
		<-c
		cache.Close()
		os.Exit(1)
	}()

	// TODO(jaquesc): Add SSL (currently unnecessary for localhost)
	h := HttpHandlers{
		cache: cache,
	}

	http.HandleFunc(downloadPrefix, h.cacheGSHandler)
	http.HandleFunc(downloadLocalPrefix, h.cacheLocalHandler)

	if err := http.ListenAndServe(fmt.Sprintf(":%d", port), nil); err != nil {
		return err
	}

	return nil
}

// cacheGSHandler handles the cache for GS
func (h *HttpHandlers) cacheGSHandler(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		h.getCacheGSHandler(w, r)
	default:
		http.Error(w, "Only GETs are supported.", http.StatusNotFound)
	}
}

// getCacheGSHandler handles GET requests to GS cache
func (h *HttpHandlers) getCacheGSHandler(w http.ResponseWriter, r *http.Request) {
	log.Print("got GET request for GS file")
	gsPath := strings.TrimPrefix(r.URL.EscapedPath(), downloadPrefix)
	if gsPath == "" {
		http.Error(w, "URL must have a path to download", http.StatusUnprocessableEntity)
		return
	}
	localPath, err := h.cache.Get(gsPath)
	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to cache %s, %v", gsPath, err), http.StatusBadRequest)
		return
	}

	fr, err := os.OpenFile(localPath, os.O_RDONLY, 0644)
	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to open local cache %s, %v", localPath, err), http.StatusInternalServerError)
		return
	}
	defer fr.Close()

	log.Printf("sending file, %s", localPath)
	// Internal impl should stream here
	io.Copy(w, fr)
	log.Printf("sent file, %s", localPath)
}

// cacheLocalHandler handles the cache for local files
func (h *HttpHandlers) cacheLocalHandler(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		h.getCacheLocalHandler(w, r)
	default:
		http.Error(w, "Only GETs are supported.", http.StatusNotFound)
	}
}

// getCacgeLocalHandler handles GET requests to local files
func (h *HttpHandlers) getCacheLocalHandler(w http.ResponseWriter, r *http.Request) {
	log.Print("got GET request for local file")
	localPath := r.URL.Query().Get(sourceURLKey)
	if localPath == "" {
		http.Error(w, fmt.Sprintf("URL must have an option with %s field", sourceURLKey), http.StatusUnprocessableEntity)
	}
	fr, err := os.OpenFile(localPath, os.O_RDONLY, 0644)
	if err != nil {
		http.Error(w, fmt.Sprintf("Unable to open local file %s, %v", localPath, err), http.StatusBadRequest)
	}
	defer fr.Close()

	log.Printf("sending file, %s", localPath)
	// Internal impl should stream here
	io.Copy(w, fr)
	log.Printf("sent file, %s", localPath)
}
