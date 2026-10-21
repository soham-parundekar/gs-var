"""Load the run settings from config/params.yaml.

Everything the pipeline can be tuned by lives in one file, so a reader can see
the whole specification without reading seven scripts, and a reviewer can
change the lookback window in one place and rerun.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .historical_sim import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = PROJECT_ROOT / "config" / "params.yaml"


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def interim(self) -> Path:
        return self.root / "data" / "interim"

    @property
    def processed(self) -> Path:
        return self.root / "data" / "processed"

    @property
    def references(self) -> Path:
        return self.root / "references"

    @property
    def figures(self) -> Path:
        return self.root / "reports" / "figures"


class Config:
    """Thin accessor over the YAML, with the derived objects callers want."""

    def __init__(self, raw: dict, root: Path):
        self._raw = raw
        self.paths = Paths(root)

    def __getitem__(self, section: str) -> dict:
        return self._raw[section]

    @property
    def years(self) -> list[int]:
        sample = self._raw["sample"]
        return list(range(sample["first_year"], sample["last_year"] + 1))

    @property
    def start(self) -> str:
        return f"{self._raw['sample']['first_year']}-01-01"

    @property
    def end(self) -> str:
        return f"{self._raw['sample']['last_year']}-12-31"

    @property
    def base_year(self) -> int:
        return int(self._raw["calibration"]["base_year"])

    def settings(
        self,
        quantile: float | None = None,
        window: int | None = None,
        age_decay: float | None = None,
    ) -> Settings:
        engine = self._raw["engine"]
        return Settings(
            window=window if window is not None else int(engine["window"]),
            quantile=quantile if quantile is not None else float(engine["quantile"]),
            interpolate=bool(engine["interpolate"]),
            age_decay=(
                age_decay if age_decay is not None else float(engine["age_decay"])
            ),
        )


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> Config:
    location = path or DEFAULT_PATH
    with location.open(encoding="utf-8") as handle:
        return Config(yaml.safe_load(handle), location.resolve().parents[1])
