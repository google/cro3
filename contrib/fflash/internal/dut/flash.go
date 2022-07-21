// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dut

import (
	"bufio"
	"compress/gzip"
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strconv"
	"time"

	"cloud.google.com/go/storage"
	"golang.org/x/oauth2"
	"google.golang.org/api/option"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/progress"
)

// Request contains everything needed to perform a flash.
type Request struct {
	// Base time when the flash started, for logging.
	ElapsedTimeWhenSent time.Duration
	Token               *oauth2.Token
	Bucket              string
	Object              string
}

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

func (r *Request) Flash(ctx context.Context, rw *progress.ReportingWriter, imageGz string, partition string) error {
	client, err := storage.NewClient(ctx,
		option.WithTokenSource(oauth2.StaticTokenSource(r.Token)),
	)
	if err != nil {
		return fmt.Errorf("storage.NewClient failed: %s", err)
	}

	obj := client.Bucket(r.Bucket).Object(path.Join(r.Object, imageGz))

	rd, err := obj.NewReader(ctx)
	if err != nil {
		return fmt.Errorf("obj.NewReader failed: %s", err)
	}
	rw.SetTotal(rd.Attrs.Size)

	brd := bufio.NewReader(io.TeeReader(rd, rw))

	gzRd, err := gzip.NewReader(brd)
	if err != nil {
		return fmt.Errorf("gzip.NewReader failed: %s", err)
	}

	w, err := os.OpenFile(partition, os.O_WRONLY, 0660)
	if err != nil {
		return fmt.Errorf("cannot open %s: %s", partition, err)
	}
	defer func() {
		if err := w.Close(); err != nil {
			panic(err)
		}
	}()

	if _, err := copyChunked(w, gzRd, make([]byte, 1<<20)); err != nil {
		return fmt.Errorf("copy to %s failed: %s", partition, err)
	}

	return nil
}

func (r *Request) FlashStateful(ctx context.Context, rw *progress.ReportingWriter) error {
	client, err := storage.NewClient(ctx,
		option.WithTokenSource(oauth2.StaticTokenSource(r.Token)),
	)
	if err != nil {
		return fmt.Errorf("storage.NewClient failed: %s", err)
	}

	obj := client.Bucket(r.Bucket).Object(path.Join(r.Object, StatefulImage))

	rd, err := obj.NewReader(ctx)
	if err != nil {
		return fmt.Errorf("obj.NewReader failed: %s", err)
	}
	rw.SetTotal(rd.Attrs.Size)

	brd := bufio.NewReader(io.TeeReader(rd, rw))

	if err := unpackStateful(ctx, brd); err != nil {
		return err
	}

	if err := os.WriteFile(
		filepath.Join(statefulDir, statefulAvailable),
		[]byte("clobber"),
		0644,
	); err != nil {
		return fmt.Errorf("failed to write %s: %s", statefulAvailable, err)
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

	cmd := exec.CommandContext(ctx, filepath.Join(dir, "postinst"), partition)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
}

func DisableRootfsVerification(ctx context.Context, kernelNum int) error {
	cmd := exec.CommandContext(ctx,
		"/usr/share/vboot/bin/make_dev_ssd.sh",
		"--remove_rootfs_verification",
		"--partitions", strconv.Itoa(kernelNum),
	)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to disable rootfs verification: %s", err)
	}
	return nil
}
