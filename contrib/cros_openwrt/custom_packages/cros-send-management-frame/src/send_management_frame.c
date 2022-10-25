/*
 * Copyright 2022 The ChromiumOS Authors
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

/*
 * Send Management Frame
 *
 * Userspace helper which sends management frames via nl80211.  This
 * can be used to inject frames used for regulatory testing, for example
 * spectrum management frames.
 */

#include <arpa/inet.h>
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <linux/if_ether.h>
#include <net/if.h>
#include <pcap.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>

#include "ieee80211_header.h"

/*
 * Minimal ieee80211 radiotap header.  The bitmap must remain zero
 * for this header to be valid.
 */
struct radiotap_header {
  __u16 version;
  __u16 header_length;
  __u32 bitmap;
} __attribute__((packed));

struct radiotap_packet {
  struct radiotap_header radiotap_header;
  struct ieee80211_mgmt ieee80211_mgmt_frame;
  /* Depending on frame type, some IEs may fit above; the rest go below. */
  unsigned char overflow[1024];
} __attribute__((packed));

struct radiotap_packet_buf {
  struct radiotap_packet packet;
  size_t len;  /* Length of populated data */
};

#define PACKET_TIMEOUT_MS 1000
#define SSID_LENGTH 32

static const char * type_beacon = "beacon";
static const char * type_channel_switch = "channel_switch";
static const char * type_probe_response = "probe_response";
static const char * usage =
    "Usage:\n"
    "  send_management_frame -i interface -t channel_switch\n"
    "                             [-a dest-addr] [-b num-bss] [-c channel]\n"
    "                             [-d delay] [-n pkt-count] [-f footer-file]\n"
    "\n"
    "  send_management_frame -i interface -t <beacon|probe_response>\n"
    "                             [-a dest-addr] [-b num-bss] [-c channel]\n"
    "                             [-d delay] [-n pkt-count] [-s ssid-prefix]\n"
    "                             [-f footer-file]\n"
    "\n"
    "Common options:\n"
    "       interface:    interface to inject frames.\n"
    "       dest-addr:    destination address (DA) for the frame.\n"
    "                     default to broadcast.\n"
    "       num-bss:      number of synthetic bss for sending frames.\n"
    "                     default to 0 (use interface MAC).\n"
    "       channel:      channel to inject frames, default to 1.\n"
    "       delay:        milliseconds delay in between frames,\n"
    "                     default to 0 (no delay).\n"
    "       pkt-count:    total number of frames to send, 0 means infinite\n"
    "                     default to 1.\n"
    "       footer-file:  non-empty file containing data to append to frames.\n"
    "\n"
    "beacon, probe_response options:\n"
    "       ssid-prefix:  prefix for the SSIDs, default to FakeSSID\n";

enum message_type {
  /* No external meaning, so sort alphabetically */
  BEACON,
  CHANNEL_SWITCH,
  PROBE_RESPONSE,
};

uint8_t message_type_to_80211_frame_subtype[] = {
  /* Ordered to match |enum message_type| */
  WLAN_FC_STYPE_BEACON,
  WLAN_FC_STYPE_ACTION,
  WLAN_FC_STYPE_PROBE_RESP,
};

int get_interface_info(char *interface,
                       int *interface_index,
                       unsigned char *mac_address) {
  struct ifreq ifr;
  int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
  if (sock < 0) {
    return -1;
  }

  memset(&ifr, 0, sizeof(ifr));
  strncpy(ifr.ifr_name, interface, sizeof(ifr.ifr_name));
  if (ioctl(sock, SIOCGIFINDEX, &ifr) != 0) {
    fprintf(stderr, "Can't get interface index for %s.\n", interface);
    return -1;
  }
  *interface_index = ifr.ifr_ifindex;

  if (ioctl(sock, SIOCGIFHWADDR, &ifr) != 0) {
    fprintf(stderr, "Can't get hardware address for %s.\n", interface);
    return -1;
  }
  memcpy(mac_address, &ifr.ifr_hwaddr.sa_data, ETH_ALEN);
  printf("Found interface %s at index %d, "
         "address %02x:%02x:%02x:%02x:%02x:%02x.\n",
         interface, *interface_index,
         mac_address[0], mac_address[1], mac_address[2],
         mac_address[3], mac_address[4], mac_address[5]);
  return 0;
}

/*
 * SSID prefix should be under 24 characters.
 */
int create_ssid(char *ssid_prefix, int bss_number, char **ssid_out) {
  *ssid_out = calloc(1, SSID_LENGTH + 1);
  if (!ssid_prefix)
    sprintf(*ssid_out, "FakeSSID%08x", bss_number);
  else {
    if (strlen(ssid_prefix) > 24) {
      fprintf(stderr, "SSID prefix too long, must be less than 24 "
              "characters.\n");
      return -EINVAL;
    }
    sprintf(*ssid_out, "%s%08X", ssid_prefix, bss_number);
  }
  return 0;
}

struct radiotap_packet_buf* packet_buf_alloc(uint16_t ieee80211_frame_subtype,
                                             const unsigned char* bssid,
                                             const unsigned char* source,
                                             const unsigned char* destination) {
  struct radiotap_packet_buf *packet_buf;
  struct ieee80211_mgmt *mgm_packet_ptr;
  packet_buf = calloc(1, sizeof(struct radiotap_packet_buf));
  packet_buf->len = 0;

  struct radiotap_packet* packet = &packet_buf->packet;
  packet->radiotap_header.version = 0;
  packet->radiotap_header.header_length = sizeof(packet->radiotap_header);
  packet->radiotap_header.bitmap = 0;
  packet_buf->len += sizeof(packet->radiotap_header);

  mgm_packet_ptr = &packet->ieee80211_mgmt_frame;
  mgm_packet_ptr->frame_control = IEEE80211_FC(WLAN_FC_TYPE_MGMT,
                                               ieee80211_frame_subtype);
  memcpy(&mgm_packet_ptr->da, destination, sizeof(mgm_packet_ptr->da));
  memcpy(&mgm_packet_ptr->sa, source, sizeof(mgm_packet_ptr->sa));
  memcpy(&mgm_packet_ptr->bssid, bssid, sizeof(mgm_packet_ptr->bssid));
  packet_buf->len += (unsigned char *) &(mgm_packet_ptr->u) -
      (unsigned char *) mgm_packet_ptr;

  return packet_buf;
}

bool packet_buf_can_accept_bytes(size_t length,
                                 struct radiotap_packet_buf *packet_buf) {
  if (length > sizeof(packet_buf->packet) - packet_buf->len)
    return false;

  unsigned char *dest = (unsigned char *) packet_buf + packet_buf->len;
  struct ieee80211_mgmt *mgm_packet_ptr =
      &packet_buf->packet.ieee80211_mgmt_frame;

  switch (WLAN_FC_GET_STYPE(mgm_packet_ptr->frame_control)) {
    case WLAN_FC_STYPE_BEACON:
      return dest >= mgm_packet_ptr->u.beacon.variable;
    case WLAN_FC_STYPE_ACTION:
      if (mgm_packet_ptr->u.action.category == WLAN_ACTION_SPECTRUM_MGMT)
        return dest > &mgm_packet_ptr->u.action.u.chan_switch.switch_count;
      else
        assert(false);
      break;
    case WLAN_FC_STYPE_PROBE_RESP:
      return dest >= mgm_packet_ptr->u.probe_resp.variable;
      break;
    default:
      assert(false);
      break;
  }
}

int packet_buf_add_info_element(unsigned char element_id,
                                unsigned char element_data_length,
                                const unsigned char *element_data,
                                struct radiotap_packet_buf *packet_buf) {
  size_t info_element_len =
      sizeof(element_id) + sizeof(element_data_length) + element_data_length;
  if (!packet_buf_can_accept_bytes(info_element_len, packet_buf))
    return -1;

  unsigned char *dest = (unsigned char *) packet_buf + packet_buf->len;
  *dest++ = element_id;
  *dest++ = element_data_length;
  memcpy(dest, element_data, element_data_length);
  packet_buf->len += info_element_len;
  return 0;
}

int packet_buf_add_raw_data(size_t data_length,
                            const unsigned char *data,
                            struct radiotap_packet_buf *packet_buf) {
  if (!packet_buf_can_accept_bytes(data_length, packet_buf))
      return -1;

  unsigned char *dest = (unsigned char *) packet_buf + packet_buf->len;
  memcpy(dest, data, data_length);
  packet_buf->len += data_length;
  return 0;
}

void packet_buf_add_fixed_params(int frame_num,
                                 struct radiotap_packet_buf *packet_buf) {
  struct ieee80211_mgmt *mgm_packet_ptr =
      &packet_buf->packet.ieee80211_mgmt_frame;

  uint16_t stype = WLAN_FC_GET_STYPE(mgm_packet_ptr->frame_control);
  if (stype == WLAN_FC_STYPE_PROBE_RESP) {
    mgm_packet_ptr->u.probe_resp.timestamp[0] = frame_num;
    mgm_packet_ptr->u.probe_resp.timestamp[1] = frame_num >> 8;
    mgm_packet_ptr->u.probe_resp.timestamp[2] = frame_num >> 16;
    mgm_packet_ptr->u.probe_resp.timestamp[3] = frame_num >> 24;
    mgm_packet_ptr->u.probe_resp.beacon_int = 0x64;  // 0.1024 seconds.  A lie.
    mgm_packet_ptr->u.probe_resp.capab_info = 0x1;  // We are an AP.
    packet_buf->len += sizeof(mgm_packet_ptr->u.probe_resp);
  } else if (stype == WLAN_FC_STYPE_BEACON) {
    mgm_packet_ptr->u.beacon.timestamp[0] = frame_num;
    mgm_packet_ptr->u.beacon.timestamp[1] = frame_num >> 8;
    mgm_packet_ptr->u.beacon.timestamp[2] = frame_num >> 16;
    mgm_packet_ptr->u.beacon.timestamp[3] = frame_num >> 24;
    mgm_packet_ptr->u.beacon.beacon_int = 0x64;  // 0.1024 seconds.  A lie.
    mgm_packet_ptr->u.beacon.capab_info = 0x1;  // We are an AP.
    packet_buf->len += sizeof(mgm_packet_ptr->u.beacon);
  }
}


int packet_buf_add_bss_info(char *ssid_prefix,
                            int bss_number,
                            uint8_t channel,
                            struct radiotap_packet_buf *packet_buf) {
  char *ssid;
  if (create_ssid(ssid_prefix, bss_number, &ssid) != 0) {
    goto err_exit;
  }

  unsigned char supported_rates[] = { 0x82, 0x84, 0x8b, 0x96,
                                      0x0c, 0x12, 0x18, 0x24 };

  if (packet_buf_add_info_element(WLAN_EID_SSID, strlen(ssid),
                                  (unsigned char *) ssid, packet_buf) != 0 ||
      packet_buf_add_info_element(WLAN_EID_SUPP_RATES, sizeof(supported_rates),
                                  supported_rates, packet_buf) != 0 ||
      packet_buf_add_info_element(WLAN_EID_DS_PARAMS, sizeof(channel),
                                  &channel, packet_buf) != 0 ) {
    goto err_exit;
  }
  free(ssid);
  return 0;

err_exit:
  free(ssid);
  return -1;
}

int fill_chanswitch_message_frame(uint8_t channel,
                                  struct radiotap_packet_buf *packet_buf) {
  struct radiotap_packet *packet = &packet_buf->packet;
  struct ieee80211_mgmt *chanswitch_packet_ptr = &packet->ieee80211_mgmt_frame;

  chanswitch_packet_ptr->u.action.category = WLAN_ACTION_SPECTRUM_MGMT;
  packet_buf->len += sizeof(chanswitch_packet_ptr->u.action.category);

  chanswitch_packet_ptr->u.action.u.chan_switch.action_code =
      WLAN_ACTION_SPCT_CHL_SWITCH;
  chanswitch_packet_ptr->u.action.u.chan_switch.element_id =
      WLAN_EID_CHANNEL_SWITCH;
  chanswitch_packet_ptr->u.action.u.chan_switch.length =
      WLAN_EID_LENGTH_CHANNEL_SWITCH;
  chanswitch_packet_ptr->u.action.u.chan_switch.switch_mode =
      WLAN_CHANNEL_SWITCH_MODE_XMIT_FORBIDDEN;
  chanswitch_packet_ptr->u.action.u.chan_switch.new_chan = channel;
  chanswitch_packet_ptr->u.action.u.chan_switch.switch_count = 5;
  packet_buf->len += sizeof(chanswitch_packet_ptr->u.action.u.chan_switch);

  return 0;
}

int fill_beacon_proberesp_message_frame(char *ssid_prefix,
                                        uint8_t channel,
                                        int bss_number,
                                        int frame_num,
                                        struct radiotap_packet_buf *packet_buf)
{
  packet_buf_add_fixed_params(frame_num, packet_buf);
  if (packet_buf_add_bss_info(ssid_prefix, bss_number, channel, packet_buf) !=
      0) {
    fprintf(stderr, "BSS info didn't fit in output buffer!?\n");
    return -EINVAL;
  }

  return 0;
}

struct radiotap_packet_buf *get_message_frame(
    enum message_type message_type,
    const unsigned char *interface_address,
    const unsigned char *destination_address,
    char *ssid_prefix,
    uint8_t channel,
    int bss_count,
    int frame_num,
    unsigned char *footer_data,
    size_t footer_len) {
  int bss_number = 0;
  unsigned char bss_address[ETH_ALEN];
  memcpy(bss_address, interface_address, sizeof(bss_address));
  if (bss_count) {
    bss_number = frame_num % bss_count;
    bss_address[0] = 0x2;  // Make this an administratively scoped address.
    bss_address[5] += bss_number;  // Make the BSSIDs unique.
    bss_address[4] += bss_number / 256;
  }

  struct radiotap_packet_buf *packet_buf =
      packet_buf_alloc(message_type_to_80211_frame_subtype[message_type],
                       bss_address, interface_address, destination_address);

  /* Generate frame based on the message type */
  int ret;
  switch (message_type) {
    case BEACON:
    case PROBE_RESPONSE:
      ret = fill_beacon_proberesp_message_frame(ssid_prefix, channel,
                                                bss_number, frame_num,
                                                packet_buf);
      break;
    case CHANNEL_SWITCH:
      ret = fill_chanswitch_message_frame(channel, packet_buf);
      break;
  }

  if (ret != 0) {
    fprintf(stderr, "Message frame generation failed with %d.\n", ret);
    ret = -EINVAL;
    goto err_exit;
  }

  if (footer_data) {
    ret = packet_buf_add_raw_data(footer_len, footer_data, packet_buf);
    if (ret != 0) {
      fprintf(stderr, "Footer append failed with %d.\n", ret);
      goto err_exit;
    }
  }

  return packet_buf;

err_exit:
  free(packet_buf);
  return NULL;
}

static int g_do_exit = 0;

void set_do_exit(int signum) {
  g_do_exit = 1;
}

int get_footer_bytes(char *footer_file, unsigned char **footer) {
  struct stat st;
  if (stat(footer_file, &st) != 0) {
    fprintf(stderr, "Error getting footer file size.\n");
    goto cleanup_footer;
  }

  if (!st.st_size) {
    fprintf(stderr, "Footer file must be non-empty.\n");
    goto cleanup_footer;
  }

  *footer = (unsigned char *) malloc(st.st_size);

  int fd = open(footer_file, O_RDONLY);
  if (fd == -1) {
    fprintf(stderr, "Error opening footer file.\n");
    goto cleanup_mem;
  }
  if (read(fd, *footer, st.st_size) != st.st_size) {
    fprintf(stderr, "Error reading footer file.\n");
    goto cleanup_fd;
  }
  close(fd);
  return st.st_size;

cleanup_fd:
  close(fd);
cleanup_mem:
  free(*footer);
cleanup_footer:
  *footer = NULL;
  return -1;
}

int main(int argc, char **argv) {
  char *interface = NULL;
  int interface_index;
  unsigned char mac_address[ETH_ALEN];
  char *message_name = NULL;
  unsigned char *frame = NULL;
  const int promiscuous = 1;
  pcap_t *pcap = NULL;
  char errbuf[PCAP_ERRBUF_SIZE];
  int inject_return;
  char buf[2048];
  int exit_value = 1;
  int pkt_count = 1;
  unsigned char channel = 1;
  int ms_delay = 0;
  int num_bss = 0;
  char *ssid_prefix = NULL;
  char *destination_address_string = NULL;
  char *footer_file = NULL;
  unsigned char *footer_data = NULL;
  int c;

  while ((c = getopt (argc, argv, "hb:c:d:i:n:t:s:a:f:")) != -1) {
    switch (c) {
      case 'b':
        num_bss = atoi(optarg);
        break;
      case 'c':
        channel = (unsigned char) atoi(optarg);
        break;
      case 'd':
        ms_delay = atoi(optarg);
        break;
      case 'i':
        interface = optarg;
        break;
      case 'n':
        pkt_count = atoi(optarg);
        break;
      case 't':
        message_name = optarg;
        break;
      case 's':
        ssid_prefix = optarg;
        break;
      case 'a':
        destination_address_string = optarg;
        break;
      case 'f':
        footer_file = optarg;
        break;
      case 'h':
      default:
        fprintf(stderr, "%s", usage);
        return 1;
    }
  }

  /* Validate arguments; ordering follows usage message */
  if (interface == NULL || message_name == NULL) {
    fprintf(stderr, "%s", usage);
    goto cleanup;
  }
  if (ms_delay < 0) {
    fprintf(stderr, "Invalid value for delay %d, must be >= 0.\n",
            ms_delay);
    goto cleanup;
  }

  enum message_type message_type;
  if (strcmp(message_name, type_beacon) == 0) {
    message_type = BEACON;
  } else if (strcmp(message_name, type_channel_switch) == 0) {
    message_type = CHANNEL_SWITCH;
  } else if (strcmp(message_name, type_probe_response) == 0) {
    message_type = PROBE_RESPONSE;
  } else {
    fprintf(stderr, "Invalid message type [%s].\n", message_name);
    goto cleanup;
  }

  if (ssid_prefix && message_type == CHANNEL_SWITCH) {
    fprintf(stderr, "-s is not valid for message type [%s].\n", message_name);
    goto cleanup;
  }

  unsigned char custom_dest[ETH_ALEN];
  const unsigned char broadcast_address[] = { 0xff, 0xff, 0xff,
                                              0xff, 0xff, 0xff };
  const unsigned char *destination_address_bytes;
  if (destination_address_string) {
    if (sscanf(destination_address_string, "%hhx:%hhx:%hhx:%hhx:%hhx:%hhx",
               &custom_dest[0], &custom_dest[1], &custom_dest[2],
               &custom_dest[3], &custom_dest[4], &custom_dest[5]) !=
        ETH_ALEN) {
      fprintf(stderr, "Invalid destination address [%s].\n",
              destination_address_string);
      goto cleanup;
    }
    destination_address_bytes = custom_dest;
  } else {
    destination_address_bytes = broadcast_address;
  }

  size_t footer_len = 0;
  if (footer_file) {
    footer_len = get_footer_bytes(footer_file, &footer_data);
  }

  /* Get interface information */
  if (get_interface_info(interface, &interface_index, mac_address) != 0) {
    fprintf(stderr, "Can't get information on AP interface %s.\n", interface);
    goto cleanup;
  }

  pcap = pcap_open_live(interface,
                        sizeof(buf),
                        promiscuous,
                        PACKET_TIMEOUT_MS,
                        errbuf);
  if (pcap == NULL) {
    fprintf(stderr, "Could not open capture handle.\n");
    goto cleanup;
  }

  if (pcap_datalink(pcap) != DLT_IEEE802_11_RADIO) {
    fprintf(stderr, "Interface %s does not use RadioTap.\n", interface);
    goto cleanup;
  }

  struct sigaction exit_action;
  exit_action.sa_handler = set_do_exit;
  exit_action.sa_flags = 0;
  sigfillset(&exit_action.sa_mask);
  sigaction(SIGTERM, &exit_action, NULL);
  sigaction(SIGINT, &exit_action, NULL);

  /*
   * Generate and inject number of frames specified. Continuous sending
   * if number of frame specified is 0.
   */
  int i = 0;
  while ( (i < pkt_count) || (pkt_count == 0) ) {
    struct radiotap_packet_buf *packet_buf =
        get_message_frame(message_type, mac_address, destination_address_bytes,
                          ssid_prefix, channel, num_bss, i, footer_data,
                          footer_len);
    if (!packet_buf) {
      fprintf(stderr, "Can't generate a frame of type %s.\n", message_name);
      goto cleanup;
    }

    unsigned char *frame = (unsigned char *) &packet_buf->packet;
    size_t frame_length = packet_buf->len;
    size_t j = 0;
    if (i == 0) {
      printf("Frame (length %zu): ", frame_length);
      for (j = 0; j < frame_length; j++) {
        printf("%02x ", frame[j]);
      }
      printf("\n");
    }

    if (ms_delay > 0)
      usleep(ms_delay * 1000);

    inject_return = pcap_inject(pcap, frame, frame_length);
    if (i == 1) printf("Inject returned %d.\n", inject_return);
    i++;

    free(frame);
    frame=NULL;

    if (g_do_exit)
      break;
  }
  exit_value = 0;
  printf("Transmitted %d frames.\n", i);

cleanup:
  if (pcap) {
    pcap_close(pcap);
  }
  free(footer_data);
  free(frame);

  return exit_value;
}
