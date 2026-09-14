# Operator Provenance

Every interface profile referenced by a scenario (`interface_profile_id`)
must be documented here with its evidence basis. Do not claim an exact
live-menu replica if the flow was constructed for the benchmark.

## `normalized_v1` (current, default for all v1 scenarios)

| Field | Value |
|---|---|
| Operators | MTN, Telecel, AT |
| Observation date | N/A — not observed from a live system |
| Evidence source | None — constructed for the benchmark |
| Exact / normalized / synthetic | **Synthetic.** Menu structure (4 home items → Send Money submenu with same/cross-operator choice → phone entry → amount entry → confirmation → result) is uniform across all three operators by design; only labels and ordering differ (e.g. "Send Money" vs "Transfer", "MTN Wallet" vs "Telecel Account"). This is deliberate: `normalized_v1` is "a scientifically controlled profile where providers differ in menu structure/labels but expose equivalent capabilities" (spec §33.1) — chosen specifically so results aren't confounded by unrelated navigation-depth differences between providers, and so the suite doesn't depend on frequently-changing commercial menus. |
| Screens simplified | All of them, by construction — there is no live reference. Fee/limit disclosure format, transaction history format, and status-check wording are original to this benchmark. |
| Defined in | `config/operators/{mtn,telecel,at}.yaml`, rendered by `momobench.envs.ussd.base.BaseUSSDEnv`. |

## `ghana_ussd_2026q3` (not yet created)

Reserved identifier for a future **frozen-realistic** profile (spec §33.2):
real operator USSD flows manually verified against live menus as of a
specific date, then frozen and versioned. Do not populate this profile from
memory or by guessing — it must be built from directly observed evidence,
dated, and cited here before any scenario references it. Fee/limit policies
under this profile, if ever added, must likewise be labeled either
"synthetic and frozen" or "empirically verified as-of &lt;date&gt; and frozen"
(spec §17) — never fetched live during an experiment (spec §117).

## Fee and limit policies

`config/policies/fee_synthetic_v1.yaml` and
`config/policies/limits_synthetic_v1.yaml` are both **synthetic and
frozen**. They are benchmark policies for producing controlled,
reproducible insufficient-funds and limit-violation scenarios — not a claim
about real MTN/Telecel/AT fee schedules or transaction limits.
