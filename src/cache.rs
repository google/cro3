// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use crate::util::gen_path_in_lium_dir;
use anyhow::Context;
use anyhow::Result;
use serde::de::DeserializeOwned;
use serde::Serialize;
use serde_json::{Map, Value};
use std::collections::HashMap;
use std::fmt::Debug;
use std::fs::File;
use std::fs::OpenOptions;
use std::io::Read;
use std::io::Seek;
use std::io::Write;
use std::marker::PhantomData;
use std::sync::Mutex;

pub struct KvCache<T: Serialize + DeserializeOwned + Sized + Clone + Debug> {
    name: &'static str,
    map: Mutex<Option<HashMap<String, T>>>,
    file: Mutex<Option<File>>,
    //
    _value_type: PhantomData<T>,
}
impl<T: Serialize + DeserializeOwned + Sized + Clone + Debug> KvCache<T> {
    pub const fn new(name: &'static str) -> Self {
        Self {
            name,
            map: Mutex::new(None),
            file: Mutex::new(None),
            _value_type: PhantomData::<T>,
        }
    }
    pub fn clear(&self) -> Result<()> {
        self.load_cache_file()?;
        {
            let mut map = self.map.lock().unwrap();
            let map = map.as_mut().unwrap();
            map.clear();
        }
        self.sync()
    }
    fn create_file(&self, remove: bool) -> Result<()> {
        let path =
            gen_path_in_lium_dir(self.name).context("Failed to generate a cache file path")?;
        if remove {
            std::fs::remove_file(&path).context("Failed to remove the file")?;
        }
        let mut f = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .open(path)?;
        if f.metadata()?.len() == 0 {
            f.write_all(serde_json::to_string(&Map::<String, Value>::new())?.as_bytes())?;
            f.sync_all()?;
        }
        let mut file = self.file.lock().expect("lock failed");
        *file = Some(f);
        Ok(())
    }
    fn load_cache_file(&self) -> Result<()> {
        let file = self.file.lock().expect("lock failed");
        let has_file = file.is_some();
        drop(file);
        if !has_file {
            self.create_file(false)?;
        }
        let mut file_lock = self.file.lock().expect("lock failed");
        let file = file_lock.as_mut().expect("File is not initialized yet");
        file.rewind()?;
        let mut json = String::new();
        file.read_to_string(&mut json)?;
        drop(file_lock);
        match serde_json::from_str(&json) {
            Ok(data) => {
                *self.map.lock().unwrap() = data;
                Ok(())
            }
            Err(e) => {
                eprintln!("Failed to parse the cache: {e:?}");
                eprintln!("Creating a cache file again...");
                self.create_file(true)?;
                *self.map.lock().unwrap() = Some(HashMap::new());
                Ok(())
            }
        }
    }
    pub fn get(&self, key: &str) -> Result<Option<T>> {
        self.load_cache_file()?;
        let mut map = self.map.lock().unwrap();
        let map = map.as_mut().unwrap();
        Ok(map.get(key).cloned())
    }
    pub fn set(&self, key: &str, value: T) -> Result<()> {
        self.load_cache_file()?;
        {
            let mut map = self.map.lock().unwrap();
            let map = map.as_mut().unwrap();
            map.insert(key.to_string(), value.clone());
        }
        self.sync()?;
        eprintln!("Cache updated. key: {}, value: {:?}", key, value);
        Ok(())
    }
    pub fn sync(&self) -> Result<()> {
        let mut map = self.map.lock().unwrap();
        let map = map.as_mut().unwrap();
        let mut file = self.file.lock().expect("lock failed");
        let file = file.as_mut().expect("File is not initialized yet");
        file.set_len(0)?;
        file.rewind()?;
        file.write_all(serde_json::to_string(map)?.as_bytes())?;
        file.sync_all().context("failed to sync backed file")
    }
    pub fn entries(&self) -> Result<HashMap<String, T>> {
        self.load_cache_file()?;
        let map = self.map.lock().unwrap();
        Ok((*map).clone().unwrap())
    }
    pub fn get_or_else(&self, key: &str, f: &dyn Fn(&str) -> Result<T>) -> Result<T> {
        if let Some(s) = self.get(key)? {
            Ok(s)
        } else {
            let value = f(key);
            if let Ok(value) = &value {
                self.set(key, value.clone())?;
            }
            value
        }
    }
}
