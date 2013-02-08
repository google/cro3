#!/bin/bash

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Script to make the test.dtb file

dtc -O dtb -o test.dtb -p 1000 - <<EOF
/dts-v1/;
/ {
    #address-cells = <0x00000001>;
    #size-cells = <0x00000001>;
    model = "NVIDIA Seaboard";
    compatible = "nvidia,seaboard", "nvidia,tegra250";
    interrupt-parent = <0x00000001>;
    chosen {
        bootargs = "";
    };
    aliases {
        console = "/serial@70006300";
        usb0 = "/usb@0xc5008000";
        usb1 = "/usb@0xc5000000";
        sdmmc0 = "/sdhci@c8000600";
        sdmmc1 = "/sdhci@c8000400";
    };
    memory {
        device_type = "memory";
        reg = <0x00000000 0x616d6261>;
    };
    amba {
        compatible = "simple-bus";
        #address-cells = <0x00000001>;
        #size-cells = <0x00000001>;
        ranges;
        interrupt-controller@50041000 {
            compatible = "nvidia,tegra250-gic", "arm,gic";
            interrupt-controller;
            #interrupt-cells = <0x00000001>;
            reg = <0x50041000 0x00001000 0x50040100 0x00000100>;
            linux,phandle = <0x00000001>;
            phandle = <0x00000001>;
        };
    };
    gpio@6000d000 {
        compatible = "nvidia,tegra250-gpio", "ns16550";
        reg = <0x6000d000 0x000000b1>;
        interrupts = <0x00000040 0x00000041 0x00000042 0x00000043 0x00000057
            0x00000077 0x00000079>;
        #gpio-cells = <0x00000002>;
        gpio-controller;
        linux,phandle = <0x00000002>;
        phandle = <0x00000002>;
    };
    serial@70006000 {
        compatible = "nvidia,tegra250-uart", "ns16550";
        reg = <0x70006000 0x00000040>;
        id = <0x00000000>;
        reg-shift = <0x00000002>;
        interrupts = <0x00000044>;
        status = "disabled";
    };
    serial@70006040 {
        compatible = "nvidia,tegra250-uart", "ns16550";
        reg = <0x70006040 0x00000040>;
        id = <0x00000001>;
        reg-shift = <0x00000002>;
        interrupts = <0x00000045>;
        status = "disabled";
    };
    serial@70006200 {
        compatible = "nvidia,tegra250-uart", "ns16550";
        reg = <0x70006200 0x00000100>;
        id = <0x00000002>;
        reg-shift = <0x00000002>;
        interrupts = <0x0000004e>;
        status = "disabled";
    };
    serial@70006300 {
        compatible = "nvidia,tegra250-uart", "ns16550";
        reg = <0x70006300 0x00000100>;
        id = <0x00000003>;
        reg-shift = <0x00000002>;
        interrupts = <0x0000007a>;
        status = "ok";
        clock-frequency = <0x0cdfe600>;
        linux,phandle = <0x00000004>;
        phandle = <0x00000004>;
    };
    serial@70006400 {
        compatible = "nvidia,tegra250-uart", "ns16550";
        reg = <0x70006400 0x00000100>;
        id = <0x00000004>;
        reg-shift = <0x00000002>;
        interrupts = <0x0000007b>;
        status = "disabled";
    };
    sdhci@c8000000 {
        compatible = "nvidia,tegra250-sdhci";
        reg = <0xc8000000 0x00000200>;
        interrupts = <0x0000002e>;
        periph-id = <0x0000000e>;
        status = "disabled";
    };
    sdhci@c8000200 {
        compatible = "nvidia,tegra250-sdhci";
        reg = <0xc8000200 0x00000200>;
        interrupts = <0x0000002f>;
        periph-id = <0x00000009>;
        status = "disabled";
    };
    sdhci@c8000400 {
        compatible = "nvidia,tegra250-sdhci";
        reg = <0xc8000400 0x00000200>;
        interrupts = <0x00000033>;
        periph-id = <0x00000045>;
        status = "ok";
        width = <0x00000004>;
        removable = <0x00000001>;
        cd-gpio = <0x00000002 0x00000045 0x00000000>;
        wp-gpio = <0x00000002 0x00000039 0x00000000>;
        power-gpio = <0x00000002 0x00000046 0x00000003>;
    };
    sdhci@c8000600 {
        compatible = "nvidia,tegra250-sdhci";
        reg = <0xc8000600 0x00000200>;
        interrupts = <0x0000003f>;
        periph-id = <0x0000000f>;
        status = "ok";
        width = <0x00000004>;
        removable = <0x00000000>;
    };
    pwm@7000a000 {
        compatible = "nvidia,tegra250-sdhci";
        reg = <0x7000a000 0x00000004>;
        status = "disabled";
    };
    pwm@7000a010 {
        compatible = "nvidia,tegra250-sdhci";
        reg = <0x7000a010 0x00000004>;
        status = "disabled";
    };
    pwm@7000a020 {
        compatible = "nvidia,tegra250-sdhci";
        reg = <0x7000a020 0x00000004>;
        status = "disabled";
        linux,phandle = <0x00000005>;
        phandle = <0x00000005>;
    };
    pwm@7000a030 {
        compatible = "nvidia,tegra250-sdhci";
        reg = <0x7000a030 0x00000004>;
        status = "disabled";
    };
    display@0x54200000 {
        compatible = "nvidia,tegra250-display";
        reg = <0x54200000 0x00040000>;
        status = "disabled";
        linux,phandle = <0x00000006>;
        phandle = <0x00000006>;
    };
    usbparams@0 {
        compatible = "nvidia,tegra250-usbparams";
        osc-frequency = <0x00c65d40>;
        params = <0x000003c0 0x0000000d 0x00000000 0x0000000c 0x00000000
                0x00000002 0x00000033 0x00000005 0x0000007f 0x00007ef4
                0x00000005>;
    };
    usbparams@1 {
        compatible = "nvidia,tegra250-usbparams";
        osc-frequency = <0x0124f800>;
        params = <0x000000c8 0x00000004 0x00000000 0x00000003 0x00000000
        0x00000003 0x0000004b 0x00000006 0x000000bb 0x0000bb80 0x00000007>;
    };
    usbparams@2 {
        compatible = "nvidia,tegra250-usbparams";
        osc-frequency = <0x00b71b00>;
        params = <0x000003c0 0x0000000c 0x00000000 0x0000000c 0x00000000
        0x00000002 0x0000002f 0x00000004 0x00000076 0x00007530 0x00000005>;
    };
    usbparams@3 {
        compatible = "nvidia,tegra250-usbparams";
        osc-frequency = <0x018cba80>;
        params = <0x000003c0 0x0000001a 0x00000000 0x0000000c 0x00000000
        0x00000004 0x00000066 0x00000009 0x000000fe 0x0000fde8 0x00000009>;
    };
    usb@0xc5008000 {
        compatible = "nvidia,tegra250-usb";
        reg = <0xc5008000 0x00008000>;
        periph-id = <0x0000003b>;
        status = "ok";
        utmi = <0x00000003>;
        host-mode = <0x00000000>;
    };
    usb@0xc5000000 {
        compatible = "nvidia,tegra250-usb";
        reg = <0xc5000000 0x00008000>;
        periph-id = <0x00000016>;
        status = "ok";
        host-mode = <0x00000001>;
    };
    kbc@0x7000e200 {
        compatible = "nvidia,tegra250-kbc";
        reg = <0x7000e200 0x00000078>;
        keycode-plain = <0x00007773 0x617a00de 0x00000000 0x00000000
        0x00000000 0x00000000 0x35347265 0x66647800 0x37367468
        0x67766320 0x39387579 0x6a6e625c 0x2d306f69 0x6c6b2c6d
        0x003d5d0d 0x00000000 0x00000000 0xdfdf0000 0x00000000
        0x00dc00dd 0x00000000 0x00000000 0x5b70273b 0x2f2e0000
        0x00000833 0x32000000 0x007f0000 0x00000000 0x00000071
        0x00003100 0x1b600009 0x00000000>;
        keycode-shift = <0x00005753 0x415a0000 0x00000000 0x00000000
        0x00000000 0x00000000 0x25245245 0x46445800 0x265e5448
        0x47564320 0x282a5559 0x4a4e427c 0x5f294f49 0x4c4b3c4d
        0x002b7d0d 0x00000000 0x00000000 0x00000000 0x00000000
        0x00000000 0x00000000 0x00000000 0x7b50223a 0x3f3e0000
        0x00000823 0x40000000 0x007f0000 0x00000000 0x00000051
        0x00002100 0x1b7e0009 0x00000000>;
        keycode-fn = <0x00000000 0x00000000 0x00000000 0x00000000
        0x00000000 0x00000000 0x00000000 0x00000000 0x37000000
        0x00000000 0x39383400 0x31000000 0x002f3635 0x33320030
        0x00000000 0x00000000 0x00000000 0x00000000 0x00000000
        0x00000000 0x00000000 0x00000000 0x0027002d 0x2b2e0000
        0x00000000 0x00000000 0x00000000 0x00000000 0x00000000
        0x00000000 0x00000000 0x3f000000>;
        keycode-ctrl = <0x00001713 0x011a0000 0x00000000 0x00000000
        0x00000000 0x00000000 0x00001205 0x06041800 0x00001408
        0x07160300 0x00001519 0x0a0e0200 0x00000f09 0x0c0b000d
        0x00000000 0x00000000 0x00000000 0x00000000 0x00000000
        0x00000000 0x00000000 0x00000000 0x00100000 0x00000000
        0x00000000 0x00000000 0x00000000 0x00000000 0x00000011
        0x00000000 0x00000000 0x00000000>;
    };
    flash@0 {
        #address-cells = <0x00000001>;
        #size-cells = <0x00000001>;
        compatible = "winbond,W25Q32BVSSIG", "cfi-flash", "chromeos,flashmap";
        reg = <0x00000000 0x00400000>;
        onestop-layout@0 {
            label = "onestop-layout";
            reg = <0x00000000 0x00080000>;
        };
        firmware-image@0 {
            label = "firmware-image";
            reg = <0x00000000 0x0007df00>;
        };
        verification-block@7df00 {
            label = "verification-block";
            reg = <0x0007df00 0x00002000>;
        };
        firmware-id@7ff00 {
            label = "firmware-id";
            reg = <0x0007ff00 0x00000100>;
        };
        readonly@0 {
            label = "readonly";
            reg = <0x00000000 0x00100000>;
            read-only;
        };
        bct@0 {
            label = "bct";
            reg = <0x00000000 0x00010000>;
            read-only;
        };
        ro-onestop@10000 {
            label = "ro-onestop";
            reg = <0x00010000 0x00080000>;
            read-only;
            type = "blob boot";
        };
        ro-gbb@90000 {
            label = "gbb";
            reg = <0x00090000 0x00020000>;
            read-only;
            type = "blob gbb";
        };
        ro-data@b0000 {
            label = "ro-data";
            reg = <0x000b0000 0x00010000>;
            read-only;
        };
        ro-vpd@c0000 {
            label = "ro-vpd";
            reg = <0x000c0000 0x00010000>;
            read-only;
            type = "wiped";
            wipe-value = [ffffffff];
        };
        fmap@d0000 {
            label = "ro-fmap";
            reg = <0x000d0000 0x00000400>;
            read-only;
            type = "fmap";
            ver-major = <0x00000001>;
            ver-minor = <0x00000000>;
        };
        readwrite@100000 {
            label = "readwrite";
            reg = <0x00100000 0x00100000>;
        };
        rw-vpd@100000 {
            label = "rw-vpd";
            reg = <0x00100000 0x00080000>;
            type = "wiped";
            wipe-value = [ffffffff];
        };
        shared-dev-cfg@180000 {
            victoria;
            label = "shared-dev-cfg";
            reg = <0x00180000 0x00040000>;
            type = "wiped";
            wipe-value = "";
        };
        shared-data@1c0000 {
            label = "shared-data";
            reg = <0x001c0000 0x00030000>;
            type = "wiped";
            wipe-value = "";
        };
        shared-env@1ff000 {
            label = "shared-env";
            reg = <0x001ff000 0x00001000>;
            type = "wiped";
            wipe-value = "";
        };
        readwrite-a@200000 {
            label = "readwrite-a";
            reg = <0x00200000 0x00080000>;
            block-lba = <0x00000022>;
        };
        rw-a-onestop@200000 {
            label = "rw-a-onestop";
            reg = <0x00200000 0x00080000>;
            type = "blob boot";
        };
        readwrite-b@300000 {
            label = "readwrite-b";
            reg = <0x00300000 0x00080000>;
            block-lba = <0x00000422>;
        };
        rw-b-onestop@300000 {
            label = "rw-b-onestop";
            reg = <0x00300000 0x00080000>;
            type = "blob boot";
        };
    };
    config {
        silent_console = <0x00000000>;
        odmdata = <0x300d8011>;
        hwid = "ARM SEABOARD TEST 1176";
        machine-arch-id = <0x00000bbd>;
        gpio_port_write_protect_switch = <0x0000003b>;
        gpio_port_recovery_switch = <0x00000038>;
        gpio_port_developer_switch = <0x000000a8>;
        polarity_write_protect_switch = <0x00000001>;
        polarity_recovery_switch = <0x00000000>;
        polarity_developer_switch = <0x00000001>;
    };
    switch {
        compatible = "nvidia,spi-uart-switch";
        uart = <0x00000004>;
        gpios = <0x00000002 0x00000043 0x00000001>;
    };
    lcd {
        compatible = "nvidia,tegra2-lcd";
        width = <0x00000556>;
        height = <0x00000300>;
        bits_per_pixel = <0x00000010>;
        pwfm = <0x00000005>;
        display = <0x00000006>;
        frame-buffer = <0x1c022000>;
        pixel_clock = <0x04354540>;
        horiz_timing = <0x0000000b 0x0000003a 0x0000003a 0x0000003a>;
        vert_timing = <0x00000001 0x00000004 0x00000004 0x00000004>;
        gpios = <0x00000002 0x0000001c 0x00000003 0x00000002 0x0000000a
            0x00000003 0x00000002 0x000000b0 0x00000003 0x00000002
            0x00000016 0x00000003>;
    };
    usbphy@0 {
        compatible = "smsc,usb3315";
        status = "ok";
        linux,phandle = <0x00000003>;
        phandle = <0x00000003>;
    };
};
EOF
