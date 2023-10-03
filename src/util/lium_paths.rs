use std::fs::create_dir_all;
use std::io::ErrorKind;
use std::path::Path;
use std::path::PathBuf;

use anyhow::Context;
use anyhow::Result;
use dirs::home_dir;

pub fn lium_dir() -> Result<String> {
    gen_path_in_lium_dir(".keep").and_then(|mut path| {
        path.pop();
        Ok(path.to_str().context("Failed to get lium dir")?.to_string())
    })
}

pub fn gen_path_in_lium_dir(name: &str) -> Result<PathBuf> {
    const WORKING_DIR_NAME: &str = ".lium";

    let path = &home_dir().context("Failed to determine home dir")?;
    let path = Path::new(path);
    let path = path.join(WORKING_DIR_NAME);
    let path = path.join(name);

    let mut dir = path.clone();
    dir.pop();
    if let Err(e) = create_dir_all(&dir) {
        if e.kind() != ErrorKind::AlreadyExists {
            return Err(e).context("Failed to create a dir");
        }
    }

    Ok(path)
}
