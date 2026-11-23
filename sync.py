"""
Jedno odpytanie: kanały z BGS → najnowsze NumQA z Eclipse → wynik do BGS.
O zerowaniu decyduje BGS (porównuje z ostatnim NumQA kanału), serwis tylko przenosi dane.
"""
import logging
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("eclipse_sync")


@dataclass
class SyncState:
    runs: int = 0
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    channels: int = 0
    found_in_eclipse: int = 0
    last_results: dict[str, str] = field(default_factory=dict)
    # Ostatnie zerowanie wywołane przez ten serwis (od startu procesu): {BoxingCode: czas}
    last_resets: dict[str, datetime] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


class SyncService:
    def __init__(self, bgs, query_latest: Callable[[list[str]], dict[str, int]],
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.bgs = bgs
        self.query_latest = query_latest
        self.clock = clock
        self.state = SyncState()
        self._lock = threading.Lock()  # harmonogram i ręczne /sync/run nie mogą iść naraz

    def run_once(self) -> SyncState:
        with self._lock:
            now = self.clock()
            self.state.runs += 1
            self.state.last_run_at = now
            try:
                self._sync(now)
            except Exception as e:  # noqa: BLE001 – każdy błąd ma trafić do /health, a harmonogram działać dalej
                self.state.consecutive_failures += 1
                self.state.last_error = f"{type(e).__name__}: {e}"
                logger.error("Odpytanie nieudane (%s z rzędu): %s", self.state.consecutive_failures, e)
            else:
                self.state.consecutive_failures = 0
                self.state.last_error = None
                self.state.last_success_at = now
            return self.state

    def _sync(self, now: datetime) -> None:
        channels = self.bgs.channels()
        codes = sorted({channel["boxing_code"] for channel in channels if channel.get("boxing_code")})
        self.state.channels = len(codes)
        if not codes:
            self.state.found_in_eclipse = 0
            self.state.last_results = {}
            return

        latest = self.query_latest(codes)
        self.state.found_in_eclipse = len(latest)
        missing = [code for code in codes if code.upper() not in {c.upper() for c in latest}]
        if missing:
            logger.warning("Brak paczek w Eclipse dla: %s", ", ".join(missing))
        if not latest:
            self.state.last_results = {}
            return

        results = self.bgs.send_num_qa(latest)
        self.state.last_results = results
        for code, outcome in results.items():
            if outcome == "reset":
                self.state.last_resets[code] = now
                logger.info("Nowa paczka QA dla %s (NumQA %s) – BGS zeruje licznik kanału", code, latest[code])
            elif outcome == "baseline":
                logger.info("Punkt odniesienia dla %s: NumQA %s", code, latest[code])
