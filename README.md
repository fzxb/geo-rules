# rule-set

> Generated from the [`main`](https://github.com/fzxb/geo-rules/tree/main) branch by GitHub Actions. Do not edit.

`2026-11-27T03:33:18Z` · sing-box `1.14.5` · source format v3 · 47 rule-sets · 152,225 domains · 34,567 prefixes · 5.7 MiB

Counts are per rule-set; service and collection layers overlap.

## Usage

```jsonc
{
  "route": {
    "rule_set": [
      {
        "type": "remote",
        "tag": "cn-domain",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/cn.srs",
        "http_client": "proxy",
        "update_interval": "1d"
      }
    ],
    "rules": [
      { "rule_set": ["cn-domain"], "outbound": "direct" }
    ],
    "final": "proxy"
  }
}
```

`format` may be omitted for `.json`/`.srs` URLs.

## Rule-sets

| Rule-set | Type | Entries | JSON | SRS |
| --- | --- | ---: | ---: | ---: |
| `domain/gfw` | domain | 4,399 | [105.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/gfw.json) | [29.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/gfw.srs) |
| `domain/privacy` | domain | 1,685 | [39.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/privacy.json) | [10.6 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/privacy.srs) |
| `domain/cn` | domain | 110,211 | [2.9 MiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/cn.json) | [422.9 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/cn.srs) |
| `domain/private` | domain | 50 | [1.6 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/private.json) | [441 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/private.srs) |
| `domain/ads` | domain | 905 | [25.4 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/ads.json) | [7.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/ads.srs) |
| `domain/cn-global` | domain | 1,226 | [35.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/cn-global.json) | [9.6 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/cn-global.srs) |
| `domain/global` | domain | 23,340 | [584.6 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/global.json) | [139.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/global.srs) |
| `domain/service/google` | domain | 820 | [19.7 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/google.json) | [5.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/google.srs) |
| `domain/service/youtube` | domain | 176 | [4.3 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/youtube.json) | [1.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/youtube.srs) |
| `domain/service/netflix` | domain | 28 | [1.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/netflix.json) | [341 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/netflix.srs) |
| `domain/service/disney` | domain | 222 | [6.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/disney.json) | [2.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/disney.srs) |
| `domain/service/spotify` | domain | 25 | [897 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/spotify.json) | [358 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/spotify.srs) |
| `domain/service/telegram` | domain | 21 | [564 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/telegram.json) | [245 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/telegram.srs) |
| `domain/service/twitter` | domain | 24 | [667 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/twitter.json) | [278 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/twitter.srs) |
| `domain/service/ai` | domain | 220 | [6.4 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/ai.json) | [2.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/ai.srs) |
| `domain/service/github` | domain | 60 | [2.4 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/github.json) | [724 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/github.srs) |
| `domain/service/apple` | domain | 1,355 | [38.5 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/apple.json) | [12.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/apple.srs) |
| `domain/service/microsoft` | domain | 512 | [14.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/microsoft.json) | [4.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/microsoft.srs) |
| `domain/service/steam` | domain | 44 | [1.5 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/steam.json) | [608 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/steam.srs) |
| `domain/service/tiktok` | domain | 39 | [1.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/tiktok.json) | [478 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/tiktok.srs) |
| `domain/service/meta` | domain | 478 | [12.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/meta.json) | [3.6 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/meta.srs) |
| `domain/service/discord` | domain | 28 | [906 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/discord.json) | [405 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/discord.srs) |
| `domain/service/twitch` | domain | 35 | [1.4 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/twitch.json) | [435 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/twitch.srs) |
| `domain/service/reddit` | domain | 12 | [395 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/reddit.json) | [178 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/reddit.srs) |
| `domain/service/epicgames` | domain | 31 | [966 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/epicgames.json) | [401 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/epicgames.srs) |
| `domain/service/amazon` | domain | 182 | [4.7 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/amazon.json) | [1.6 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/amazon.srs) |
| `domain/proxy` | domain | 6,137 | [151.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/proxy.json) | [41.5 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/proxy.srs) |
| `ip/cn` | ip | 12,938 | [348.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn.json) | [54.9 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn.srs) |
| `ip/cn4` | ip | 7,417 | [193.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn4.json) | [27.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn4.srs) |
| `ip/cn6` | ip | 5,521 | [155.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn6.json) | [25.9 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn6.srs) |
| `ip/private` | ip | 27 | [712 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/private.json) | [208 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/private.srs) |
| `ip/gfw` | ip | 1 | [101 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/gfw.json) | [34 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/gfw.srs) |
| `ip/service/telegram` | ip | 11 | [374 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/telegram.json) | [114 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/telegram.srs) |
| `ip/service/cloudflare` | ip | 22 | [653 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/cloudflare.json) | [218 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/cloudflare.srs) |
| `ip/service/google` | ip | 148 | [3.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/google.json) | [848 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/google.srs) |
| `ip/service/gcloud` | ip | 495 | [12.7 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/gcloud.json) | [1.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/gcloud.srs) |
| `ip/service/aws` | ip | 217 | [5.9 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/aws.json) | [1.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/aws.srs) |
| `ip/service/github` | ip | 149 | [4.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/github.json) | [682 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/github.srs) |
| `ip/service/netflix` | ip | 256 | [7.6 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/netflix.json) | [518 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/netflix.srs) |
| `ip/service/twitter` | ip | 14 | [467 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/twitter.json) | [162 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/twitter.srs) |
| `ip/service/steam` | ip | 32 | [965 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/steam.json) | [222 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/steam.srs) |
| `ip/service/meta` | ip | 36 | [1016 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/meta.json) | [264 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/meta.srs) |
| `ip/service/tiktok` | ip | 172 | [4.7 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/tiktok.json) | [582 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/tiktok.srs) |
| `ip/operator/telecom` | ip | 3,232 | [85.4 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/telecom.json) | [11.9 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/telecom.srs) |
| `ip/operator/unicom` | ip | 2,466 | [66.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/unicom.json) | [9.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/unicom.srs) |
| `ip/operator/mobile` | ip | 1,224 | [32.5 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/mobile.json) | [4.6 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/mobile.srs) |
| `ip/operator/cernet` | ip | 189 | [5.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/cernet.json) | [891 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/cernet.srs) |

## Verification

Every file's SHA-256 is recorded in [`manifest.json`](manifest.json):

```bash
curl -sL https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/manifest.json | jq -r '.rulesets[].files.srs.sha256'
```

## Sources

| Source | Kind | Revision |
| --- | --- | --- |
| `aws_ip` | `aws_ipranges` | `-` |
| `bgp_v4` | `ip2asn` | `-` |
| `bgp_v6` | `ip2asn` | `-` |
| `cernet` | `cidr` | `31f093f8325f` |
| `china4` | `cidr` | `31f093f8325f` |
| `china46` | `cidr` | `31f093f8325f` |
| `china6` | `cidr` | `31f093f8325f` |
| `china_domain` | `dnsmasq_china` | `a30697b2725c` |
| `cloudflare_ip` | `cloudflare` | `-` |
| `dlc` | `dlc` | `20261127013500` |
| `gcloud_ip` | `google_ipranges` | `-` |
| `geo_cn` | `dbip_country` | `-` |
| `gfwlist` | `gfwlist` | `f09bc923be06` |
| `github_ip` | `github_meta` | `-` |
| `google_ip` | `google_ipranges` | `-` |
| `iana_private_names` | `iana_special_domains` | `-` |
| `iana_private_reverse` | `iana_locally_served_zones` | `-` |
| `iana_v4_special` | `iana_special` | `-` |
| `iana_v6_special` | `iana_special` | `-` |
| `mobile` | `cidr` | `31f093f8325f` |
| `rir_afrinic` | `rir` | `-` |
| `rir_apnic` | `rir` | `-` |
| `rir_arin` | `rir` | `-` |
| `rir_lacnic` | `rir` | `-` |
| `rir_ripe` | `rir` | `-` |
| `telecom` | `cidr` | `31f093f8325f` |
| `telegram_ip` | `cidr` | `-` |
| `unicom` | `cidr` | `31f093f8325f` |
