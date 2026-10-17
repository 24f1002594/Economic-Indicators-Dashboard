import asyncio

from app.config import Settings
from app.services import collector_service


class RecordingDatabase:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []

    async def execute(self, query: str, parameters: tuple[object, ...] | None = None) -> int:
        self.calls.append((query, parameters))
        return 1


def test_metadata_initialization_registers_each_indicator_before_its_source_binding(monkeypatch) -> None:
    settings = Settings(
        database_url="postgresql://dashboard:password@localhost:5432/economic_dashboard",
        jwt_secret_key="a" * 32,
        cors_origins="https://dashboard.example.com",
    )
    monkeypatch.setattr(collector_service, "get_settings", lambda: settings)
    database = RecordingDatabase()

    asyncio.run(collector_service.initialize_dashboard_metadata(database))

    calls = database.calls
    for indicator_id in (
        "debt_to_gdp_india",
        "gst_collection_india",
        "inflation_india",
    ):
        indicator_index = next(
            index
            for index, (query, parameters) in enumerate(calls)
            if "INSERT INTO indicators" in query and parameters and parameters[0] == indicator_id
        )
        binding_index = next(
            index
            for index, (query, parameters) in enumerate(calls)
            if "INSERT INTO indicator_sources" in query and parameters and parameters[0] == indicator_id
        )
        assert indicator_index < binding_index
