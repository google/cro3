# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from analyzer.backend import tast_results_dir
from analyzer.frontend import cli_frontend
import click


CONTEXT_SETTINGS = {
    "show_default": True,
}


@click.group(context_settings=CONTEXT_SETTINGS)
def cli() -> None:
    pass


cli.add_command(
    tast_results_dir.ingest_tast_results_directory, name="ingest-tast"
)
cli.add_command(cli_frontend.print_results, name="print-results")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli()
