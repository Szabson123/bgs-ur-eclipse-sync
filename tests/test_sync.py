from datetime import datetime, timezone

import httpx
import pytest

from bgs_client import BgsClient, BgsError
from sync import SyncService

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)


class FakeBgs:
    def __init__(self, channels, outcome="unchanged"):
        self.channels_data = channels
        self.outcome = outcome
        self.sent: list[dict] = []
        self.fail_channels: Exception | None = None

    def channels(self):
        if self.fail_channels:
            raise self.fail_channels
        return self.channels_data

    def close(self):
        pass

    def send_num_qa(self, latest):
        self.sent.append(dict(latest))
        outcome = self.outcome
        return {code: outcome(code) if callable(outcome) else outcome for code in latest}


def ch(code):
    return {"id": 1, "station_name": "SMT-1", "boxing_code": code, "last_num_qa": None}


def make(channels, latest, **kwargs):
    queried = []

    def query(codes):
        queried.append(codes)
        if isinstance(latest, Exception):
            raise latest
        return {code: num for code, num in latest.items() if code in codes}

    bgs = FakeBgs(channels, **kwargs)
    return SyncService(bgs, query, clock=lambda: NOW), bgs, queried


def test_sends_latest_num_qa_for_all_channels_in_one_query():
    service, bgs, queried = make([ch("NEXYMLITEJAF27"), ch("NEXYMLITEJAF28"), ch("NEXYMLITEJAF27")],
                                 {"NEXYMLITEJAF27": 1001, "NEXYMLITEJAF28": 2002})
    state = service.run_once()
    assert queried == [["NEXYMLITEJAF27", "NEXYMLITEJAF28"]]  # bez duplikatów, jedno zapytanie
    assert bgs.sent == [{"NEXYMLITEJAF27": 1001, "NEXYMLITEJAF28": 2002}]
    assert state.last_error is None
    assert state.last_success_at == NOW
    assert (state.channels, state.found_in_eclipse) == (2, 2)


def test_reset_recorded_in_state():
    service, bgs, _ = make([ch("A"), ch("B")], {"A": 5, "B": 6},
                           outcome=lambda code: "reset" if code == "A" else "unchanged")
    state = service.run_once()
    assert state.last_results == {"A": "reset", "B": "unchanged"}
    assert state.last_resets == {"A": NOW}


def test_codes_missing_in_eclipse_are_not_sent():
    service, bgs, _ = make([ch("A"), ch("BRAK")], {"A": 5})
    state = service.run_once()
    assert bgs.sent == [{"A": 5}]
    assert (state.channels, state.found_in_eclipse) == (2, 1)


def test_nothing_to_do_without_channels_or_results():
    service, bgs, queried = make([], {})
    service.run_once()
    assert queried == [] and bgs.sent == []

    service, bgs, _ = make([ch("A")], {})
    assert service.run_once().last_error is None
    assert bgs.sent == []


def test_eclipse_error_is_kept_and_next_run_recovers():
    service, bgs, _ = make([ch("A")], ConnectionError("Eclipse nie odpowiada"))
    state = service.run_once()
    service.run_once()
    assert state.consecutive_failures == 2
    assert "Eclipse nie odpowiada" in state.last_error
    assert state.last_success_at is None
    assert bgs.sent == []

    service.query_latest = lambda codes: {"A": 1}
    state = service.run_once()
    assert (state.consecutive_failures, state.last_error, state.runs) == (0, None, 3)


def test_bgs_error_does_not_break_scheduler():
    service, bgs, queried = make([ch("A")], {"A": 1})
    bgs.fail_channels = BgsError("BGS niedostępny")
    state = service.run_once()
    assert state.last_error == "BgsError: BGS niedostępny"
    assert queried == []


# --- klient HTTP BGS ---

def client_with(handler):
    return BgsClient(base_url="http://bgs.test/", api_key="k", transport=httpx.MockTransport(handler))


def test_client_paths_key_and_payload():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("/channels/"):
            return httpx.Response(200, json=[ch("A")])
        return httpx.Response(200, json={"results": {"A": "baseline"}})

    client = client_with(handler)
    assert client.channels() == [ch("A")]
    assert client.send_num_qa({"A": 7}) == {"A": "baseline"}
    assert [str(r.url) for r in seen] == ["http://bgs.test/api/ur/cycle-guard/eclipse/channels/",
                                          "http://bgs.test/api/ur/cycle-guard/eclipse/num-qa/"]
    assert all(r.headers["X-Api-Key"] == "k" for r in seen)
    assert seen[1].read() == b'{"results":[{"boxing_code":"A","num_qa":7}]}'


@pytest.mark.parametrize("response, message", [
    (httpx.Response(403, json={}), "klucz"),
    (httpx.Response(500, text="boom"), "BGS 500"),
])
def test_client_errors(response, message):
    with pytest.raises(BgsError, match=message):
        client_with(lambda request: response).channels()


def test_client_connection_error():
    def handler(request):
        raise httpx.ConnectError("odmowa")
    with pytest.raises(BgsError, match="niedostępny"):
        client_with(handler).channels()
