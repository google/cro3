use std::process::Command;

use anyhow::Context;
use anyhow::Result;

pub fn list_gs_files(pattern: &str) -> Result<String> {
    let cmd = format!("gsutil.py ls {}", pattern.trim());
    println!("{:?}", cmd);
    let output = Command::new("bash").arg("-c").arg(cmd).output().context(
        "Failed to execute gsutil ls (maybe you need depot_tools and/or `gsutil.py config` with \
         'chromeos-swarming' project)",
    )?;
    Ok(String::from_utf8_lossy(&output.stdout)
        .to_string()
        .trim()
        .to_string())
}
