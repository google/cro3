// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use crate::common;
use crate::common::ServerError;

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::error::Error;

pub const ENTITLEMENT_OK_CODE: u16 = common::HTTP_OK;
pub const ENTITLEMENT_NOK_CODE: u16 = common::HTTP_ERROR_FORBIDDEN;
pub const ENTITLEMENT_ERROR_USER_NOT_ALLOWED_TO_TETHER: i32 = 1000;
pub const ENTITLEMENT_ERROR_SYNTAX_ERROR: i32 = 1001;
const ENTITLEMENT_ERROR_USER_NOT_RECOGNIZED: i32 = 1003;

pub enum EntitlementCheckResult {
    Ok,
    NotOk(i32),
    DoNotRespond,
}

#[derive(Serialize, Deserialize)]
struct SetupEntitlementReturnCodeForDevice {
    imsi: String,
    code: i32,
}

#[derive(Serialize, Deserialize)]
struct ResetEntitlementValueForDevice {
    imsi: String,
}

pub(crate) struct EntitlementCheck {
    // A `map{imsi: string, result:boolean}` containing the result to be returned for
    // an imsi for each entitlement check.
    etl_result: HashMap<String, i32>,
    ignore_next_etl: HashMap<String, u16>,
}

impl EntitlementCheck {
    pub fn new() -> EntitlementCheck {
        return EntitlementCheck {
            etl_result: HashMap::new(),
            ignore_next_etl: HashMap::new(),
        };
    }

    pub fn is_ignore_next_request(&mut self, imeisv: &str) -> bool {
        if let Some(val) = self.ignore_next_etl.get_mut(imeisv) {
            *val = *val - 1;
            if *val <= 0 {
                println!("Ignoring entitlement check");
                self.ignore_next_etl.remove(imeisv);
                return true;
            }
        }
        return false;
    }
    pub fn check_entitlement(&mut self, imeisv: &str, imsi: &str) -> EntitlementCheckResult {
        if self.is_ignore_next_request(imeisv) {
            return EntitlementCheckResult::DoNotRespond;
        }
        let imeisv_imsi_key = Self::make_key(imeisv, imsi);
        println!(
            "check_entitlement. imeisv={} imsi={} key:{}",
            imeisv, imsi, imeisv_imsi_key
        );
        let result: i32;
        if self.etl_result.contains_key(&imeisv_imsi_key) {
            result = self.etl_result[&imeisv_imsi_key];
        } else if self.etl_result.contains_key(imsi) {
            // try falling back to the imsi only, in case the callbox API is failing.
            result = self.etl_result[imsi];
        } else {
            return EntitlementCheckResult::NotOk(ENTITLEMENT_ERROR_USER_NOT_RECOGNIZED);
        }
        if result == 0 {
            return EntitlementCheckResult::Ok;
        } else {
            return EntitlementCheckResult::NotOk(result);
        }
    }

    fn make_key(imeisv: &str, imsi: &str) -> String {
        return imeisv.to_owned() + "-" + imsi;
    }

    fn setup_entitlement_value(
        &mut self,
        setup: SetupEntitlementReturnCodeForDevice,
        imeisv: &str,
    ) -> std::result::Result<(), Box<dyn Error>> {
        println!(
            "setup_entitlement_value. imeisv={} imsi={} value:{} key:{}",
            imeisv,
            setup.imsi,
            setup.code,
            Self::make_key(imeisv, setup.imsi.as_str())
        );
        self.etl_result
            .insert(Self::make_key(imeisv, setup.imsi.as_str()), setup.code);
        return Ok(());
    }

    fn reset_entitlement_value(
        &mut self,
        setup: ResetEntitlementValueForDevice,
        imeisv: &str,
    ) -> std::result::Result<(), Box<dyn Error>> {
        // remove any key that starts with |imeisv|
        self.etl_result.retain(|key, _| !key.starts_with(imeisv));
        self.etl_result.remove(&setup.imsi);
        self.ignore_next_etl.remove(imeisv);
        return Ok(());
    }

    pub fn process_command(
        &mut self,
        setup: common::ServerCommand,
        imeisv: &str,
    ) -> Result<(), Box<dyn Error>> {
        match setup.command.as_str() {
            // This command is used to setup the entitlement check return value for a specific IMSI+imeisv combination.
            // This is useful when multiple SIM cards have the same IMSI(Amarisoft 5G SIM cards).
            "SetupEntitlementReturnCodeForDevice" => {
                match common::parse_value_to_json::<SetupEntitlementReturnCodeForDevice>(
                    setup.params,
                ) {
                    Ok(val) => match self.setup_entitlement_value(val, imeisv) {
                        Ok(val) => Ok(val),
                        Err(err) => Err(err),
                    },
                    Err(error) => Err(common::create_parse_error(
                        setup.command.as_str(),
                        Box::new(error),
                    )),
                }
            }
            "ResetEntitlementValueForDevice" => {
                match common::parse_value_to_json::<ResetEntitlementValueForDevice>(setup.params) {
                    Ok(conf) => match self.reset_entitlement_value(conf, imeisv) {
                        Ok(val) => Ok(val),
                        Err(err) => Err(err),
                    },
                    Err(error) => Err(common::create_parse_error(
                        setup.command.as_str(),
                        Box::new(error),
                    )),
                }
            }
            "IgnoreNextEntitlementCheckForDevice" => {
                // For now, we only ignore 1 request, but we could add an argument in the command to configure the number
                self.ignore_next_etl.insert(imeisv.to_owned(), 1);
                Ok(())
            }
            _ => return Err(Box::new(ServerError("Unknown command".to_owned()))),
        }
    }
}
