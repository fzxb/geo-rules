# geo

sing-box rule-sets (`domain` / `ip`) built from primary upstream sources and published as
JSON and SRS on the `rule-set` branch, which is rebuilt daily. Build code and
configuration live on `main`; artifacts are served from
`https://raw.githubusercontent.com/fzxb/geo-rules/rule-set/<ruleset>.srs`.

Current build: **46 rule-sets**, roughly 150k domain entries and 34k IP prefixes (~5 MiB);
counts are per rule-set, so layers overlap.

## Data sources

| Source | Feeds | License |
| --- | --- | --- |
| [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) | `domain/cn` `non-cn` `private` `ads` `privacy` `service/*` | MIT |
| [dnsmasq-china-list](https://github.com/felixonmars/dnsmasq-china-list) | `domain/cn` | WTFPL v2 |
| [gfwlist/gfwlist](https://github.com/gfwlist/gfwlist) | `domain/gfw` `ip/gfw` | LGPL-2.1 |
| [DB-IP Lite Country](https://db-ip.com/db/download/ip-to-country-lite) | `ip/cn*` (geolocation) | CC BY 4.0 |
| APNIC / ARIN / RIPE NCC / LACNIC / AFRINIC delegated stats | `ip/cn*` (registry) | public registry data (RIR terms) |
| [gaoyifan/china-operator-ip](https://github.com/gaoyifan/china-operator-ip) | `ip/cn*` `ip/operator/*` (BGP) | MIT |
| [iptoasn.com](https://iptoasn.com) | `ip/service/{netflix,twitter,steam,meta,tiktok}` (BGP) | PDDL v1.0 |
| IANA special-purpose registries | `ip/private` | public data |
| Vendor endpoints (Telegram, Cloudflare, Google, GCloud, AWS, GitHub) | `ip/service/*` | public endpoints (vendor terms) |

`domain/cn` means domestic DNS/NS presence, not "Chinese company" or "hosted in
China"; `ip/cn` is the union of geolocation, BGP and RIR registry data.

## License

Data remains under its upstream licenses (see the table above). DB-IP Lite is
CC BY 4.0 and requires attribution to DB-IP.com; RIR delegated stats and vendor
endpoint data are subject to their own terms. Code is [MIT](LICENSE).
