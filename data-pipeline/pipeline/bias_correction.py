"""Bias correction — QUANTILE MAPPING theo từng xã.

Ý tưởng: mô hình (Open-Meteo) hay lệch hệ thống so với TRẠM đo ở từng xã (vd vùng cao
thường bị dự báo hụt lượng mưa). Quantile mapping ánh xạ giá trị mô hình → giá trị đã
hiệu chỉnh dựa trên cặp phân vị (model_q → obs_q) học từ lịch sử.

- `data/quantile_maps.json`: {commune_code: {variable: {model_q:[...], obs_q:[...]}}}.
- Không có map cho xã/biến nào → GIỮ NGUYÊN (identity), an toàn.
- `train_quantile_map()`: khi có dữ liệu trạm thật, tính cặp phân vị để nạp vào file.
"""

from __future__ import annotations

import json

from pipeline.config import DATA_DIR


class QuantileMapper:
    def __init__(self, maps: dict | None = None) -> None:
        self._maps = maps if maps is not None else self._load()

    @staticmethod
    def _load() -> dict:
        path = DATA_DIR / "quantile_maps.json"
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data.pop("_comment", None)
        return data

    def correct(self, commune_code: str, variable: str, value: float) -> float:
        """Hiệu chỉnh 1 giá trị. Không có map → trả nguyên."""
        m = self._maps.get(commune_code, {}).get(variable)
        if not m:
            return value
        return round(_interp(value, m["model_q"], m["obs_q"]), 2)

    def correct_series(self, commune_code: str, variable: str,
                       values: list[float]) -> list[float]:
        return [self.correct(commune_code, variable, v) for v in values]


def _interp(x: float, xs: list[float], ys: list[float]) -> float:
    """Nội suy tuyến tính từng đoạn (như np.interp), có ngoại suy ở biên."""
    n = len(xs)
    if n == 0:
        return x
    if x <= xs[0]:
        return ys[0] + (x - xs[0]) * (ys[1] - ys[0]) / (xs[1] - xs[0]) if n > 1 else ys[0]
    if x >= xs[-1]:
        return ys[-1] + (x - xs[-1]) * (ys[-1] - ys[-2]) / (xs[-1] - xs[-2]) if n > 1 else ys[-1]
    for i in range(1, n):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


def train_quantile_map(model_series: list[float], obs_series: list[float],
                       n_quantiles: int = 11) -> dict:
    """Tạo cặp phân vị (model_q, obs_q) từ dữ liệu lịch sử (mô hình vs trạm đo).

    Dùng khi đã có số liệu trạm KTTV Điện Biên. Kết quả nạp vào quantile_maps.json.
    """
    def quantiles(sorted_vals: list[float]) -> list[float]:
        n = len(sorted_vals)
        out = []
        for k in range(n_quantiles):
            p = k / (n_quantiles - 1)
            idx = p * (n - 1)
            lo, hi = int(idx), min(int(idx) + 1, n - 1)
            out.append(round(sorted_vals[lo] + (idx - lo) * (sorted_vals[hi] - sorted_vals[lo]), 3))
        return out

    if not model_series or not obs_series:
        raise ValueError("Cần cả model_series và obs_series")
    return {"model_q": quantiles(sorted(model_series)), "obs_q": quantiles(sorted(obs_series))}
