import httpx

from config import settings

ECLIPSE_PATH = "/api/ur/cycle-guard/eclipse/"


class BgsError(Exception):
    pass


class BgsClient:
    """Endpointy BGS-backend dla tego serwisu (nagłówek X-Api-Key = CYCLE_GUARD_ECLIPSE_API_KEY)."""

    def __init__(self, base_url: str = settings.bgs_url, api_key: str = settings.bgs_api_key,
                 timeout: float = settings.request_timeout_seconds, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + ECLIPSE_PATH,
            headers={"X-Api-Key": api_key, "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise BgsError(f"BGS niedostępny: {e}") from e
        if response.status_code in (401, 403):
            raise BgsError("BGS odrzucił klucz serwisu (BGS_API_KEY ≠ CYCLE_GUARD_ECLIPSE_API_KEY w backendzie).")
        if response.status_code >= 400:
            raise BgsError(f"BGS {response.status_code}: {response.text[:300]}")
        return response.json()

    def channels(self) -> list[dict]:
        """Kanały aktywnych stanowisk z BoxingCode: [{id, station_name, boxing_code, last_num_qa, ...}]."""
        return self._request("GET", "channels/")

    def send_num_qa(self, latest: dict[str, int]) -> dict[str, str]:
        """Zwraca status per kod: baseline | unchanged | reset | unknown | inactive."""
        payload = {"results": [{"boxing_code": code, "num_qa": num_qa} for code, num_qa in latest.items()]}
        return self._request("POST", "num-qa/", json=payload)["results"]

    def close(self) -> None:
        self._client.close()
