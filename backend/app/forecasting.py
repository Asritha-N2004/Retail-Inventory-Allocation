import math
import numpy as np
from sklearn.ensemble import RandomForestRegressor

MODELS = [
    "moving_average",
    "exponential_smoothing",
    "linear_regression",
    "random_forest",
]


def predict(values, horizon=7, model="exponential_smoothing"):
    y = np.asarray(values, dtype=float)
    if len(y) < 7:
        return max(1, float(y.mean()) if len(y) else 2) * horizon, "fallback"
    y = y[-90:]
    if model == "moving_average":
        daily = float(y[-14:].mean())
    elif model == "linear_regression":
        slope, intercept = np.polyfit(np.arange(len(y)), y, 1)
        daily = float(
            np.maximum(
                0, intercept + slope * np.arange(len(y), len(y) + horizon)
            ).mean()
        )
    elif model == "random_forest":
        x = np.array([[i % 7, i] for i in range(len(y))])
        reg = RandomForestRegressor(
            n_estimators=24, max_depth=5, random_state=42, n_jobs=1
        ).fit(x, y)
        daily = float(
            reg.predict([[i % 7, i] for i in range(len(y), len(y) + horizon)]).mean()
        )
    else:
        daily = float(y[0])
        for value in y[1:]:
            daily = 0.25 * value + 0.75 * daily
    return max(0, daily * horizon), model


def forecast(values, horizon=7, model="exponential_smoothing"):
    estimate, used = predict(values, horizon, model)
    holdout = min(7, len(values) // 3)
    if holdout:
        expected, _ = predict(values[:-holdout], holdout, model)
        actual = sum(values[-holdout:])
        mae = abs(actual - expected) / holdout
        wape = abs(actual - expected) / max(1, actual)
    else:
        mae = 0
        wape = 1
    spread = (
        1.96
        * float(np.std(values[-30:]) if len(values) > 1 else 2)
        * math.sqrt(horizon)
    )
    return dict(
        predicted_demand=round(estimate, 2),
        lower_bound=round(max(0, estimate - spread), 2),
        upper_bound=round(estimate + spread, 2),
        model_name=used,
        confidence_score=round(max(0, 1 - min(wape, 1)), 3),
        metrics={
            "mae": round(mae, 3),
            "wape": round(wape, 3),
            "horizon": horizon,
            "observations": len(values),
        },
    )
