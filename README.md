# rule-set

> Generated from the [`main`](https://github.com/fzxb/geo-rules/tree/main) branch by GitHub Actions. Do not edit.

`2026-11-14T01:20:01Z` · sing-box `1.14.4` · source format v3 · 46 rule-sets · 152,053 domains · 34,273 prefixes · 5.2 MiB

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

`http_client` is required since sing-box 1.14; `format` may be omitted. Match `gfw` before `cn` (~0.6% overlap via the bare `cn` TLD).

## Rule-sets

| Rule-set | Type | Entries | JSON | SRS |
| --- | --- | ---: | ---: | ---: |
| `domain/gfw` | domain | 4,371 | [104.3 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/gfw.json) | [27.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/gfw.srs) |
| `domain/privacy` | domain | 1,685 | [39.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/privacy.json) | [10.6 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/privacy.srs) |
| `domain/cn` | domain | 110,236 | [2.5 MiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/cn.json) | [428.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/cn.srs) |
| `domain/private` | domain | 39 | [1.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/private.json) | [427 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/private.srs) |
| `domain/ads` | domain | 904 | [25.3 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/ads.json) | [7.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/ads.srs) |
| `domain/non-cn` | domain | 24,304 | [609.4 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/non-cn.json) | [144.9 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/non-cn.srs) |
| `domain/service/google` | domain | 819 | [19.6 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/google.json) | [5.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/google.srs) |
| `domain/service/youtube` | domain | 176 | [4.3 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/youtube.json) | [1.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/youtube.srs) |
| `domain/service/netflix` | domain | 24 | [752 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/netflix.json) | [249 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/netflix.srs) |
| `domain/service/disney` | domain | 221 | [6.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/disney.json) | [2.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/disney.srs) |
| `domain/service/spotify` | domain | 25 | [897 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/spotify.json) | [361 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/spotify.srs) |
| `domain/service/telegram` | domain | 21 | [564 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/telegram.json) | [248 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/telegram.srs) |
| `domain/service/twitter` | domain | 24 | [667 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/twitter.json) | [284 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/twitter.srs) |
| `domain/service/ai` | domain | 217 | [6.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/ai.json) | [2.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/ai.srs) |
| `domain/service/github` | domain | 60 | [2.4 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/github.json) | [727 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/github.srs) |
| `domain/service/apple` | domain | 1,485 | [42.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/apple.json) | [13.3 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/apple.srs) |
| `domain/service/microsoft` | domain | 511 | [13.9 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/microsoft.json) | [4.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/microsoft.srs) |
| `domain/service/steam` | domain | 44 | [1.5 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/steam.json) | [611 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/steam.srs) |
| `domain/service/tiktok` | domain | 39 | [1.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/tiktok.json) | [482 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/tiktok.srs) |
| `domain/service/meta` | domain | 478 | [12.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/meta.json) | [3.7 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/meta.srs) |
| `domain/service/discord` | domain | 28 | [906 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/discord.json) | [408 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/discord.srs) |
| `domain/service/twitch` | domain | 35 | [1.4 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/twitch.json) | [438 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/twitch.srs) |
| `domain/service/reddit` | domain | 12 | [395 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/reddit.json) | [181 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/reddit.srs) |
| `domain/service/epicgames` | domain | 30 | [881 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/epicgames.json) | [373 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/epicgames.srs) |
| `domain/service/amazon` | domain | 182 | [4.7 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/amazon.json) | [1.7 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/service/amazon.srs) |
| `domain/proxy` | domain | 6,101 | [150.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/proxy.json) | [39.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/domain/proxy.srs) |
| `ip/cn` | ip | 12,945 | [348.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn.json) | [53.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn.srs) |
| `ip/cn4` | ip | 7,427 | [193.2 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn4.json) | [26.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn4.srs) |
| `ip/cn6` | ip | 5,518 | [155.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn6.json) | [25.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/cn6.srs) |
| `ip/private` | ip | 27 | [712 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/private.json) | [211 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/private.srs) |
| `ip/gfw` | ip | 1 | [101 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/gfw.json) | [32 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/gfw.srs) |
| `ip/service/telegram` | ip | 11 | [374 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/telegram.json) | [117 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/telegram.srs) |
| `ip/service/cloudflare` | ip | 22 | [653 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/cloudflare.json) | [221 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/cloudflare.srs) |
| `ip/service/google` | ip | 148 | [3.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/google.json) | [851 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/google.srs) |
| `ip/service/gcloud` | ip | 495 | [12.7 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/gcloud.json) | [1.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/gcloud.srs) |
| `ip/service/aws` | ip | 216 | [5.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/aws.json) | [1.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/aws.srs) |
| `ip/service/github` | ip | 145 | [4.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/github.json) | [666 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/github.srs) |
| `ip/service/netflix` | ip | 256 | [7.6 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/netflix.json) | [524 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/netflix.srs) |
| `ip/service/twitter` | ip | 14 | [467 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/twitter.json) | [165 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/twitter.srs) |
| `ip/service/steam` | ip | 32 | [965 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/steam.json) | [225 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/steam.srs) |
| `ip/service/meta` | ip | 36 | [1016 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/meta.json) | [268 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/meta.srs) |
| `ip/service/tiktok` | ip | 172 | [4.7 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/tiktok.json) | [584 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/service/tiktok.srs) |
| `ip/operator/telecom` | ip | 3,018 | [79.8 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/telecom.json) | [11.4 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/telecom.srs) |
| `ip/operator/unicom` | ip | 2,505 | [67.0 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/unicom.json) | [9.4 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/unicom.srs) |
| `ip/operator/mobile` | ip | 1,096 | [29.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/mobile.json) | [4.3 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/mobile.srs) |
| `ip/operator/cernet` | ip | 189 | [5.1 KiB](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/cernet.json) | [892 B](https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/ip/operator/cernet.srs) |

## Verification

Every file's SHA-256 is recorded in [`manifest.json`](manifest.json):

```bash
curl -sL https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/manifest.json | jq -r '.rulesets[].files.srs.sha256'
```

## Sources

| Source | Kind | Revision |
| --- | --- | --- |
| `aws_ip` | aws_ipranges | `-` |
| `bgp_v4` | ip2asn | `-` |
| `bgp_v6` | ip2asn | `-` |
| `cernet` | cidr | `65542b2f10bc` |
| `china4` | cidr | `65542b2f10bc` |
| `china46` | cidr | `65542b2f10bc` |
| `china6` | cidr | `65542b2f10bc` |
| `china_domain` | dnsmasq_china | `fbd13c699034` |
| `cloudflare_ip` | cloudflare | `-` |
| `dlc` | dlc | `20261112220449` |
| `gcloud_ip` | google_ipranges | `-` |
| `geo_cn` | dbip_country | `-` |
| `gfwlist` | gfwlist | `d151dea9efaf` |
| `github_ip` | github_meta | `-` |
| `google_ip` | google_ipranges | `-` |
| `iana_v4_special` | iana_special | `-` |
| `iana_v6_special` | iana_special | `-` |
| `mobile` | cidr | `65542b2f10bc` |
| `rir_afrinic` | rir | `-` |
| `rir_apnic` | rir | `-` |
| `rir_arin` | rir | `-` |
| `rir_lacnic` | rir | `-` |
| `rir_ripe` | rir | `-` |
| `telecom` | cidr | `65542b2f10bc` |
| `telegram_ip` | cidr | `-` |
| `unicom` | cidr | `65542b2f10bc` |
