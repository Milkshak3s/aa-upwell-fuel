# Changelog

All notable changes to this project are documented here.

## [0.1.1] - 2026-08-17

* Sortable columns: click any heading to reorder the table, with the sort
  carried into the CSV export

## [0.1.0] - 2026-08-12

Initial release.

* Fuel projection page for Upwell structures over a configurable period,
  defaulting to 30 days
* Burn rates measured from each structure's own fuel bay and expiry date,
  falling back to modelled rates from fitted service modules when a structure
  is not burning fuel
* Gross burn, current fuel, and remaining shortfall per structure, with
  per-corporation subtotals
* Volume and ISK costing, the latter using eveuniverse market prices when loaded
* Magmatic gas projection for Metenox drills and liquid ozone stock for Ansiblexes
* Corporation and shortfall filters, and CSV export
* Reuses aa-structures' permissions; adds no models or migrations
