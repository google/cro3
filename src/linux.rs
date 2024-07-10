use anyhow::Result;
use once_cell::sync::Lazy;
use regex::Regex;

pub fn cmdline_to_masked(s: &str) -> Result<String> {
    static RE_CMDLINE_DM_PARAMS: Lazy<Regex> = Lazy::new(|| Regex::new(r#"dm="[^"]*""#).unwrap());
    static RE_CMDLINE_DM_HASH: Lazy<Regex> = Lazy::new(|| Regex::new("[0-9a-z]{64}").unwrap());
    static RE_CMDLINE_UUID: Lazy<Regex> = Lazy::new(|| {
        Regex::new("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}").unwrap()
    });
    static RE_CMDLINE_CROS_LSB_RELEASE_HASH: Lazy<Regex> =
        Lazy::new(|| Regex::new("cros_lsb_release_hash=.{44}").unwrap());
    let s = RE_CMDLINE_DM_PARAMS.replace_all(s, "{DM_PARAMS}");
    let s = RE_CMDLINE_DM_HASH.replace_all(&s, "{HASH{64}}");
    let s = RE_CMDLINE_UUID.replace_all(&s, "{UUID}");
    let s = RE_CMDLINE_CROS_LSB_RELEASE_HASH.replace_all(&s, "{CROS_LSB_HASH}");
    Ok(s.to_string())
}

pub fn cmdline_to_mitigations(s: &str) -> Result<String> {
    let s = cmdline_to_masked(s)?;
    let s = s
        .split(' ')
        .filter(|s| {
            !s.starts_with("add_efi_memmap")
                && !s.starts_with("alg=")
                && !s.starts_with("console=")
                && !s.starts_with("cros_debug")
                && !s.starts_with("cros_lsb_release_hash=")
                && !s.starts_with("cros_secure")
                && !s.starts_with("dm_verity.")
                && !s.starts_with("drm.")
                && !s.starts_with("hashstart=")
                && !s.starts_with("hashtree=")
                && !s.starts_with("i915.")
                && !s.starts_with("init=")
                && !s.starts_with("kern_guid=")
                && !s.starts_with("loglevel=")
                && !s.starts_with("noinitrd")
                && !s.starts_with("noresume")
                && !s.starts_with("ramoops.")
                && !s.starts_with("root=")
                && !s.starts_with("root_hexdigest=")
                && !s.starts_with("rootwait")
                && !s.starts_with("rw")
                && !s.starts_with("salt=")
                && !s.starts_with("vt.")
                && !s.starts_with("{DM_PARAMS}")
                && !s.starts_with("{CROS_LSB_HASH}")
                && !s.starts_with("kvm.tdp_mmu=")
                && !s.starts_with("intel_idle.")
                && !s.starts_with("cpuidle.")
                && !s.starts_with("gsmi.")
                && !s.starts_with("disablevmx=")
                && !s.starts_with("intel_pmc_core.")
                && !s.starts_with("irqchip.")
                && !s.starts_with("sdhci.debug_quirks=")
                && true
        })
        .collect::<Vec<&str>>()
        .join(" ");
    Ok(s.to_string())
}
