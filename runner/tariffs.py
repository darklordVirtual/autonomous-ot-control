"""Named grid tariffs the runs can be priced with.

Every twin fixture carries a declared reference tariff (`plant.grid_tariff`,
ASSUMPTION D-13). A run can replace it with a named tariff from this registry
so that a savings figure can be priced on a published tariff sheet, with the
sheet's URL and validity carried into the output.

    python -m runner.areas --tariff elvia-stor-naering-lavspent-2026-01 ...
    python -m runner.pilot --tariff elvia-stor-naering-lavspent-2026-01 ...

The twin charges the power part on the month's highest hourly mean kW
(`twin/model.py::_grid_tariff`), which is how the published sheets define
"anleggets høyeste effektuttak pr kalendermåned" for hourly-metered sites.
Taxes (elavgift, VAT) are never included; the fixed part (fastledd) is
reported as a constant that no strategy can change.

The registry is data, transcribed by hand from the sheets named in
`source`. A transcription error is a defect of this file, not of the twin;
the `transcribed` date says when it was read.
"""
from __future__ import annotations

import copy
from typing import Any

TARIFFS: dict[str, dict[str, Any]] = {
    "reference-generic": {
        "tariff_id": "reference-generic",
        "name": "Generic reference business tariff (ASSUMPTION D-13)",
        "energy_nok_per_kwh": 0.06,
        "power_nok_per_kw_month": {"winter": 110.0, "summer": 45.0},
        "winter_months": [1, 2, 3, 11, 12],
        "fixed_nok_per_month": 0.0,
        "source": {"kind": "assumption",
                   "note": "The fixtures' declared reference tariff; not any grid company's published tariff."},
    },
    "elvia-stor-naering-lavspent-2026-07": {
        "tariff_id": "elvia-stor-naering-lavspent-2026-07",
        "name": "Elvia, stor næring effekt, lavspent uttak, from 2026-07-01",
        "energy_nok_per_kwh": 0.05,
        "power_nok_per_kw_month": {"winter": 111.0, "summer": 46.0},
        "winter_months": [10, 11, 12, 1, 2, 3],
        "fixed_nok_per_month": 500.0,
        "source": {
            "kind": "published_tariff_sheet",
            "publisher": "Elvia AS",
            "sheet": "Tariffblad 3.0 Stor næring effekt lavspent, gyldig fra 01.07.2026",
            "url": "https://www.elvia.no/siteassets/dokumenter/priser/2026/1-juli-2026/tariffblad_3_0_stor-naring_effekt_lavspent_20260701.pdf",
            "applies_to": "low-voltage customers with ordinary transfer and more than 100 000 kWh a year",
            "power_definition": "Effektleddet avregnes etter anleggets høyeste effektuttak pr kalendermåned",
            "excluded": "elavgift, VAT, reactive-power charge (21/50 kr/kVAr/mnd summer/winter; power factor assumed >= 0.95)",
            "transcribed": "2026-10-28",
            "note": "Energiledd 5,00 øre/kWh (one rate); effektledd 111 kr/kW/mnd Oct-Mar and 46 kr/kW/mnd Apr-Sep; "
                    "fastledd 500 kr/mnd (lavspent uttak; 1 225 kr/mnd for fellesmåling), Enova charge included. "
                    "The sheet in force on 2026-10-28. Transcribed by hand; verify against the sheet before contractual use.",
        },
    },
    "elvia-stor-naering-lavspent-2026-01": {
        "tariff_id": "elvia-stor-naering-lavspent-2026-01",
        "name": "Elvia, stor næring effekt, lavspent uttak, from 2026-01-01",
        "energy_nok_per_kwh": 0.05,
        "power_nok_per_kw_month": {"winter": 74.0, "summer": 31.0},
        "winter_months": [10, 11, 12, 1, 2, 3],
        "fixed_nok_per_month": 500.0,
        "source": {
            "kind": "published_tariff_sheet",
            "publisher": "Elvia AS",
            "sheet": "Tariffblad 3.0 Stor næring effekt lavspent, gyldig fra 01.01.2026",
            "url": "https://www.elvia.no/siteassets/dokumenter/priser/2026/tariffblad_3_0_stor-naring_effekt_lavspent_20260101.pdf",
            "applies_to": "low-voltage customers with ordinary transfer and more than 100 000 kWh a year",
            "power_definition": "Effektleddet avregnes etter anleggets høyeste effektuttak pr kalendermåned",
            "excluded": "elavgift, VAT, reactive-power charge (power factor assumed >= 0.95)",
            "transcribed": "2026-10-28",
            "note": "Energiledd 5,00 øre/kWh (one rate); effektledd 74 kr/kW/mnd Oct-Mar and 31 kr/kW/mnd Apr-Sep; "
                    "fastledd 500 kr/mnd (lavspent uttak; 1 225 kr/mnd for fellesmåling), Enova charge included. "
                    "Superseded by the 2026-07-01 sheet; kept as the first half of 2026. "
                    "Transcribed from the sheet by hand; verify against the sheet before contractual use.",
        },
    },
}


def get_tariff(tariff_id: str) -> dict[str, Any]:
    if tariff_id not in TARIFFS:
        raise KeyError(f"unknown tariff {tariff_id!r}; known: {', '.join(sorted(TARIFFS))}")
    return copy.deepcopy(TARIFFS[tariff_id])


def apply_tariff(config: dict[str, Any], tariff_id: str | None) -> dict[str, Any]:
    """Return a copy of a twin config priced with the named tariff (None: unchanged)."""
    cfg = copy.deepcopy(config)
    if tariff_id:
        t = get_tariff(tariff_id)
        cfg.setdefault("plant", {})["grid_tariff"] = {
            "tariff_id": t["tariff_id"], "energy_nok_per_kwh": t["energy_nok_per_kwh"],
            "power_nok_per_kw_month": t["power_nok_per_kw_month"], "winter_months": t["winter_months"],
            "fixed_nok_per_month": t["fixed_nok_per_month"], "comment": f"{t['name']} (runner.tariffs)",
        }
    return cfg


def describe(config: dict[str, Any]) -> dict[str, Any]:
    """The tariff a config is priced with, with its provenance when it is a registry tariff."""
    gt = config.get("plant", {}).get("grid_tariff") or {}
    tid = gt.get("tariff_id")
    if tid and tid in TARIFFS:
        return get_tariff(tid)
    return {"tariff_id": tid or "fixture-declared", "name": gt.get("comment", "fixture-declared reference tariff"),
            "energy_nok_per_kwh": gt.get("energy_nok_per_kwh"), "power_nok_per_kw_month": gt.get("power_nok_per_kw_month"),
            "winter_months": gt.get("winter_months"), "fixed_nok_per_month": gt.get("fixed_nok_per_month", 0.0),
            "source": {"kind": "assumption"}}
