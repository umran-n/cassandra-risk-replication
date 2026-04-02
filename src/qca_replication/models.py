from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

from .clients import fetch_yahoo_chart
from .utils import clamp, correlation, mean, parse_date, percentile, safe_div


def _transpose(matrix: list[list[float]]) -> list[list[float]]:
    return [list(column) for column in zip(*matrix)]


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    bt = _transpose(b)
    return [[sum(x * y for x, y in zip(row, col)) for col in bt] for row in a]


def _matvec(a: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(x * y for x, y in zip(row, vector)) for row in a]


def _invert_matrix(matrix: list[list[float]]) -> list[list[float]] | None:
    n = len(matrix)
    augmented = []
    for row_idx, row in enumerate(matrix):
        augmented.append(row[:] + [1.0 if row_idx == col_idx else 0.0 for col_idx in range(n)])
    for col in range(n):
        pivot_row = max(range(col, n), key=lambda idx: abs(augmented[idx][col]))
        pivot = augmented[pivot_row][col]
        if abs(pivot) < 1e-12:
            return None
        augmented[col], augmented[pivot_row] = augmented[pivot_row], augmented[col]
        pivot = augmented[col][col]
        augmented[col] = [value / pivot for value in augmented[col]]
        for row_idx in range(n):
            if row_idx == col:
                continue
            factor = augmented[row_idx][col]
            augmented[row_idx] = [
                current - factor * pivot_value
                for current, pivot_value in zip(augmented[row_idx], augmented[col])
            ]
    return [row[n:] for row in augmented]


def _ols_fit(x: list[list[float]], y: list[float], clusters: list[str] | None = None) -> dict | None:
    if not x or len(x) != len(y):
        return None
    xt = _transpose(x)
    xtx = _matmul(xt, x)
    for idx in range(len(xtx)):
        xtx[idx][idx] += 1e-9
    inv = _invert_matrix(xtx)
    if inv is None:
        return None
    xty = [sum(value * target for value, target in zip(column, y)) for column in xt]
    beta = _matvec(inv, xty)
    fitted = [sum(coef * value for coef, value in zip(beta, row)) for row in x]
    residuals = [target - estimate for target, estimate in zip(y, fitted)]
    sse = sum(value * value for value in residuals)
    mean_y = mean(y)
    tss = sum((value - mean_y) ** 2 for value in y)
    r2 = 0.0 if tss == 0 else 1.0 - (sse / tss)
    dof = max(len(y) - len(beta), 1)
    sigma2 = sse / dof
    stderr = [math.sqrt(max(inv[idx][idx] * sigma2, 0.0)) for idx in range(len(beta))]

    cluster_stderr = stderr[:]
    if clusters:
        unique = sorted(set(clusters))
        if len(unique) > 1 and len(y) > len(beta):
            meat = [[0.0 for _ in beta] for _ in beta]
            for cluster in unique:
                indices = [idx for idx, item in enumerate(clusters) if item == cluster]
                score = [0.0 for _ in beta]
                for idx in indices:
                    for col_idx, value in enumerate(x[idx]):
                        score[col_idx] += value * residuals[idx]
                for row_idx in range(len(beta)):
                    for col_idx in range(len(beta)):
                        meat[row_idx][col_idx] += score[row_idx] * score[col_idx]
            vcov = _matmul(_matmul(inv, meat), inv)
            factor = (len(unique) / max(len(unique) - 1, 1)) * ((len(y) - 1) / max(len(y) - len(beta), 1))
            cluster_stderr = [math.sqrt(max(vcov[idx][idx] * factor, 0.0)) for idx in range(len(beta))]
    return {
        "beta": beta,
        "stderr": stderr,
        "cluster_stderr": cluster_stderr,
        "fitted": fitted,
        "residuals": residuals,
        "r2": r2,
        "n_obs": len(y),
        "n_params": len(beta),
    }


def _wild_cluster_bootstrap(
    x: list[list[float]],
    y: list[float],
    clusters: list[str],
    coefficient_index: int,
    resamples: int,
    seed: int,
) -> tuple[float | None, float | None, float | None]:
    fit = _ols_fit(x, y, clusters=clusters)
    if fit is None:
        return None, None, None
    rng = random.Random(seed)
    unique_clusters = sorted(set(clusters))
    draws: list[float] = []
    for _ in range(resamples):
        weights = {cluster: rng.choice([-1.0, 1.0]) for cluster in unique_clusters}
        y_star = [fit["fitted"][idx] + fit["residuals"][idx] * weights[clusters[idx]] for idx in range(len(y))]
        trial = _ols_fit(x, y_star, clusters=clusters)
        if trial is not None:
            draws.append(trial["beta"][coefficient_index])
    if not draws:
        return None, None, None
    draws.sort()
    ci_low = percentile(draws, 0.025)
    ci_high = percentile(draws, 0.975)
    p_value = 2.0 * min(
        sum(value >= 0 for value in draws) / len(draws),
        sum(value <= 0 for value in draws) / len(draws),
    )
    return ci_low, ci_high, clamp(p_value, 0.0, 1.0)


def _rmse(actual: list[float], predicted: list[float]) -> float:
    if not actual:
        return 0.0
    return math.sqrt(mean([(a - b) ** 2 for a, b in zip(actual, predicted)]))


def _mae(actual: list[float], predicted: list[float]) -> float:
    if not actual:
        return 0.0
    return mean([abs(a - b) for a, b in zip(actual, predicted)])


def _directional_accuracy(actual: list[float], predicted: list[float]) -> float:
    if not actual:
        return 0.0
    hits = 0
    for observed, forecast in zip(actual, predicted):
        if observed == 0 and forecast == 0:
            hits += 1
        elif observed != 0 and forecast != 0 and (observed > 0) == (forecast > 0):
            hits += 1
    return hits / len(actual)


def _linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0, 0.0, 0.0
    x_mean = mean(xs)
    y_mean = mean(ys)
    denominator = sum((value - x_mean) ** 2 for value in xs)
    if denominator == 0:
        return y_mean, 0.0, 0.0
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    intercept = y_mean - slope * x_mean
    fitted = [intercept + slope * x for x in xs]
    residual = sum((y - fit) ** 2 for y, fit in zip(ys, fitted))
    total = sum((y - y_mean) ** 2 for y in ys)
    r2 = 0.0 if total == 0 else 1.0 - residual / total
    return intercept, slope, r2


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted(set(values))


@dataclass
class TreeNode:
    feature_idx: int | None = None
    threshold: float | None = None
    left: "TreeNode | None" = None
    right: "TreeNode | None" = None
    prediction: float = 0.0


class RandomForestRegressorLite:
    def __init__(self, n_trees: int = 50, max_depth: int = 4, min_samples_split: int = 4, seed: int = 0) -> None:
        self.n_trees = n_trees
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.seed = seed
        self.trees: list[TreeNode] = []

    def fit(self, x: list[list[float]], y: list[float]) -> None:
        rng = random.Random(self.seed)
        self.trees = []
        for _ in range(self.n_trees):
            indices = [rng.randrange(len(x)) for _ in range(len(x))]
            sample_x = [x[idx] for idx in indices]
            sample_y = [y[idx] for idx in indices]
            self.trees.append(self._build_tree(sample_x, sample_y, depth=0, rng=rng))

    def predict(self, x: list[list[float]]) -> list[float]:
        if not self.trees:
            return [0.0 for _ in x]
        return [mean([self._predict_tree(tree, row) for tree in self.trees]) for row in x]

    def _build_tree(self, x: list[list[float]], y: list[float], depth: int, rng: random.Random) -> TreeNode:
        node = TreeNode(prediction=mean(y))
        if depth >= self.max_depth or len(x) < self.min_samples_split or len(set(y)) == 1:
            return node
        n_features = len(x[0])
        feature_candidates = rng.sample(range(n_features), k=max(1, int(math.sqrt(n_features))))
        best_feature = None
        best_threshold = None
        best_score = math.inf
        best_split = None
        for feature_idx in feature_candidates:
            values = sorted({row[feature_idx] for row in x})
            if len(values) < 2:
                continue
            thresholds = [(left + right) / 2.0 for left, right in zip(values, values[1:])]
            if len(thresholds) > 8:
                step = max(1, len(thresholds) // 8)
                thresholds = thresholds[::step]
            for threshold in thresholds:
                left_indices = [idx for idx, row in enumerate(x) if row[feature_idx] <= threshold]
                right_indices = [idx for idx, row in enumerate(x) if row[feature_idx] > threshold]
                if not left_indices or not right_indices:
                    continue
                left_y = [y[idx] for idx in left_indices]
                right_y = [y[idx] for idx in right_indices]
                score = sum((value - mean(left_y)) ** 2 for value in left_y) + sum((value - mean(right_y)) ** 2 for value in right_y)
                if score < best_score:
                    best_score = score
                    best_feature = feature_idx
                    best_threshold = threshold
                    best_split = (left_indices, right_indices)
        if best_split is None or best_feature is None or best_threshold is None:
            return node
        left_indices, right_indices = best_split
        node.feature_idx = best_feature
        node.threshold = best_threshold
        node.left = self._build_tree([x[idx] for idx in left_indices], [y[idx] for idx in left_indices], depth + 1, rng)
        node.right = self._build_tree([x[idx] for idx in right_indices], [y[idx] for idx in right_indices], depth + 1, rng)
        return node

    def _predict_tree(self, node: TreeNode, row: list[float]) -> float:
        if node.feature_idx is None or node.threshold is None or node.left is None or node.right is None:
            return node.prediction
        if row[node.feature_idx] <= node.threshold:
            return self._predict_tree(node.left, row)
        return self._predict_tree(node.right, row)


def fit_coherence_curve(horizons: list[int], cars: list[float], config: dict) -> dict | None:
    rows = [{"horizon_days": horizon, "car": car} for horizon, car in zip(horizons, cars)]
    return _fit_coherence_event("synthetic", rows, config)


def spectral_entropy_from_matrix(matrix: list[list[float]]) -> tuple[list[float], float, float]:
    eigenvalues = _jacobi_eigenvalues(matrix)
    total = sum(eigenvalues)
    probabilities = [safe_div(value, total) for value in eigenvalues if value > 0]
    entropy = -sum(probability * math.log(probability, 2) for probability in probabilities if probability > 0)
    return probabilities, entropy, 2.0 ** entropy


def _build_primary_design(rows: list[dict]) -> tuple[list[list[float]], list[float], list[str], list[str]]:
    firms = _sorted_unique([row["ticker"] for row in rows])
    x: list[list[float]] = []
    y: list[float] = []
    clusters: list[str] = []
    columns = ["intercept", "qii"]
    columns.extend([f"firm_{ticker}" for ticker in firms[1:]])
    columns.extend(["market_state_20d", "vix_t1"])
    for row in rows:
        vector = [1.0, float(row["qii"])]
        vector.extend([1.0 if row["ticker"] == ticker else 0.0 for ticker in firms[1:]])
        vector.extend([float(row["market_state_20d"]), float(row["vix_t1"])])
        x.append(vector)
        y.append(float(row["car_0_5"]))
        clusters.append(row["ticker"])
    return x, y, columns, clusters


def _build_simple_design(rows: list[dict], features: list[str]) -> tuple[list[list[float]], list[float], list[str], list[str]]:
    x: list[list[float]] = []
    y: list[float] = []
    clusters: list[str] = []
    columns = ["intercept"] + features
    for row in rows:
        if any(row.get(feature) is None for feature in features):
            continue
        vector = [1.0] + [float(row[feature]) for feature in features]
        x.append(vector)
        y.append(float(row["car_0_5"]))
        clusters.append(row["ticker"])
    return x, y, columns, clusters


def _fit_regression_model(rows: list[dict], model_name: str, features: list[str], include_firms: bool, config: dict) -> dict:
    if include_firms:
        x, y, columns, clusters = _build_primary_design(rows)
    else:
        x, y, columns, clusters = _build_simple_design(rows, features)
    fit = _ols_fit(x, y, clusters=clusters)
    if fit is None:
        return {"model": model_name, "status": "failed"}
    ci_low = ci_high = p_value = None
    if include_firms:
        ci_low, ci_high, p_value = _wild_cluster_bootstrap(
            x,
            y,
            clusters,
            coefficient_index=1,
            resamples=int(config["regression"]["bootstrap_resamples"]),
            seed=int(config["regression"]["seed"]),
        )
    coefficient_rows = []
    for idx, column in enumerate(columns):
        coefficient_rows.append(
            {
                "model": model_name,
                "term": column,
                "coefficient": fit["beta"][idx],
                "cluster_stderr": fit["cluster_stderr"][idx],
                "data_tier": "public_proxy",
            }
        )
    return {
        "model": model_name,
        "status": "ok",
        "r2": fit["r2"],
        "n_obs": fit["n_obs"],
        "coefficients": coefficient_rows,
        "qii_ci_low": ci_low,
        "qii_ci_high": ci_high,
        "qii_p_value": p_value,
        "predictions": fit["fitted"],
    }


def _split_rows(rows: list[dict], start: str, end: str) -> list[dict]:
    return [row for row in rows if start <= row["announcement_date"] <= end]


def _fit_coherence_event(event_id: str, event_rows: list[dict], config: dict) -> dict | None:
    available = {int(row["horizon_days"]): float(row["car"]) for row in event_rows if row["car"] is not None}
    if not available or max(available) < int(config["coherence"]["min_post_days"]):
        return None
    x = sorted(available)
    y = [available[horizon] for horizon in x]
    best = None
    tau = float(config["coherence"]["tau_min"])
    tau_max = float(config["coherence"]["tau_max"])
    step = float(config["coherence"]["tau_step"])
    while tau <= tau_max + 1e-9:
        z = [math.exp(-horizon / tau) for horizon in x]
        intercept, slope, _ = _linear_fit(z, y)
        car_inf = intercept
        car_0 = intercept + slope
        if not (-0.5 <= car_0 <= 0.5 and -0.3 <= car_inf <= 0.3):
            tau += step
            continue
        fitted = [car_inf + (car_0 - car_inf) * math.exp(-horizon / tau) for horizon in x]
        sse = sum((obs - fit) ** 2 for obs, fit in zip(y, fitted))
        total = sum((obs - mean(y)) ** 2 for obs in y)
        r2 = 0.0 if total == 0 else 1.0 - sse / total
        if best is None or sse < best["sse"]:
            best = {
                "event_id": event_id,
                "tau": tau,
                "car_0": car_0,
                "car_inf": car_inf,
                "r2": r2,
                "sse": sse,
                "data_tier": "public_proxy",
            }
        tau += step
    if best is None or best["r2"] < float(config["coherence"]["min_fit_r2"]):
        return None
    return best


def _fit_decay_law(coherence_rows: list[dict]) -> dict:
    qualified = [row for row in coherence_rows if row.get("qualified")]
    if len(qualified) < 2:
        return {
            "tau_max": None,
            "alpha": None,
            "r2": None,
            "qualified_events": len(qualified),
            "data_tier": "public_proxy",
        }
    xs = [float(row["theta_degrees"]) for row in qualified]
    ys = [math.log(max(float(row["tau"]), 1e-6)) for row in qualified]
    intercept, slope, r2 = _linear_fit(xs, ys)
    return {
        "tau_max": math.exp(intercept),
        "alpha": -slope,
        "r2": r2,
        "qualified_events": len(qualified),
        "data_tier": "public_proxy",
    }


def _jacobi_eigenvalues(matrix: list[list[float]]) -> list[float]:
    size = len(matrix)
    a = [row[:] for row in matrix]
    for _ in range(100):
        p = q = 0
        max_value = 0.0
        for row_idx in range(size):
            for col_idx in range(row_idx + 1, size):
                value = abs(a[row_idx][col_idx])
                if value > max_value:
                    max_value = value
                    p, q = row_idx, col_idx
        if max_value < 1e-10:
            break
        angle = 0.5 * math.atan2(2.0 * a[p][q], a[q][q] - a[p][p])
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        app = a[p][p]
        aqq = a[q][q]
        apq = a[p][q]
        a[p][p] = cos_angle * cos_angle * app - 2.0 * sin_angle * cos_angle * apq + sin_angle * sin_angle * aqq
        a[q][q] = sin_angle * sin_angle * app + 2.0 * sin_angle * cos_angle * apq + cos_angle * cos_angle * aqq
        a[p][q] = 0.0
        a[q][p] = 0.0
        for idx in range(size):
            if idx in {p, q}:
                continue
            aip = a[idx][p]
            aiq = a[idx][q]
            a[idx][p] = cos_angle * aip - sin_angle * aiq
            a[p][idx] = a[idx][p]
            a[idx][q] = sin_angle * aip + cos_angle * aiq
            a[q][idx] = a[idx][q]
    return sorted([max(a[idx][idx], 0.0) for idx in range(size)], reverse=True)


def _zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    mu = mean(values)
    variance = mean([(value - mu) ** 2 for value in values])
    sigma = math.sqrt(max(variance, 0.0))
    if sigma == 0:
        return [0.0 for _ in values]
    return [(value - mu) / sigma for value in values]


def _compute_entanglement(feature_rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in feature_rows:
        grouped.setdefault(row["ticker"], []).append(row)
    rows: list[dict] = []
    for ticker, items in sorted(grouped.items()):
        if len(items) < 2:
            rows.append(
                {
                    "ticker": ticker,
                    "event_count": len(items),
                    "entropy_bits": None,
                    "d_eff": None,
                    "risk_tier": "insufficient_data",
                    "data_tier": "public_proxy",
                }
            )
            continue
        particle = _zscore([float(item["particle_amplitude"] or 0.0) for item in items])
        wave = _zscore([float(item["wave_amplitude"] or 0.0) for item in items])
        auth = _zscore([float(item["authorization_intensity"] or 0.0) for item in items])
        skew = _zscore([1.0 - float(item["s_options"] or 0.5) for item in items])
        macro = _zscore([float(item["vix_t1"] or 0.0) - 100.0 * float(item["market_state_20d"] or 0.0) for item in items])
        drivers = [particle, wave, auth, skew, macro]
        matrix = [[0.0 for _ in drivers] for _ in drivers]
        for row_idx, series_a in enumerate(drivers):
            for col_idx, series_b in enumerate(drivers):
                matrix[row_idx][col_idx] = correlation(series_a, series_b)
            matrix[row_idx][row_idx] = 1.0
        eigenvalues = _jacobi_eigenvalues(matrix)
        total = sum(eigenvalues)
        probabilities = [safe_div(value, total) for value in eigenvalues if value > 0]
        entropy = -sum(probability * math.log(probability, 2) for probability in probabilities if probability > 0)
        d_eff = 2.0 ** entropy
        if d_eff < 2.75:
            tier = "low"
        elif d_eff < 3.30:
            tier = "moderate"
        elif d_eff < 4.0:
            tier = "elevated"
        else:
            tier = "high"
        rows.append(
            {
                "ticker": ticker,
                "event_count": len(items),
                "entropy_bits": entropy,
                "d_eff": d_eff,
                "risk_tier": tier,
                "eigenvalues": probabilities,
                "data_tier": "public_proxy",
            }
        )
    rows.sort(key=lambda item: (item["d_eff"] is None, -(item["d_eff"] or 0.0), item["ticker"]))
    return rows


def _assign_coherence_regimes(coherence_rows: list[dict], entanglement_rows: list[dict]) -> list[dict]:
    d_eff_lookup = {row["ticker"]: row["d_eff"] for row in entanglement_rows if row["d_eff"] is not None}
    rows: list[dict] = []
    for row in coherence_rows:
        if not row.get("qualified"):
            continue
        d_eff = d_eff_lookup.get(row["ticker"])
        if d_eff is None:
            continue
        theta = float(row["theta_degrees"])
        if theta < 45:
            phase_band = "0_45"
            regime = "A+" if d_eff < 3.0 else "A" if d_eff < 4.0 else "A-"
        elif theta < 90:
            phase_band = "45_90"
            regime = "B+" if d_eff < 3.0 else "B" if d_eff < 4.0 else "B-"
        else:
            phase_band = "90_180"
            regime = "C+" if d_eff < 3.0 else "C" if d_eff < 4.0 else "D"
        rows.append(
            {
                "event_id": row["event_id"],
                "ticker": row["ticker"],
                "theta_degrees": theta,
                "tau": row["tau"],
                "d_eff": d_eff,
                "phase_band": phase_band,
                "regime": regime,
                "t90_days": 2.303 * float(row["tau"]),
                "data_tier": "public_proxy",
            }
        )
    return rows


def _build_tail_screen(feature_rows: list[dict], entanglement_rows: list[dict], threshold: float) -> list[dict]:
    d_eff_lookup = {row["ticker"]: row for row in entanglement_rows}
    tier_hits: dict[str, list[int]] = {}
    for row in feature_rows:
        ent = d_eff_lookup.get(row["ticker"])
        tier = ent["risk_tier"] if ent else "unknown"
        severe = 1 if row.get("post_event_drawdown_50d") is not None and float(row["post_event_drawdown_50d"]) <= threshold else 0
        tier_hits.setdefault(tier, []).append(severe)
    rows: list[dict] = []
    for row in feature_rows:
        ent = d_eff_lookup.get(row["ticker"])
        if ent is None:
            continue
        tier = ent["risk_tier"]
        rate = mean(tier_hits.get(tier, []))
        rows.append(
            {
                "event_id": row["event_id"],
                "ticker": row["ticker"],
                "post_event_drawdown_50d": row["post_event_drawdown_50d"],
                "major_drawdown_flag": row.get("post_event_drawdown_50d") is not None and float(row["post_event_drawdown_50d"]) <= threshold,
                "d_eff": ent["d_eff"],
                "risk_tier": tier,
                "screen_probability": rate,
                "data_tier": "public_proxy",
            }
        )
    rows.sort(key=lambda item: (item["post_event_drawdown_50d"] is None, item["post_event_drawdown_50d"] or 0.0))
    return rows


def _build_contagion_edges(config: dict, raw_dir: Path, refresh: bool = False, fixture_data: dict | None = None) -> list[dict]:
    market_symbol = config["market_data"]["market_symbol"]
    price_payloads: dict[str, dict] = {}
    symbols = [firm["ticker"] for firm in config["firms"]] + [market_symbol]
    for symbol in symbols:
        if fixture_data and symbol in fixture_data.get("price_history", {}):
            price_payloads[symbol] = fixture_data["price_history"][symbol]
        else:
            try:
                price_payloads[symbol] = fetch_yahoo_chart(
                    symbol,
                    config["sample"]["lookback_start"],
                    config["sample"]["end"],
                    raw_dir,
                    config["market_data"]["chart_url_template"],
                    refresh=refresh,
                )
            except Exception:
                continue
    returns: dict[str, dict[str, float]] = {}
    for symbol, payload in price_payloads.items():
        series = {row["date"]: float(row["adjclose"]) for row in payload["rows"]}
        ordered = sorted(series)
        returns[symbol] = {}
        previous = None
        for day in ordered:
            close = series[day]
            returns[symbol][day] = 0.0 if previous is None else (close / previous) - 1.0
            previous = close
    if market_symbol not in returns:
        return []
    market_returns = returns[market_symbol]
    threshold = float(config["entanglement"]["contagion_threshold"])
    edges: list[dict] = []
    tickers = [firm["ticker"] for firm in config["firms"] if firm["ticker"] in returns]
    for idx, left in enumerate(tickers):
        for right in tickers[idx + 1 :]:
            common_days = sorted(set(returns[left]) & set(returns[right]) & set(market_returns))
            if len(common_days) < 60:
                continue
            left_excess = [returns[left][day] - market_returns[day] for day in common_days]
            right_excess = [returns[right][day] - market_returns[day] for day in common_days]
            xi = correlation(left_excess, right_excess)
            if xi <= threshold:
                continue
            edges.append(
                {
                    "left_ticker": left,
                    "right_ticker": right,
                    "xi_ij": xi,
                    "observations": len(common_days),
                    "data_tier": "public_proxy",
                }
            )
    edges.sort(key=lambda item: (-item["xi_ij"], item["left_ticker"], item["right_ticker"]))
    return edges


def run_analytics(
    feature_rows: list[dict],
    return_rows: list[dict],
    config: dict,
    raw_dir: Path,
    refresh: bool = False,
    fixture_data: dict | None = None,
) -> dict:
    eligible_rows = [row for row in feature_rows if row.get("primary_regression_eligible")]
    eligible_rows.sort(key=lambda item: item["announcement_date"])

    primary = _fit_regression_model(eligible_rows, "primary_qii", ["qii"], include_firms=True, config=config)
    authorization_only = _fit_regression_model(
        [row for row in eligible_rows if row.get("authorization_intensity") is not None],
        "authorization_only",
        ["authorization_intensity", "market_state_20d", "vix_t1"],
        include_firms=False,
        config=config,
    )
    component_rows = []
    for row in eligible_rows:
        if row.get("theta_degrees") is None:
            continue
        clone = dict(row)
        clone["theta_alignment"] = math.cos(math.radians(float(row["theta_degrees"])))
        component_rows.append(clone)
    components = _fit_regression_model(component_rows, "raw_components", ["particle_amplitude", "wave_amplitude", "theta_alignment"], include_firms=False, config=config)

    benchmark_rows: list[dict] = []
    for model in (primary, authorization_only, components):
        if model.get("status") == "ok":
            benchmark_rows.append({"model": model["model"], "r2": model["r2"], "n_obs": model["n_obs"], "data_tier": "public_proxy"})

    alt_rows: list[dict] = []
    for name, builder in (
        ("alt_multiplicative", lambda row: float(row["particle_amplitude"] or 0.0) * float(row["wave_amplitude"] or 0.0) * math.cos(math.radians(float(row["theta_degrees"])))),
        ("alt_arithmetic", lambda row: 0.5 * (float(row["particle_amplitude"] or 0.0) + float(row["wave_amplitude"] or 0.0)) * math.cos(math.radians(float(row["theta_degrees"])))),
        ("alt_cosine_only", lambda row: math.cos(math.radians(float(row["theta_degrees"])))),
    ):
        transformed = []
        for row in eligible_rows:
            if row.get("theta_degrees") is None:
                continue
            clone = dict(row)
            clone["alt_feature"] = builder(row)
            transformed.append(clone)
        model = _fit_regression_model(transformed, name, ["alt_feature", "market_state_20d", "vix_t1"], include_firms=False, config=config)
        if model.get("status") == "ok":
            alt_rows.append({"model": name, "r2": model["r2"], "n_obs": model["n_obs"], "data_tier": "public_proxy"})

    split_rows: list[dict] = []
    for split in config["regression"]["time_splits"]:
        subset = _split_rows(eligible_rows, split["start"], split["end"])
        model = _fit_regression_model(subset, f"time_{split['name']}", ["qii"], include_firms=True, config=config)
        if model.get("status") == "ok":
            split_rows.append({"split": split["name"], "r2": model["r2"], "n_obs": model["n_obs"], "data_tier": "public_proxy"})
    by_size = sorted([row for row in eligible_rows if row.get("authorization_intensity") is not None], key=lambda item: float(item["authorization_intensity"]))
    if by_size:
        midpoint = len(by_size) // 2
        for name, subset in {"size_low": by_size[:midpoint], "size_high": by_size[midpoint:]}.items():
            model = _fit_regression_model(subset, name, ["qii"], include_firms=True, config=config)
            if model.get("status") == "ok":
                split_rows.append({"split": name, "r2": model["r2"], "n_obs": model["n_obs"], "data_tier": "public_proxy"})
    by_vix = sorted([row for row in eligible_rows if row.get("vix_t1") is not None], key=lambda item: float(item["vix_t1"]))
    if by_vix:
        cut_1 = len(by_vix) // 3
        cut_2 = 2 * len(by_vix) // 3
        for name, subset in {"vix_low": by_vix[:cut_1], "vix_mid": by_vix[cut_1:cut_2], "vix_high": by_vix[cut_2:]}.items():
            model = _fit_regression_model(subset, name, ["qii"], include_firms=True, config=config)
            if model.get("status") == "ok":
                split_rows.append({"split": name, "r2": model["r2"], "n_obs": model["n_obs"], "data_tier": "public_proxy"})

    oos_rows: list[dict] = []
    train_rows = [row for row in eligible_rows if row["announcement_date"] < config["sample"]["oos_start"]]
    test_rows = [row for row in eligible_rows if row["announcement_date"] >= config["sample"]["oos_start"]]
    if train_rows and test_rows:
        x_train, y_train, _, _ = _build_primary_design(train_rows)
        x_test, y_test, _, _ = _build_primary_design(test_rows)
        fit = _ols_fit(x_train, y_train, clusters=[row["ticker"] for row in train_rows])
        if fit is not None:
            predictions = [sum(beta * value for beta, value in zip(fit["beta"], row)) for row in x_test]
            mean_y = mean(y_test)
            total = sum((value - mean_y) ** 2 for value in y_test)
            residual = sum((actual - pred) ** 2 for actual, pred in zip(y_test, predictions))
            oos_rows.append({"model": "primary_qii", "r2": 0.0 if total == 0 else 1.0 - residual / total, "rmse": _rmse(y_test, predictions), "mae": _mae(y_test, predictions), "directional_accuracy": _directional_accuracy(y_test, predictions), "data_tier": "public_proxy"})
        rf_features = ["qii", "market_state_20d", "vix_t1", "particle_amplitude", "wave_amplitude"]
        forest = RandomForestRegressorLite(seed=int(config["regression"]["seed"]))
        forest.fit([[float(row[feature] or 0.0) for feature in rf_features] for row in train_rows], y_train)
        rf_predictions = forest.predict([[float(row[feature] or 0.0) for feature in rf_features] for row in test_rows])
        mean_rf = mean(y_test)
        total_rf = sum((value - mean_rf) ** 2 for value in y_test)
        residual_rf = sum((actual - pred) ** 2 for actual, pred in zip(y_test, rf_predictions))
        oos_rows.append({"model": "random_forest_lite", "r2": 0.0 if total_rf == 0 else 1.0 - residual_rf / total_rf, "rmse": _rmse(y_test, rf_predictions), "mae": _mae(y_test, rf_predictions), "directional_accuracy": _directional_accuracy(y_test, rf_predictions), "data_tier": "public_proxy"})

    grouped_returns: dict[str, list[dict]] = {}
    feature_lookup = {row["event_id"]: row for row in feature_rows}
    for row in return_rows:
        grouped_returns.setdefault(row["event_id"], []).append(row)
    coherence_rows: list[dict] = []
    for event_id, rows in grouped_returns.items():
        fit = _fit_coherence_event(event_id, rows, config)
        base = feature_lookup.get(event_id, {})
        coherence_rows.append({"event_id": event_id, "ticker": base.get("ticker"), "theta_degrees": base.get("theta_degrees"), "tau": fit["tau"] if fit else None, "car_0": fit["car_0"] if fit else None, "car_inf": fit["car_inf"] if fit else None, "fit_r2": fit["r2"] if fit else None, "qualified": bool(fit), "data_tier": "public_proxy"})
    coherence_rows.sort(key=lambda item: (item["qualified"] is False, item["ticker"] or "", item["event_id"]))
    decay_law = _fit_decay_law(coherence_rows)
    entanglement_rows = _compute_entanglement(feature_rows)
    tail_screen_rows = _build_tail_screen(feature_rows, entanglement_rows, float(config["entanglement"]["major_drawdown_threshold"]))
    coherence_regimes = _assign_coherence_regimes(coherence_rows, entanglement_rows)
    contagion_edges = _build_contagion_edges(config, raw_dir, refresh=refresh, fixture_data=fixture_data)

    coefficient_rows = []
    for model in (primary, authorization_only, components):
        coefficient_rows.extend(model.get("coefficients", []))

    summary = {
        "target_start": config["sample"]["start"],
        "target_end": config["sample"]["end"],
        "eligible_events": len(eligible_rows),
        "all_events": len(feature_rows),
        "oos_start": config["sample"]["oos_start"],
        "data_tier": "public_proxy",
        "management_model": "lexical_public_proxy",
    }
    return {
        "summary": summary,
        "model_summaries": benchmark_rows,
        "coefficient_rows": coefficient_rows,
        "alternative_rows": alt_rows,
        "robustness_rows": split_rows,
        "oos_rows": oos_rows,
        "coherence_rows": coherence_rows,
        "decay_law": decay_law,
        "coherence_regimes": coherence_regimes,
        "entanglement_rows": entanglement_rows,
        "tail_screen_rows": tail_screen_rows,
        "contagion_edges": contagion_edges,
    }
