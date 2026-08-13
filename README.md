# AA Upwell Fuel

Fuel planning for Upwell structures in [Alliance Auth](https://gitlab.com/allianceauth/allianceauth).

Answers one question for leadership: **how much fuel do our structures need over
the next N days, and how much of it still has to be bought?**

Alerting is deliberately out of scope — [aa-structures](https://gitlab.com/ErikKalkoken/aa-structures)
already notifies when a structure is running low. This is the planning view that
sits next to it.

## What it shows

* Every Upwell structure you can see, soonest to run dry first
* The burn rate each structure is actually running at, in blocks per day
* Fuel blocks consumed over the planning period (default 30 days)
* What still has to be delivered, after the fuel already in the bay
* Volume in m³ to size the haul, and ISK at average market price
* Subtotals per corporation, and a CSV export for whoever runs the buy order
* Magmatic gas for Metenox drills, and liquid ozone stock for Ansiblexes

## Where the numbers come from

Burn rates are **measured, not modelled**. Each structure's fuel bay contents
divided by the time until its `fuel_expires_at` gives the rate the game is
actually charging it, which already accounts for every hull bonus, rig and
service combination without this app modelling any of them.

That matters, because modelling it is genuinely error-prone. A hull's
`structureServiceRoleBonus` only applies to service modules matching the hull's
role: a Raitaru discounts manufacturing but not a clone bay, an Athanor
discounts reprocessing but not moon drilling. And citadels measurably burn
7.0 blocks/hour for a clone bay where the −25% in dogma predicts 7.5.

The modelled rates in `upwellfuel/fuel/catalog.py` are therefore only a
**fallback**, used for structures that are not currently burning fuel — where the
question is what refuelling one would cost. Those rows are marked as estimates
on the page. The catalog's discount rules were validated against measured rates
across a live 41-structure fleet.

Two figures on the page are estimates by necessity:

* **Magmatic gas** — the Metenox drill's gas rate is not in dogma and gas has no
  expiry date in ESI to measure against, so it uses a configurable constant.
* **Liquid ozone** — shown as stock only. Jump bridges burn ozone per jump
  rather than per hour, so projecting it over a period would be meaningless.

## Requirements

* Alliance Auth >= 4.6
* aa-structures, installed, configured, and syncing assets

This app reads aa-structures' data and stores nothing of its own. It adds no
models, no migrations, no ESI calls and no scheduled tasks — the report is
computed per request and is exactly as fresh as aa-structures' last sync.

## Installation

```bash
pip install aa-upwell-fuel
```

Add to `INSTALLED_APPS` in `local.py`:

```python
INSTALLED_APPS += ["upwellfuel"]
```

There are no migrations to run. Restart Auth and the entry appears in the menu.

### ISK estimates (optional)

The cost column needs market prices, which nothing loads by default. Add
eveuniverse's price task to your schedule:

```python
CELERYBEAT_SCHEDULE["eveuniverse_update_market_prices"] = {
    "task": "eveuniverse.tasks.update_market_prices",
    "schedule": crontab(minute=0, hour=3),
}
```

Until it runs, the page shows the fuel figures and hides the cost column.

## Permissions

This app defines none of its own. It is a different view onto data
aa-structures already owns, so it reuses that app's access model:

| Permission | Effect |
|---|---|
| `structures.basic_access` | Can reach the page |
| `structures.view_corporation_structures` | Sees their corporation's structures |
| `structures.view_alliance_structures` | Sees their alliance's structures |
| `structures.view_all_structures` | Sees everything |

A user with `basic_access` but no viewing permission gets an empty table
explaining why.

## Settings

| Setting | Default | Description |
|---|---|---|
| `UPWELLFUEL_DEFAULT_PERIOD_DAYS` | `30` | Planning period selected on load |
| `UPWELLFUEL_PERIOD_CHOICES` | `[7, 14, 30, 60, 90]` | Options in the period picker |
| `UPWELLFUEL_MAX_PERIOD_DAYS` | `365` | Upper clamp on a period from the URL |
| `UPWELLFUEL_MAGMATIC_GAS_PER_HOUR` | `55.0` | Gas burned per Metenox drill |
| `UPWELLFUEL_DEFAULT_FUEL_BLOCK_TYPE_ID` | `4312` | Block priced when the bay is empty |

## License

MIT
