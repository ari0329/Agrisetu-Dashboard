"""AgriSetu dashboard translations — shared JSON files for UI and API content."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from mongo_store import DEFAULT_LANGUAGE, normalize_language

TRANSLATIONS_DIR = Path(__file__).parent / "static" / "i18n"


@lru_cache(maxsize=16)
def _load(lang: str) -> dict:
    code = normalize_language(lang)
    path = TRANSLATIONS_DIR / f"{code}.json"
    if not path.is_file():
        path = TRANSLATIONS_DIR / f"{DEFAULT_LANGUAGE}.json"
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _lookup(lang: str, key: str) -> Optional[str]:
    parts = key.split(".")
    node: Any = _load(lang)
    for part in parts:
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node if isinstance(node, str) else None


def t(lang: str, key: str, **params: Any) -> str:
    code = normalize_language(lang)
    text = _lookup(code, key)
    if text is None:
        text = _lookup(DEFAULT_LANGUAGE, key)
    text = text or key
    for name, value in params.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def translate_advisory_bundle(bundle: dict, lang: str) -> dict:
    """Translate farmer advisory API payload."""
    if normalize_language(lang) == DEFAULT_LANGUAGE:
        return bundle

    out = copy.deepcopy(bundle)

    irr = out.get("irrigation") or {}
    msg_key = irr.get("message_key")
    if msg_key:
        extras = []
        if irr.get("reservoir_low"):
            extras.append(t(lang, "server.irrigation.reservoir_low"))
        irr["message"] = t(lang, f"server.irrigation.{msg_key}") + "".join(extras)
    irr["action_label"] = t(lang, f"server.irrigation_actions.{irr.get('action', 'monitor')}")
    irr["urgency_label"] = t(lang, f"server.urgency.{irr.get('urgency', 'normal')}")
    out["irrigation"] = irr

    risks = out.get("environmental_risks") or {}
    for risk in risks.get("risks") or []:
        rid = risk.get("id") or ""
        if rid:
            risk["label"] = t(lang, f"server.risks.{rid}.label")
            risk["advice"] = t(lang, f"server.risks.{rid}.advice")
        level = risk.get("level")
        if level:
            risk["level_label"] = t(lang, f"server.levels.{level}")
    if risks.get("overall_level"):
        risks["overall_level_label"] = t(lang, f"server.levels.{risks['overall_level']}")
    out["environmental_risks"] = risks

    nutrient = out.get("nutrient") or {}
    status = nutrient.get("status")
    if status:
        nutrient["message"] = t(
            lang,
            f"server.nutrient.status.{status}",
            ph=f"{nutrient.get('ph', 0):.1f}" if nutrient.get("ph") is not None else "—",
        )
        nutrient["deficiencies"] = [
            t(lang, f"server.nutrient.deficiency.{key}")
            for key in (nutrient.get("deficiency_keys") or [])
        ]
        nutrient["actions"] = [
            t(lang, f"server.nutrient.action.{key}")
            for key in (nutrient.get("action_keys") or [])
        ]
    out["nutrient"] = nutrient

    translated_advisories = []
    irr_msg_key = irr.get("message_key")
    for item in out.get("advisories") or []:
        code = item.get("action_code") or item.get("category") or "ok"
        translated_advisories.append({
            **item,
            "title": t(lang, f"server.advisories.{code}.title"),
            "detail": _translate_advisory_detail(item, lang, irr_msg_key),
        })
    out["advisories"] = translated_advisories

    out["alerts"] = [
        {
            **alert,
            "msg": f"{adv['title']} — {adv['detail']}",
        }
        for alert, adv in zip(out.get("alerts") or [], translated_advisories)
    ]
    return out


def _translate_advisory_detail(item: dict, lang: str, irrigation_msg_key: Optional[str] = None) -> str:
    code = item.get("action_code") or "ok"
    if code in {
        "heat_stress", "flood_risk", "drought", "disease_climate",
        "nutrient_check", "disease_detected", "pest_alert", "leaf_nutrient", "ok",
    }:
        return t(lang, f"server.advisories.{code}.detail")
    if code in {"irrigate_now", "delay_irrigation", "stop_irrigation", "monitor"}:
        key = irrigation_msg_key or code
        return t(lang, f"server.irrigation.{key}")
    return item.get("detail", "")


def translate_vision_result(result: dict, lang: str) -> dict:
    if normalize_language(lang) == DEFAULT_LANGUAGE:
        return result

    out = copy.deepcopy(result)
    profile = out.get("demo_profile")
    if profile:
        out["disease_summary"] = t(lang, f"server.vision.demo.{profile}.disease_summary")
        out["pest_summary"] = t(lang, f"server.vision.demo.{profile}.pest_summary")
        out["nutrient_summary"] = t(lang, f"server.vision.demo.{profile}.nutrient_summary")
        out["recommendations"] = [
            t(lang, f"server.vision.demo.{profile}.recommendation")
        ]
        out["growth_stage"] = t(lang, f"server.vision.growth.{profile if profile != 'healthy' else 'healthy'}")
    else:
        out["disease_summary"] = _translate_vision_summary(out.get("disease_summary"), "disease", lang)
        out["pest_summary"] = _translate_vision_summary(out.get("pest_summary"), "pest", lang)
        out["nutrient_summary"] = _translate_vision_summary(out.get("nutrient_summary"), "nutrient", lang)
        out["recommendations"] = [
            _translate_vision_recommendation(rec, lang)
            for rec in (out.get("recommendations") or [])
        ]
        stage_key = _growth_stage_key(out.get("growth_stage"))
        if stage_key:
            out["growth_stage"] = t(lang, f"server.vision.growth.{stage_key}")

    return out


def _translate_vision_summary(text: str, kind: str, lang: str) -> str:
    if not text:
        return text
    none_key = f"server.vision.none.{kind}"
    if text.startswith("No strong"):
        return t(lang, none_key)
    parts = [part.strip() for part in text.split(";")]
    translated = []
    for part in parts:
        key = _vision_label_key(part)
        translated.append(t(lang, key) if key else part)
    return "; ".join(translated)


def _vision_label_key(label: str) -> Optional[str]:
    mapping = {
        "Leaf blight / brown spot pattern": "server.vision.labels.blight",
        "Necrotic lesions": "server.vision.labels.necrotic",
        "Powdery mildew–like whitening": "server.vision.labels.mildew",
        "Chlorosis with secondary lesions": "server.vision.labels.chlorosis_lesions",
        "Chewing / sucking pest damage pattern": "server.vision.labels.chewing",
        "Dense dark mottling (possible insect frass / holes)": "server.vision.labels.mottling",
        "Scattered feeding scars": "server.vision.labels.scars",
        "General chlorosis — possible N deficiency": "server.vision.labels.n_deficiency",
        "Interveinal yellowing risk — Fe / Mg / Mn": "server.vision.labels.interveinal",
        "Purpling — possible P deficiency": "server.vision.labels.p_deficiency",
    }
    return mapping.get(label)


def _translate_vision_recommendation(text: str, lang: str) -> str:
    mapping = {
        "Isolate affected plants; remove badly infected leaves; consider targeted fungicide.": "server.vision.recommendations.fungicide",
        "Scout early morning for insects; prefer spot-treatment over blanket spraying.": "server.vision.recommendations.pest_scout",
        "Confirm with soil / leaf NPK test before applying fertilizer.": "server.vision.recommendations.npk_test",
        "Leaf appearance is mostly healthy — continue routine monitoring.": "server.vision.recommendations.healthy",
    }
    key = mapping.get(text)
    return t(lang, key) if key else text


def _growth_stage_key(stage: str) -> Optional[str]:
    mapping = {
        "Vegetative / healthy canopy": "healthy",
        "Mid growth": "mid",
        "Stress / senescence signs": "stress",
        "Uncertain — upload a clearer leaf close-up": "uncertain",
    }
    return mapping.get(stage or "")


def translate_prediction(prediction: dict, lang: str) -> dict:
    if normalize_language(lang) == DEFAULT_LANGUAGE:
        return prediction

    out = copy.deepcopy(prediction)
    if out.get("advisory"):
        out["advisory"] = translate_advisory_bundle(out["advisory"], lang)
    if out.get("alerts"):
        out["alerts"] = out["advisory"]["alerts"] if out.get("advisory") else out["alerts"]
    if out.get("explanation"):
        out["explanation"] = t(lang, "server.prediction.explanation_fallback", crop=out.get("recommended_crop", ""))
    return out
