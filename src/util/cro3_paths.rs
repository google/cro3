use std::fs::create_dir_all;
use std::io::ErrorKind;
use std::path::Path;
use std::path::PathBuf;

use anyhow::Context;
use anyhow::Result;
use dirs::home_dir;

pub fn cro3_dir() -> Result<String> {
    gen_path_in_cro3_dir(".keep").and_then(|mut path| {
        path.pop();
        Ok(path.to_str().context("Failed to get cro3 dir")?.to_string())
    })
}

pub fn gen_path_in_cro3_dir(name: &str) -> Result<PathBuf> {
    const WORKING_DIR_NAME: &str = ".cro3";

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
