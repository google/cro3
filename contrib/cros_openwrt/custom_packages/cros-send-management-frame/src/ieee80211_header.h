/*
 * Copyright 2022 The ChromiumOS Authors
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

/*
 * These header definitions are taken from wpa_supplicant, which offers
 * the use of them under the terms of a BSD license.
 */

#ifndef CONTRIB_CROS_OPENWRT_CUSTOM_PACKAGES_CROS_SEND_MANAGEMENT_FRAME_SRC_IEEE80211_HEADER_H_
#define CONTRIB_CROS_OPENWRT_CUSTOM_PACKAGES_CROS_SEND_MANAGEMENT_FRAME_SRC_IEEE80211_HEADER_H_

#include <linux/types.h>

#define WLAN_FC_TYPE_MGMT 0
#define WLAN_FC_TYPE_CTRL 1
#define WLAN_FC_TYPE_DATA 2

/* management */
#define WLAN_FC_STYPE_ASSOC_REQ 0
#define WLAN_FC_STYPE_ASSOC_RESP 1
#define WLAN_FC_STYPE_REASSOC_REQ 2
#define WLAN_FC_STYPE_REASSOC_RESP 3
#define WLAN_FC_STYPE_PROBE_REQ 4
#define WLAN_FC_STYPE_PROBE_RESP 5
#define WLAN_FC_STYPE_BEACON 8
#define WLAN_FC_STYPE_ATIM 9
#define WLAN_FC_STYPE_DISASSOC 10
#define WLAN_FC_STYPE_AUTH 11
#define WLAN_FC_STYPE_DEAUTH 12
#define WLAN_FC_STYPE_ACTION 13

/* control */
#define WLAN_FC_STYPE_PSPOLL 10
#define WLAN_FC_STYPE_RTS 11
#define WLAN_FC_STYPE_CTS 12
#define WLAN_FC_STYPE_ACK 13
#define WLAN_FC_STYPE_CFEND 14
#define WLAN_FC_STYPE_CFENDACK 15

/* data */
#define WLAN_FC_STYPE_DATA 0
#define WLAN_FC_STYPE_DATA_CFACK 1
#define WLAN_FC_STYPE_DATA_CFPOLL 2
#define WLAN_FC_STYPE_DATA_CFACKPOLL 3
#define WLAN_FC_STYPE_NULLFUNC 4
#define WLAN_FC_STYPE_CFACK 5
#define WLAN_FC_STYPE_CFPOLL 6
#define WLAN_FC_STYPE_CFACKPOLL 7
#define WLAN_FC_STYPE_QOS_DATA 8
#define WLAN_FC_STYPE_QOS_DATA_CFACK 9
#define WLAN_FC_STYPE_QOS_DATA_CFPOLL 10
#define WLAN_FC_STYPE_QOS_DATA_CFACKPOLL 11
#define WLAN_FC_STYPE_QOS_NULL 12
#define WLAN_FC_STYPE_QOS_CFPOLL 14
#define WLAN_FC_STYPE_QOS_CFACKPOLL 15

#define WLAN_FC_GET_STYPE(fc) (((fc)&0x00f0) >> 4)

/* Action frame categories (IEEE 802.11-2007, 7.3.1.11, Table 7-24) */
#define WLAN_ACTION_SPECTRUM_MGMT 0
#define WLAN_ACTION_QOS 1
#define WLAN_ACTION_DLS 2
#define WLAN_ACTION_BLOCK_ACK 3
#define WLAN_ACTION_PUBLIC 4
#define WLAN_ACTION_RADIO_MEASUREMENT 5
#define WLAN_ACTION_FT 6
#define WLAN_ACTION_HT 7
#define WLAN_ACTION_SA_QUERY 8
#define WLAN_ACTION_WNM 10
#define WLAN_ACTION_UNPROTECTED_WNM 11
#define WLAN_ACTION_TDLS 12
#define WLAN_ACTION_WMM 17 /* WMM Specification 1.1 */
#define WLAN_ACTION_VENDOR_SPECIFIC 127

/* SPECTRUM_MGMT action codes */
#define WLAN_ACTION_SPCT_MSR_REQ 0
#define WLAN_ACTION_SPCT_MSR_RPRT 1
#define WLAN_ACTION_SPCT_TPC_REQ 2
#define WLAN_ACTION_SPCT_TPC_RPRT 3
#define WLAN_ACTION_SPCT_CHL_SWITCH 4

/* Information Element IDs */
#define WLAN_EID_SSID 0
#define WLAN_EID_SUPP_RATES 1
#define WLAN_EID_FH_PARAMS 2
#define WLAN_EID_DS_PARAMS 3
#define WLAN_EID_CF_PARAMS 4
#define WLAN_EID_TIM 5
#define WLAN_EID_IBSS_PARAMS 6
#define WLAN_EID_COUNTRY 7
#define WLAN_EID_CHALLENGE 16
/* EIDs defined by IEEE 802.11h - START */
#define WLAN_EID_PWR_CONSTRAINT 32
#define WLAN_EID_PWR_CAPABILITY 33
#define WLAN_EID_TPC_REQUEST 34
#define WLAN_EID_TPC_REPORT 35
#define WLAN_EID_SUPPORTED_CHANNELS 36
#define WLAN_EID_CHANNEL_SWITCH 37
#define WLAN_EID_MEASURE_REQUEST 38
#define WLAN_EID_MEASURE_REPORT 39
#define WLAN_EID_QUITE 40
#define WLAN_EID_IBSS_DFS 41
/* EIDs defined by IEEE 802.11h - END */
#define WLAN_EID_ERP_INFO 42
#define WLAN_EID_HT_CAP 45
#define WLAN_EID_RSN 48
#define WLAN_EID_EXT_SUPP_RATES 50
#define WLAN_EID_MOBILITY_DOMAIN 54
#define WLAN_EID_FAST_BSS_TRANSITION 55
#define WLAN_EID_TIMEOUT_INTERVAL 56
#define WLAN_EID_RIC_DATA 57
#define WLAN_EID_HT_OPERATION 61
#define WLAN_EID_SECONDARY_CHANNEL_OFFSET 62
#define WLAN_EID_TIME_ADVERTISEMENT 69
#define WLAN_EID_20_40_BSS_COEXISTENCE 72
#define WLAN_EID_20_40_BSS_INTOLERANT 73
#define WLAN_EID_OVERLAPPING_BSS_SCAN_PARAMS 74
#define WLAN_EID_MMIE 76
#define WLAN_EID_TIME_ZONE 98
#define WLAN_EID_LINK_ID 101
#define WLAN_EID_INTERWORKING 107
#define WLAN_EID_ADV_PROTO 108
#define WLAN_EID_ROAMING_CONSORTIUM 111
#define WLAN_EID_EXT_CAPAB 127
#define WLAN_EID_VENDOR_SPECIFIC 221

#define WLAN_EID_LENGTH_CHANNEL_SWITCH 3

/* Channel Swtich Modes (IEEE 802.11h-2003, 7.3.2.20) */
#define WLAN_CHANNEL_SWITCH_MODE_XMIT_ALLOWED 0
#define WLAN_CHANNEL_SWITCH_MODE_XMIT_FORBIDDEN 1

struct ieee80211_hdr {
  __le16 frame_control;
  __le16 duration_id;
  __u8 addr1[6];
  __u8 addr2[6];
  __u8 addr3[6];
  __le16 seq_ctrl;
  /* followed by 'u8 addr4[6];' if ToDS and FromDS is set in data frame
   */
} __attribute__((packed));

#define IEEE80211_FC(type, stype) ((type << 2) | (stype << 4))
#define WLAN_SA_QUERY_TR_ID_LEN 2

struct ieee80211_mgmt {
  __le16 frame_control;
  __le16 duration;
  __u8 da[6];
  __u8 sa[6];
  __u8 bssid[6];
  __le16 seq_ctrl;
  union {
    struct {
      __le16 auth_alg;
      __le16 auth_transaction;
      __le16 status_code;
      /* possibly followed by Challenge text */
      __u8 variable[0];
    } __attribute__((packed)) auth;
    struct {
      __le16 reason_code;
      __u8 variable[0];
    } __attribute__((packed)) deauth;
    struct {
      __le16 capab_info;
      __le16 listen_interval;
      /* followed by SSID and Supported rates */
      __u8 variable[0];
    } __attribute__((packed)) assoc_req;
    struct {
      __le16 capab_info;
      __le16 status_code;
      __le16 aid;
      /* followed by Supported rates */
      __u8 variable[0];
    } __attribute__((packed)) assoc_resp, reassoc_resp;
    struct {
      __le16 capab_info;
      __le16 listen_interval;
      __u8 current_ap[6];
      /* followed by SSID and Supported rates */
      __u8 variable[0];
    } __attribute__((packed)) reassoc_req;
    struct {
      __le16 reason_code;
      __u8 variable[0];
    } __attribute__((packed)) disassoc;
    struct {
      __u8 timestamp[8];
      __le16 beacon_int;
      __le16 capab_info;
      /* followed by some of SSID, Supported rates,
       * FH Params, DS Params, CF Params, IBSS Params, TIM */
      __u8 variable[0];
    } __attribute__((packed)) beacon;
    struct {
      /* only variable items: SSID, Supported rates */
      __u8 variable[0];
    } __attribute__((packed)) probe_req;
    struct {
      __u8 timestamp[8];
      __le16 beacon_int;
      __le16 capab_info;
      /* followed by some of SSID, Supported rates,
       * FH Params, DS Params, CF Params, IBSS Params */
      __u8 variable[0];
    } __attribute__((packed)) probe_resp;
    struct {
      __u8 category;
      union {
        struct {
          __u8 action_code;
          __u8 dialog_token;
          __u8 status_code;
          __u8 variable[0];
        } __attribute__((packed)) wmm_action;
        struct {
          __u8 action_code;
          __u8 element_id;
          __u8 length;
          __u8 switch_mode;
          __u8 new_chan;
          __u8 switch_count;
        } __attribute__((packed)) chan_switch;
        struct {
          __u8 action;
          __u8 sta_addr[ETH_ALEN];
          __u8 target_ap_addr[ETH_ALEN];
          __u8 variable[0]; /* FT Request */
        } __attribute__((packed)) ft_action_req;
        struct {
          __u8 action;
          __u8 sta_addr[ETH_ALEN];
          __u8 target_ap_addr[ETH_ALEN];
          __le16 status_code;
          __u8 variable[0]; /* FT Request */
        } __attribute__((packed)) ft_action_resp;
        struct {
          __u8 action;
          __u8 trans_id[WLAN_SA_QUERY_TR_ID_LEN];
        } __attribute__((packed)) sa_query_req;
        struct {
          __u8 action; /* */
          __u8 trans_id[WLAN_SA_QUERY_TR_ID_LEN];
        } __attribute__((packed)) sa_query_resp;
        struct {
          __u8 action;
          __u8 variable[0];
        } __attribute__((packed)) public_action;
        struct {
          __u8 action; /* 9 */
          __u8 oui[3];
          /* Vendor-specific content */
          __u8 variable[0];
        } __attribute__((packed)) vs_public_action;
        struct {
          __u8 action; /* 7 */
          __u8 dialog_token;
          __u8 req_mode;
          __le16 disassoc_timer;
          __u8 validity_interval;
          /* BSS Termination Duration (optional),
           * Session Information URL (optional),
           * BSS Transition Candidate List
           * Entries */
          __u8 variable[0];
        } __attribute__((packed)) bss_tm_req;
      } u;
    } __attribute__((packed)) action;
  } u;
} __attribute__((packed));

#endif  // CONTRIB_CROS_OPENWRT_CUSTOM_PACKAGES_CROS_SEND_MANAGEMENT_FRAME_SRC_IEEE80211_HEADER_H_
