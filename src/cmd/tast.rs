// Copyright 2023 The ChromiumOS Authors
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

use std::path::Path;

use anyhow::Result;
use argh::FromArgs;
use cro3::chroot::Chroot;
use cro3::config::Config;
use cro3::dut::SshInfo;
use cro3::repo::get_cros_dir;
use cro3::tast::collect_results;
use cro3::tast::print_cached_tests;
use cro3::tast::run_tast_test;
use cro3::tast::save_result_metadata_json;
use cro3::tast::update_cached_tests;
use cro3::tast::TastAnalyzerInputJson;
use cro3::tast::TastResultMetadata;
use cro3::tast::TastTestExecutionType;
use glob::Pattern;
use hashbrown::HashMap;
use tracing::info;
use tracing::warn;

#[derive(FromArgs, PartialEq, Debug)]
/// run Tast test
#[argh(subcommand, name = "tast")]
pub struct Args {
    #[argh(subcommand)]
    nested: SubCommand,
}

#[derive(FromArgs, PartialEq, Debug)]
#[argh(subcommand)]
enum SubCommand {
    Analyze(ArgsAnalyze),
    Build(ArgsBuild),
    List(ArgsList),
    Run(ArgsRun),
}
#[tracing::instrument(level = "trace")]
pub fn run(args: &Args) -> Result<()> {
    match &args.nested {
        SubCommand::Analyze(args) => args.run(),
        SubCommand::Build(args) => args.run(),
        SubCommand::List(args) => run_tast_list(args),
        SubCommand::Run(args) => args.run(),
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Analyze tast results
/// # List results
/// cro3 tast analyze --results-dir /data/tast/results
#[argh(subcommand, name = "analyze")]
pub struct ArgsAnalyze {
    /// cros source dir to be used for data retrieval(exclusive with
    /// --results-dir)
    #[argh(option)]
    cros: Option<String>,

    /// results dir to be used (exclusive with --cros)
    #[argh(option)]
    results_dir: Option<String>,

    // TODO: FIX THIS
    /// start datetime to be analyzed in YYYYMMDD-hhmmss format.
    #[argh(option)]
    start: Option<String>,

    // TODO: FIX THIS
    /// end datetime to be analyzed in YYYYMMDD-hhmmss format.
    #[argh(option)]
    end: Option<String>,

    /// model filter (case insensitive)
    #[argh(option)]
    model: Option<String>,
}
impl ArgsAnalyze {
    fn run(&self) -> Result<()> {
        let results = collect_results(
            self.cros.as_deref(),
            self.results_dir.as_deref(),
            self.start.as_deref(),
            self.end.as_deref(),
        )?;
        info!("{} tests have valid generic Tast metadata", results.len());
        let results: Vec<&TastResultMetadata> = results
            .iter()
            .filter(|e| e.invocation.abtest_metadata().is_some())
            .collect();
        info!("{} tests have valid cro3 abtest metadata", results.len());

        if let Some(result) = results.first() {
            info!("Sample (first): {result:#?}");
        }
        if let Some(result) = results.last() {
            info!("Sample (last): {result:#?}");
        }
        let mut bucket = HashMap::<String, Vec<&TastResultMetadata>>::new();
        for e in results.iter() {
            if let Some(abtest_metadata) = e.invocation.abtest_metadata() {
                let key = format!(
                    "{}/{}/{}",
                    abtest_metadata.runner.experiment_name,
                    abtest_metadata.config,
                    e.invocation.model().unwrap_or("UNKNOWN_MODEL")
                );
                if !bucket.contains_key(&key) {
                    bucket.insert(key.clone(), Vec::new());
                }
                bucket.get_mut(&key).unwrap().push(e);
            }
        }
        for (k, v) in bucket {
            info!("{k}: {}", v.len());
            let t = TastAnalyzerInputJson::from_results(&v)?;
            let name = k.replace('/', "_").to_string();
            save_result_metadata_json(&v, Some(&name))?;
            t.save(Path::new("out").join(name).with_extension("json").as_path())?;
        }
        info!("To compare the results statistically, run:");
        info!(
            "PYTHONPATH=$TAST_ANALYZER python3 -m analyzer.run print-results --compare \
             $RESULT_A_JSON $RESULT_B_JSON"
        );
        info!("Note: TAST_ANALYZER can be downloaded from: https://chromium.googlesource.com/chromiumos/platform/tast-tests/");
        info!(
            "and please specify the absolute path of tools/tast-analyzer/ in the repo above as \
             TAST_ANALYZER"
        );
        save_result_metadata_json(&results, None)?;
        Ok(())
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Generate a portable tast execution package
#[argh(subcommand, name = "build")]
pub struct ArgsBuild {
    /// cros source dir
    #[argh(option)]
    cros: Option<String>,
}
impl ArgsBuild {
    fn run(&self) -> Result<()> {
        let cros = get_cros_dir(self.cros.as_deref())?;
        let chroot = Chroot::new(&cros)?;
        chroot.run_bash_script_in_chroot(
            "generate_tast_archive",
            r#"
# First, emerge the required packages.
cros-workon --host start tast-remote-tests-cros tast-tests-remote-data
sudo emerge tast-remote-tests-cros tast-tests-remote-data

# If the checkout has private repos as well, build the crosint bundle as well.
if [ -d ~/chromiumos/src/platform/tast-tests-private ] ; then
  cros-workon --host start tast-remote-tests-crosint
  sudo emerge tast-remote-tests-crosint
fi

# Copy all the files to a dir which is visible from the outside of chroot.
TASTPACK_PATH_COMMON="tmp/tastpack_`date +%Y%m%d_%H%M%S_%N`"
: "${EXTERNAL_TRUNK_PATH:=/path/to/chromiumos}"
TASTPACK_PATH_INSIDE="/${TASTPACK_PATH_COMMON}"
TASTPACK_PATH_OUTSIDE="${EXTERNAL_TRUNK_PATH}/out/${TASTPACK_PATH_COMMON}"
echo "Copying the files into ${TASTPACK_PATH_INSIDE}"
mkdir -p ${TASTPACK_PATH_INSIDE}
cp -r \
  /usr/bin/remote_test_runner \
  /usr/bin/tast \
  /usr/libexec/tast/bundles \
  /usr/share/tast/data \
  ~/chromiumos/src/platform/tast/tools/run_tast.sh \
  ${TASTPACK_PATH_INSIDE}

echo "Done! You can find the tastpack artifact at in the chroot:"
echo "${TASTPACK_PATH_INSIDE}"
echo "...or, the same thing is visible from the host at:"
echo "${TASTPACK_PATH_OUTSIDE}"
echo ""
echo "Move into the dir and run something like this to run Tast tests:"
echo "./run_tast.sh \${DUT} meta.RemotePass"
"#,
            None,
        )?;
        Ok(())
    }
}

#[derive(FromArgs, PartialEq, Debug)]
/// Get tast test for the target DUT
#[argh(subcommand, name = "list")]
pub struct ArgsList {
    /// target cros repo directory
    #[argh(option)]
    cros: Option<String>,

    /// target DUT
    #[argh(option)]
    dut: Option<String>,

    /// glob pattern of the listint test
    #[argh(positional)]
    tests: Option<String>,

    /// only show cached list
    #[argh(switch)]
    cached: bool,

    #[argh(option, hidden_help)]
    repo: Option<String>,
}

fn run_tast_list(args: &ArgsList) -> Result<()> {
    let filter = args
        .tests
        .as_ref()
        .map(|s| Pattern::new(s))
        .unwrap_or_else(|| Pattern::new("*"))?;
    let config = Config::read()?;
    let mut bundles = config.tast_bundles();
    if bundles.is_empty() {
        bundles.push(cro3::tast::DEFAULT_BUNDLE);
    }

    if !args.cached {
        let dut = args
            .dut
            .as_ref()
            .expect("Test name is not cached. Please rerun with --dut <DUT>");

        update_cached_tests(&bundles, dut, &get_cros_dir(args.cros.as_deref())?)?;
    }

    print_cached_tests(&filter, &bundles)?;

    Ok(())
}

#[derive(FromArgs, PartialEq, Debug)]
/// Get tast test for the target DUT
#[argh(subcommand, name = "run")]
pub struct ArgsRun {
    /// target cros repo directory
    #[argh(option)]
    cros: Option<String>,

    /// tastpack directory
    #[argh(option)]
    tastpack: Option<String>,

    /// target DUT
    #[argh(option)]
    dut: String,

    /// test options (e.g. "-var ...")
    #[argh(option)]
    option: Option<String>,

    /// test name or pattern
    #[argh(positional)]
    tests: String,

    #[argh(option, hidden_help)]
    repo: Option<String>,
}
impl ArgsRun {
    fn run(&self) -> Result<()> {
        let tast = TastTestExecutionType::from_cros_or_tastpack(
            self.cros.as_deref(),
            self.tastpack.as_deref(),
        )?;
        run_tast_test(
            &SshInfo::new(&self.dut)?,
            &tast,
            &self.tests,
            self.option.as_deref(),
        )
    }
}
