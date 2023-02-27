// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use crate::common::ServerError;

use serde::de::DeserializeOwned;
use serde_json::Value;
use std::error::Error;
use std::{collections::HashMap, str, time};
use tungstenite::{
    client::IntoClientRequest,
    connect,
    protocol::{frame::coding::CloseCode, CloseFrame},
    Message,
};

struct ImeisvCache {
    imeisv: String,
    last_retrieved: std::time::Instant,
}

pub(crate) struct AmarisoftAPI {
    imeisv_cache: HashMap<String, ImeisvCache>,
}

impl AmarisoftAPI {
    pub fn new() -> AmarisoftAPI {
        return AmarisoftAPI {
            imeisv_cache: HashMap::new(),
        };
    }

    fn extract_member<T: DeserializeOwned>(
        value: &Value,
        name: &str,
        data: &String,
    ) -> Result<T, Box<dyn Error>> {
        match serde_json::from_value::<T>((&value[&name]).clone()) {
            Ok(res) => Ok(res),
            Err(_) => Err(Self::new_json_parse_error(&name, data.as_str())),
        }
    }

    pub fn get_imeisv(&mut self, ip: &str) -> std::result::Result<String, Box<dyn Error>> {
        // cache the value for 5 minutes
        if let Some(val) = self.imeisv_cache.get_mut(ip) {
            if time::Instant::now().duration_since(val.last_retrieved)
                < time::Duration::from_secs(60 * 5)
            {
                println!(
                    "Returning cached imeisv value. ip:{} imeisv:{}",
                    ip, val.imeisv
                );
                return Ok(val.imeisv.clone());
            }
        }
        let data = Self::call_mme_remote_api(r#"{"message": "ue_get"}"#)?;
        let ue_get = serde_json::from_str::<Value>(data.as_str())
            .map_err(|_| Self::new_json_parse_error("ue_get", data.as_str()))?;
        for ue in Self::extract_member::<Vec<Value>>(&ue_get, "ue_list", &data)? {
            // The bearers object might not exist
            if ue.get("bearers").is_none() {
                continue;
            }
            for bearer in Self::extract_member::<Vec<Value>>(&ue, "bearers", &data)? {
                let ipv4 = bearer["ip"].as_str().unwrap_or_default();
                let ipv6 = bearer["ipv6"].as_str().unwrap_or_default();
                if ip == ipv6 || ip == ipv4 {
                    let imeisv = Self::extract_member::<String>(&ue, "imeisv", &data)?;
                    println!("Found matching ip: {:?}  imeisv:{:?}", ip, imeisv);
                    self.imeisv_cache.insert(
                        ip.to_string(),
                        ImeisvCache {
                            imeisv: imeisv.to_string(),
                            last_retrieved: time::Instant::now(),
                        },
                    );
                    return Ok(imeisv.to_string());
                }
            }
        }
        return Err(Box::new(ServerError(
            "ip address was not found in ue_get".to_owned(),
        )));
    }

    // Execute a generic command on the Amarisoft Remote API using ws.js
    fn call_mme_remote_api(command: &str) -> std::result::Result<String, Box<dyn Error>> {
        let mut req = "ws://127.0.0.1:9000/".into_client_request()?;
        let headers = req.headers_mut();
        headers.insert("Origin", "croscellularserver.com".parse()?);

        let (mut socket, _response) = connect(req).expect("Can't connect");
        socket.write_message(Message::Text(command.into())).unwrap();
        // If the server becomes slow due to high demand from DUTs, this should be improved by making the requests async.
        match socket.get_mut() {
            tungstenite::stream::MaybeTlsStream::Plain(t) => {
                t.set_read_timeout(Some(std::time::Duration::from_millis(100)))
                    .expect("Error: cannot set read-timeout to underlying stream");
            }
            _ => return Err(Box::new(ServerError("Error: it is not TlsStream".into()))),
        }
        // This could be improved by keeping the socket opened.
        let mut msg: String;
        let mut counter = 0;
        let start = std::time::Instant::now();
        loop {
            match socket.read_message() {
                Ok(val) => {
                    counter += 1;
                    msg = val.to_string(); // replace the string. the server returns 2 values, and the last one is the one we need.
                    if counter == 2 {
                        let close_frame = CloseFrame {
                            code: CloseCode::Normal,
                            reason: Default::default(),
                        };

                        _ = socket
                            .close(Some(close_frame))
                            .map_err(|err| println!("Failed to close the connection:{}", err));
                        println!("Remote API call succeeded in : {:?}", start.elapsed());
                        return Ok(msg);
                    }
                }
                Err(_) => {
                    println!("Remote API call failed in : {:?}", start.elapsed());
                    return Ok(String::new());
                }
            }
        }
    }

    fn new_json_parse_error(object_name: &str, message: &str) -> Box<dyn Error> {
        return Box::new(ServerError(format!(
            "Failed to parse {}. message:{}",
            object_name, message
        )));
    }
}
