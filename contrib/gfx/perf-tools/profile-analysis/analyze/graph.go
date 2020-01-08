// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyze

import (
	"fmt"
	"golang.org/x/image/colornames"
	"gonum.org/v1/plot"
	"gonum.org/v1/plot/plotter"
	"gonum.org/v1/plot/vg"
	"gonum.org/v1/plot/vg/draw"
	"os/exec"
)

const plotFileName = "./analyzer_calls.png"

// PlotCallNameUsagePerFrame generates a scatter-plot of the number of calls
// to GL functions that match the given regex per frame and launches Chrome
// to show the resulting graph.
func PlotCallNameUsagePerFrame(prof *ProfileData, callNameRegex string) error {
	var calls []int
	var err error
	if calls, err = GatherNumCallsPerFrame(prof, callNameRegex); err != nil {
		return err
	}

	pts := make(plotter.XYs, len(calls))
	for i, callCount := range calls {
		if callCount > 0 {
			pts[i].X = float64(i)
			pts[i].Y = float64(callCount)
		}
	}

	var p *plot.Plot
	if p, err = plot.New(); err != nil {
		return err
	}

	p.Title.Text = fmt.Sprintf("Calls to %s per frame", callNameRegex)
	p.X.Label.Text = "frame num"
	p.Y.Label.Text = "call count"
	p.Add(plotter.NewGrid())

	var s *plotter.Scatter
	if s, err = plotter.NewScatter(pts); err != nil {
		return err
	}
	s.GlyphStyle.Color = colornames.Blue
	s.Shape = draw.PlusGlyph{}

	p.Add(s)

	// Save the plot to a PNG file.
	if err = p.Save(9*vg.Inch, 4*vg.Inch, plotFileName); err != nil {
		return err
	}

	// Show plot. If 'display' is available (imagemagick), we'll use that.
	// Otherwise we fallback to Chrome.
	var cmd *exec.Cmd
	_, err = exec.LookPath("display")
	if err != nil {
		cmd = exec.Command("/usr/bin/google-chrome", plotFileName)
	} else {
		cmd = exec.Command("display", plotFileName)
	}
	return cmd.Start()
}
