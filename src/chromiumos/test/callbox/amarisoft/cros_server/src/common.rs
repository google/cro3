// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use std::error::Error;
use std::fmt;

pub const HTTP_OK: u16 = 200;
pub const HTTP_ERROR_FORBIDDEN: u16 = 403;

#[derive(Debug)]
pub struct ServerError(pub String);

impl std::error::Error for ServerError {}

impl fmt::Display for ServerError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

#[derive(Clone, Deserialize, Serialize, PartialEq, Eq, Debug)]
pub struct ServerCommand {
    // The command to execute on the server.
    pub command: String,
    // The command parameters.
    pub params: serde_json::Value,
}

pub fn create_parse_error(fn_name: &str, root_error: Box<dyn Error>) -> Box<dyn Error> {
    return Box::new(ServerError(
        format!("Failed to parse {} command: {}", fn_name, root_error).to_owned(),
    ));
}

pub fn parse_value_to_json<T: DeserializeOwned>(
    content: serde_json::Value,
) -> std::result::Result<T, ServerError> {
    let temp_content = content.clone();
    match serde_json::from_value::<T>(content) {
        Ok(result) => return Ok(result),
        Err(error) => {
            println!(
                "Failed to parse JSON content of type: `{}`: {} content:{:?}",
                std::any::type_name::<T>(),
                error,
                temp_content
            );
            return Err(ServerError("Failed to parse json message".to_owned()));
        }
    };
}

pub fn parse_string_to_json<T: DeserializeOwned>(
    content: &String,
) -> std::result::Result<T, ServerError> {
    match serde_json::from_str::<T>(&content) {
        Ok(result) => return Ok(result),
        Err(error) => {
            println!(
                "Failed to parse JSON content of type: `{}`: {}",
                std::any::type_name::<T>(),
                error
            );
            return Err(ServerError("Failed to parse json message".to_owned()));
        }
    };
}
