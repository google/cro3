// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

mod amarisoft_api;
mod common;
mod entitlement_check;

use std::error::Error;

use amarisoft_api::AmarisoftAPI;
use common::ServerError;
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use tiny_http;

use crate::entitlement_check::EntitlementCheckResult;

const SERVER_PORT: i32 = 9920;
const HTTP_ERROR_INTERNAL_SERVER: u16 = 500;

#[derive(Serialize, Deserialize)]
pub struct UE {
    imsi: Option<String>,
}

struct CrosWebServer {
    entl_check: entitlement_check::EntitlementCheck,
    amarisoft: AmarisoftAPI,
}

impl CrosWebServer {
    fn new() -> CrosWebServer {
        return CrosWebServer {
            entl_check: entitlement_check::EntitlementCheck::new(),
            amarisoft: AmarisoftAPI::new(),
        };
    }

    fn get_header_field(request: &mut tiny_http::Request, field: &'static str) -> String {
        for h in request.headers() {
            if h.field.equiv(field) {
                return h.value.to_string();
            }
        }
        String::new()
    }

    fn get_content_type(request: &mut tiny_http::Request) -> String {
        CrosWebServer::get_header_field(request, "Content-Type")
    }

    fn respond_http_response(request: tiny_http::Request, data: &str, code: u16) {
        println!("returning data:{:?}  code:{:?}", data, code);
        let response =
            tiny_http::Response::from_string(data).with_status_code(tiny_http::StatusCode(code));
        if let Err(e) = request.respond(response) {
            println!("Error sending response:{}", e);
        }
    }

    fn get_json_content<T: DeserializeOwned>(
        request: &mut tiny_http::Request,
    ) -> std::result::Result<T, ServerError> {
        let content_type = CrosWebServer::get_content_type(request);
        if content_type.starts_with("application/json") {
            let mut content = String::new();
            if let Err(error) = request.as_reader().read_to_string(&mut content) {
                println!("Failed to read JSON content");
                return Err(ServerError(error.to_string()));
            }
            return common::parse_string_to_json(&mut content);
        }
        return Err(ServerError(format!(
            "The Content type {} is not application/json",
            content_type
        )));
    }

    fn handle_entitlement_check(&mut self, mut request: tiny_http::Request, imeisv: String) {
        println!("entitlement_check");
        match CrosWebServer::get_json_content::<UE>(&mut request) {
            Ok(ue) => {
                let imsi = match ue.imsi {
                    Some(val) => val,
                    None => String::new(),
                };
                println!("imeisv:{:?} imsi:{:?}", imeisv, imsi);
                match self.entl_check.check_entitlement(&imeisv, &imsi) {
                    EntitlementCheckResult::Ok => CrosWebServer::respond_http_response(
                        request,
                        "",
                        entitlement_check::ENTITLEMENT_OK_CODE,
                    ),
                    EntitlementCheckResult::NotOk(code) => CrosWebServer::respond_http_response(
                        request,
                        code.to_string().as_str(),
                        entitlement_check::ENTITLEMENT_NOK_CODE,
                    ),

                    EntitlementCheckResult::DoNotRespond => (),
                }
            }
            Err(error) => {
                println!("Failed to parse json content of type `UE`: {}", error);
                CrosWebServer::respond_http_response(
                    request,
                    entitlement_check::ENTITLEMENT_ERROR_SYNTAX_ERROR
                        .to_string()
                        .as_str(),
                    entitlement_check::ENTITLEMENT_NOK_CODE,
                );
            }
        };
    }

    /// Handles all the server commands that will change the server behavior. The commands should be json values
    /// that include the API version, the command name, and the parameters applicable to that command.
    fn handle_server_command(
        &mut self,
        mut request: tiny_http::Request,
        imeisv: String,
        request_ip: String,
    ) {
        match CrosWebServer::get_json_content::<common::ServerCommand>(&mut request) {
            Ok(server_command) => {
                println!(
                    "Server Command received: {} ip:{}",
                    server_command.command.as_str(),
                    request_ip
                );
                let result: Result<(), Box<dyn Error>> = match server_command.command.as_str() {
                    "SetupEntitlementReturnCodeForDevice"
                    | "ResetEntitlementValueForDevice"
                    | "IgnoreNextEntitlementCheckForDevice" => {
                        self.entl_check.process_command(server_command, &imeisv)
                    }
                    _ => Err(Box::new(ServerError("Unknown command".to_owned()))),
                };
                return match result {
                    Ok(_) => CrosWebServer::respond_http_response(request, "", common::HTTP_OK),
                    Err(error) => CrosWebServer::respond_http_response(
                        request,
                        error.to_string().as_str(),
                        HTTP_ERROR_INTERNAL_SERVER,
                    ),
                };
            }
            Err(error) => {
                return CrosWebServer::respond_http_response(
                    request,
                    error.to_string().as_str(),
                    HTTP_ERROR_INTERNAL_SERVER,
                )
            }
        };
    }

    pub fn handle_url_request(
        &mut self,
        request: tiny_http::Request,
    ) -> std::result::Result<(), std::io::Error> {
        let mut request_ip = request.remote_addr().ip().to_string();
        // IPv4 addresses are sometimes converted to IPv6 addresses
        if request_ip.starts_with("::ffff:192.") {
            request_ip = request_ip.replace("::ffff:", "")
        }
        let imeisv = match self.amarisoft.get_imeisv(request_ip.as_str()) {
            Ok(val) => val,
            Err(error) => {
                println!("Failed to get imeisv:{:?}", error);
                String::new()
            }
        };

        match request.url() {
            "/entitlement_check_ok" => {
                println!("{}", request.url());
                if !self.entl_check.is_ignore_next_request(&imeisv) {
                    CrosWebServer::respond_http_response(
                        request,
                        "",
                        entitlement_check::ENTITLEMENT_OK_CODE,
                    )
                }
            }
            "/entitlement_check_nok" => {
                println!("{}", request.url());
                if !self.entl_check.is_ignore_next_request(&imeisv) {
                    CrosWebServer::respond_http_response(
                        request,
                        entitlement_check::ENTITLEMENT_ERROR_USER_NOT_ALLOWED_TO_TETHER
                            .to_string()
                            .as_str(),
                        entitlement_check::ENTITLEMENT_NOK_CODE,
                    )
                }
            }
            "/entitlement_check" => self.handle_entitlement_check(request, imeisv),
            // `server_command` implements the first version of this API. Any major changes on the API or implementation should be added by adding a new url(e.g. server_command_v2)
            // because the server should be backwards compatible.
            "/server_command" => self.handle_server_command(request, imeisv, request_ip),
            _ => CrosWebServer::respond_http_response(
                request,
                r###"<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>cros_webserver!</title></head><body><h1>Error 404</h1>
        <p>Unknown path. Check cros_server for available commands.</p></body></html>
        "###,
                404,
            ),
        };

        Ok(())
    }
}

fn main() -> std::result::Result<(), std::io::Error> {
    let server = tiny_http::Server::http(format!("[::]:{}", SERVER_PORT)).unwrap();
    let mut cros_webserver = CrosWebServer::new();
    loop {
        // blocks until the next request is received
        let request = match server.recv() {
            Ok(rq) => rq,
            Err(e) => {
                println!("error: {}", e);
                break;
            }
        };

        if let Err(e) = cros_webserver.handle_url_request(request) {
            println!("Error when handling the stream: {:?}", e);
        }
    }

    println!("Done");
    Ok(())
}
