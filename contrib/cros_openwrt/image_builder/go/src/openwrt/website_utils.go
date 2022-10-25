// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package openwrt

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strings"

	"chromiumos/platform/dev/contrib/cros_openwrt/image_builder/log"
	"github.com/PuerkitoBio/goquery"
)

const openWrtDownloadsUrlPrefix = "https://downloads.openwrt.org/"

func AutoResolveDownloadURLs(ctx context.Context, autoURL string) (sdkURL, imageBuilderURL string, err error) {
	// Validate and parse out URL to build target download page.
	log.Logger.Printf("Automatically resolving sdk and image builder archive download URLs from %q\n", autoURL)
	if !strings.HasPrefix(autoURL, openWrtDownloadsUrlPrefix) {
		return "", "", fmt.Errorf("automatic URL resolution only supported from %s pages", openWrtDownloadsUrlPrefix)
	}
	pageURL, err := url.Parse(autoURL)
	pathParts := strings.Split(strings.Trim(pageURL.Path, "/"), "/")
	targetsPathPartIndex := -1
	for i, part := range pathParts {
		if part == "targets" {
			targetsPathPartIndex = i
			break
		}
	}
	if targetsPathPartIndex == -1 {
		return "", "", fmt.Errorf("invalid autoUrl %q: expected a 'targets' path part", autoURL)
	}
	if len(pathParts) <= targetsPathPartIndex+2 {
		return "", "", fmt.Errorf("invalid autoUrl %q: failed to parse build target path", autoURL)
	}
	target := strings.Join(pathParts[(targetsPathPartIndex+1):(targetsPathPartIndex+3)], "/")
	log.Logger.Printf("Resolved target as %q\n", target)
	targetDownloadPageURL, err := url.Parse(openWrtDownloadsUrlPrefix + strings.Join(pathParts[:(targetsPathPartIndex+3)], "/"))
	if err != nil {
		return "", "", fmt.Errorf("failed to parse valid target download page URL from autoUrl %q: %w", autoURL, err)
	}
	targetDownloadPageURLStr := targetDownloadPageURL.String()
	log.Logger.Printf("Resolved target download page URL as %q\n", targetDownloadPageURLStr)

	// Download html of page.
	req, err := http.NewRequestWithContext(ctx, "GET", targetDownloadPageURLStr, nil)
	if err != nil {
		return "", "", fmt.Errorf("failed to HTTPS GET request of target download page resolved as %q: %w", targetDownloadPageURLStr, err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", "", fmt.Errorf("failed to download html of target download page resolved as %q: %w", targetDownloadPageURLStr, err)
	}
	defer (func() {
		_ = resp.Body.Close()
	})()

	// Search html for sdk and image builder download links.
	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return "", "", fmt.Errorf("failed to create new html document reader of target download page resolved as %q: %w", targetDownloadPageURLStr, err)
	}
	doc.Find("td.n a").EachWithBreak(func(i int, selection *goquery.Selection) bool {
		fileName, hasHref := selection.Attr("href")
		if !hasHref {
			return true
		}
		fileUrl := targetDownloadPageURLStr + "/" + fileName
		if strings.HasPrefix(fileName, "openwrt-sdk-") {
			sdkURL = fileUrl
			log.Logger.Printf("Resolved sdk download URL as %q\n", sdkURL)
		} else if strings.HasPrefix(fileName, "openwrt-imagebuilder-") {
			imageBuilderURL = fileUrl
			log.Logger.Printf("Resolved image builder download URL as %q\n", imageBuilderURL)

		}
		return sdkURL == "" || imageBuilderURL == ""
	})
	if sdkURL == "" {
		return "", "", fmt.Errorf("failed to find sdk download URL in target download page resolved as %q", targetDownloadPageURLStr)
	}
	if imageBuilderURL == "" {
		return "", "", fmt.Errorf("failed to find image builder download URL in target download page resolved as %q", targetDownloadPageURLStr)
	}

	return sdkURL, imageBuilderURL, err
}
