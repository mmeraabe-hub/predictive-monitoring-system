
RISK_THRESHOLDS = {
    "Quarterly": {
        "on_track": 0.90,
        "at_risk": 0.70,
    },

    "Annual": {
        "on_track": 0.95,
        "at_risk": 0.80,
    },

    "LoP": {
        "on_track": 1.00,
        "at_risk": 0.85,
    }
}


def classify_risk(ratio, assessment_level):

    if ratio is None:
        return "Unknown"

    thresholds = RISK_THRESHOLDS[assessment_level]

    if ratio >= thresholds["on_track"]:
        return "On Track"

    elif ratio >= thresholds["at_risk"]:
        return "At Risk"

    else:
        return "Off Track"


def get_thresholds(assessment_level):
    return RISK_THRESHOLDS[assessment_level]
