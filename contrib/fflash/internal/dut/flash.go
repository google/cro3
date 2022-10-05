// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dut

import (
	"compress/gzip"
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"path"
	"path/filepath"
	"strconv"
	"syscall"
	"time"

	"cloud.google.com/go/storage"
	"github.com/klauspost/readahead"
	"golang.org/x/oauth2"
	"google.golang.org/api/option"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/misc"
	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/progress"
)

// Request contains everything needed to perform a flash.
type Request struct {
	// Base time when the flash started, for logging.
	ElapsedTimeWhenSent time.Duration

	Token           *oauth2.Token
	Bucket          string
	Directory       string
	ClearTpmOwner   bool
	ClobberStateful bool
}

type Result struct {
	RetryDisableRootfsVerification bool
	RetryClearTpmOwner             bool
}

// copyChunked copies r to w in chunks.
func copyChunked(w io.Writer, r io.Reader, buf []byte) (written int64, err error) {
	for {
		n, err := io.ReadFull(r, buf)
		if err != nil && err != io.ErrUnexpectedEOF {
			if err == io.EOF {
				break
			}
			return written, err
		}
		if m, err := w.Write(buf[:n]); err != nil {
			return written, err
		} else {
			written += int64(m)
		}
	}
	return written, nil
}

type closeFunc func() error

// Client creates a storage.Client from req.
func (req *Request) Client(ctx context.Context) (*storage.Client, error) {
	client, err := storage.NewClient(ctx,
		option.WithTokenSource(oauth2.StaticTokenSource(req.Token)),
	)
	if err != nil {
		return nil, fmt.Errorf("storage.NewClient failed: %w", err)
	}

	return client, nil
}

// object returns the storage.ObjectHandle for the file in the directory specified by req.
func (req *Request) object(client *storage.Client, name string) *storage.ObjectHandle {
	return client.Bucket(req.Bucket).Object(path.Join(req.Directory, name))
}

// openObject opens the file in the the directory specified by req.
func (req *Request) openObject(ctx context.Context, client *storage.Client, rw *progress.ReportingWriter, name string, decompress bool) (io.Reader, closeFunc, error) {
	obj := req.object(client, name)

	rd, err := obj.NewReader(ctx)
	if err != nil {
		return nil, nil, fmt.Errorf("obj.NewReader for %s failed: %w", misc.GsURI(obj), err)
	}
	rw.SetTotal(rd.Attrs.Size)

	aheadRd, err := readahead.NewReadCloserSize(rd, 4, 1<<20)
	if err != nil {
		rd.Close()
		return nil, nil, fmt.Errorf(
			"readahead.NewReadCloserSize for %s failed: %w", misc.GsURI(obj), err)
	}

	brd := io.TeeReader(aheadRd, rw)

	var gzRd io.ReadCloser
	if decompress {
		gzRd, err = gzip.NewReader(brd)
		if err != nil {
			rd.Close()
			return nil, nil, fmt.Errorf("gzip.NewReader for %s failed: %w", misc.GsURI(obj), err)
		}
	} else {
		gzRd = io.NopCloser(brd)
	}

	return gzRd,
		func() error {
			gzRd.Close()
			return aheadRd.Close()
		},
		nil
}

// Check access to Cloud Storage files.
func (req *Request) Check(ctx context.Context, client *storage.Client) error {
	for _, file := range []string{KernelImage, RootfsImage, StatefulImage} {
		obj := req.object(client, file)

		if _, err := obj.Attrs(ctx); err != nil {
			return fmt.Errorf("error checking access: %s: %w", misc.GsURI(obj), err)
		}
	}
	return nil
}

// Flash a partition with imageGz to partition.
func (req *Request) Flash(ctx context.Context, client *storage.Client, rw *progress.ReportingWriter, imageGz string, partition string) error {
	r, close, err := req.openObject(ctx, client, rw, imageGz, true)
	if err != nil {
		return err
	}
	defer close()

	w, err := os.OpenFile(partition, os.O_WRONLY|syscall.O_DIRECT, 0660)
	if err != nil {
		return fmt.Errorf("cannot open %s: %w", partition, err)
	}
	defer func() {
		if err := w.Close(); err != nil {
			panic(err)
		}
	}()

	if _, err := copyChunked(w, r, make([]byte, 1<<20)); err != nil {
		return fmt.Errorf("copy to %s failed: %w", partition, err)
	}

	return nil
}

// FlashStateful flashes the stateful partition.
func (req *Request) FlashStateful(ctx context.Context, client *storage.Client, rw *progress.ReportingWriter, clobber bool) error {
	r, close, err := req.openObject(ctx, client, rw, StatefulImage, false)
	if err != nil {
		return err
	}
	defer close()

	if err := unpackStateful(ctx, r); err != nil {
		return err
	}

	content := ""
	if clobber {
		content = "clobber"
	}

	if err := os.WriteFile(
		filepath.Join(statefulDir, statefulAvailable),
		[]byte(content),
		0644,
	); err != nil {
		return fmt.Errorf("failed to write %s: %w", statefulAvailable, err)
	}

	return nil
}

// RunPostinst runs "postinst" from the partition.
func RunPostinst(ctx context.Context, partition string) error {
	dir, err := os.MkdirTemp("/tmp", "dut-agent-*")
	if err != nil {
		return err
	}

	if _, err := runCommand(ctx, "mount", "-o", "ro", partition, dir); err != nil {
		return err
	}
	defer func() {
		if _, err := runCommand(context.Background(), "umount", partition); err != nil {
			log.Printf("failed to unmount rootfs: %s", err)
		}
	}()

	return runCommandStderr(ctx, filepath.Join(dir, "postinst"), partition)
}

func DisableRootfsVerification(ctx context.Context, kernelNum int) error {
	return runCommandStderr(ctx,
		"/usr/share/vboot/bin/make_dev_ssd.sh",
		"--remove_rootfs_verification",
		"--partitions", strconv.Itoa(kernelNum),
	)
}

func ClearTpmOwner(ctx context.Context) error {
	return runCommandStderr(ctx,
		"crossystem",
		"clear_tpm_owner_request=1",
	)
}
