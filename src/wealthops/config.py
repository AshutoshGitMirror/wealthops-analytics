"""Project configuration and paths.

The project is intentionally configuration-light: a single frozen dataclass
holds the synthetic-data scenario parameters and filesystem locations.  All
commands accept overrides so tests can build into a temporary directory.
"""

from __future__ import annotations

import calendar
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


@dataclass(frozen=True)
class Settings:
    """Scenario and storage settings.

    Dates are expressed as month-end dates.  The default observation window is
    the 24 complete months ending 31 Oct 2026.
    """

    seed: int = 42
    n_clients: int = 5_000
    n_advisors: int = 30
    n_channels: int = 3
    months: int = 24
    end_month: date = date(2026, 10, 31)
    data_dir: Path = PROJECT_ROOT / "data"
    export_dir: Path = PROJECT_ROOT / "exports"
    sql_dir: Path = PROJECT_ROOT / "sql"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "wealthops.duckdb"

    @property
    def start_month(self) -> date:
        """First month-end in the observation window."""
        year = self.end_month.year
        month = self.end_month.month - (self.months - 1)
        while month <= 0:
            month += 12
            year -= 1
        return month_end(year, month)

    @property
    def month_ends(self) -> list[date]:
        """All month-end dates in the observation window, oldest first."""
        out: list[date] = []
        year, month = self.start_month.year, self.start_month.month
        for _ in range(self.months):
            out.append(month_end(year, month))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return out

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = os.getenv("WEALTHOPS_DATA_DIR")
        db_path = os.getenv("WEALTHOPS_DB_PATH")
        export_dir = os.getenv("WEALTHOPS_EXPORT_DIR")
        resolved_data_dir = (
            Path(data_dir)
            if data_dir
            else (Path(db_path).parent if db_path else PROJECT_ROOT / "data")
        )
        return cls(
            seed=_env_int("WEALTHOPS_SEED", 42),
            n_clients=_env_int("WEALTHOPS_CLIENTS", 5_000),
            n_advisors=_env_int("WEALTHOPS_ADVISORS", 30),
            n_channels=_env_int("WEALTHOPS_CHANNELS", 3),
            months=_env_int("WEALTHOPS_MONTHS", 24),
            data_dir=resolved_data_dir,
            export_dir=Path(export_dir) if export_dir else PROJECT_ROOT / "exports",
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
