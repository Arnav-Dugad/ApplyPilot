# Profile schema

`profile_facts` is the source of candidate truth.

| Field | Meaning |
|---|---|
| `category`, `fact_key` | Stable semantic identity |
| `country_code` | Optional exact country scope; required for authorization/sponsorship |
| `value_json` | Typed value; may be null when unknown |
| `status` | `VERIFIED`, `UNVERIFIED`, `UNKNOWN`, or `EXPIRED` |
| `source` | Human-readable provenance |
| `date_added`, `last_confirmed`, `expires_at` | Lifecycle metadata |
| `notes` | User context, never an inference source |
| `revision` | Monotonic change counter |

Fact changes invalidate dependent Answer Vault entries and applications through `fact_dependencies`. A value imported from a CV starts `UNVERIFIED`; only explicit user review can make it `VERIFIED`.

