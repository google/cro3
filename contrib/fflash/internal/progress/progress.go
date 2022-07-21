// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package progress

import (
	"bytes"
	"fmt"
	"io"
	"log"
	"strings"
	"sync"
	"time"
)

func formatSize(n int64) string {
	f := float64(n)
	var unit string
	for _, unit = range []string{"B", "KB", "MB", "GB", "TB"} {
		if f < 1000 {
			break
		}
		f /= 1000
	}
	return strings.TrimRight(fmt.Sprintf("%#.3g", f), ".") + unit
}

// formatSize2 formats n, total as n/total, optionally with a size suffix.
func formatSize2(n, total int64) string {
	if n == total {
		return formatSize(n)
	}
	return fmt.Sprintf("%s/%s", formatSize(n), formatSize(total))
}

type progressWriter struct {
	name       string
	n          int64
	lastUpdate time.Time
	total      int64
}

var _ io.WriteCloser = &progressWriter{}

// NewWriter creates a Writer that tracks the progress by the Write() call.
func NewWriter(name string, total int64) io.WriteCloser {
	return &progressWriter{
		name:  name,
		total: total,
	}
}

func (w *progressWriter) Write(b []byte) (int, error) {
	w.n += int64(len(b))

	now := time.Now()
	if now.Sub(w.lastUpdate) > time.Second {
		w.Close()
		w.lastUpdate = now
	}

	return len(b), nil
}

func (w *progressWriter) Close() error {
	log.Printf(
		"[%s]  %5.1f%%  %s\n",
		w.name,
		100*float64(w.n)/float64(w.total),
		formatSize2(w.n, w.total),
	)
	return nil
}

// ProgressReporter aggregates the progress of multiple ReportingWriters.
type ProgressReporter struct {
	sources []*ReportingWriter
}

// Report returns the aggregated progress of r.
func (r *ProgressReporter) Report() string {
	var b bytes.Buffer
	var gN int64
	var gTotal int64
	for i, w := range r.sources {
		if i > 0 {
			b.WriteString(" ")
		}
		stats, n, total := w.Stats()
		b.WriteString(stats)
		gN += n
		gTotal += total
	}
	if gTotal == 0 {
		gTotal = 1 // prevent div by zero
	}
	return fmt.Sprintf("%5.1f%% %s", float64(gN)/float64(gTotal)*100, b.String())
}

// NewWriter creates a ReportingWriter reporting to r.
func (r *ProgressReporter) NewWriter(name string) *ReportingWriter {
	rw := &ReportingWriter{
		name: name,
	}
	r.sources = append(r.sources, rw)
	return rw
}

// ReportingWriter is an io.Writer which reports its progress to a ProgressWriter.
type ReportingWriter struct {
	mutex sync.Mutex
	name  string
	n     int64
	total int64
}

var _ io.Writer = &ReportingWriter{}

// SetTotal sets to total size to be written to w.
func (w *ReportingWriter) SetTotal(total int64) {
	w.mutex.Lock()
	w.total = total
	w.mutex.Unlock()
}

func (w *ReportingWriter) Write(b []byte) (int, error) {
	w.mutex.Lock()
	defer w.mutex.Unlock()

	w.n += int64(len(b))
	return len(b), nil
}

// Stats returns the local statistics to w.
func (w *ReportingWriter) Stats() (stats string, n, total int64) {
	w.mutex.Lock()
	defer w.mutex.Unlock()

	return fmt.Sprintf("[%s %s]", w.name, formatSize2(w.n, w.total)), w.n, w.total
}
