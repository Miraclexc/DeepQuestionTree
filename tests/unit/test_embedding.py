import pytest

from src.backend.llm.embedding import EmbeddingManager


@pytest.fixture
def reset_embedding_manager():
    original_instance = EmbeddingManager._instance
    original_model = EmbeddingManager._model
    original_client = EmbeddingManager._client
    original_prefer_client = EmbeddingManager._prefer_client
    original_hash_fallback = EmbeddingManager._using_hash_fallback
    original_fallback_warning_emitted = EmbeddingManager._fallback_warning_emitted

    EmbeddingManager._instance = None
    EmbeddingManager._model = None
    EmbeddingManager._client = None
    EmbeddingManager._prefer_client = False
    EmbeddingManager._using_hash_fallback = False
    EmbeddingManager._fallback_warning_emitted = False

    yield

    EmbeddingManager._instance = original_instance
    EmbeddingManager._model = original_model
    EmbeddingManager._client = original_client
    EmbeddingManager._prefer_client = original_prefer_client
    EmbeddingManager._using_hash_fallback = original_hash_fallback
    EmbeddingManager._fallback_warning_emitted = original_fallback_warning_emitted


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embedding_manager_falls_back_to_hash_embedding_when_local_model_fails(
    monkeypatch,
    reset_embedding_manager,
):
    monkeypatch.setenv("EMBEDDING__USE_LOCAL", "true")
    monkeypatch.setenv("EMBEDDING__LOCAL_FILES_ONLY", "true")
    monkeypatch.setenv("EMBEDDING__FALLBACK_MODE", "hash")

    import src.backend.llm.embedding as embedding_module
    from src.backend.config_loader import reload_settings

    reload_settings()

    class FailingSentenceTransformer:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("local model unavailable")

    monkeypatch.setattr(
        embedding_module,
        "SentenceTransformer",
        FailingSentenceTransformer,
        raising=False,
    )

    manager = EmbeddingManager()
    vector = await manager.get_embedding("test question")

    assert len(vector) == 768
    assert manager.get_dimension() == 768
    assert all(isinstance(value, float) for value in vector)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embedding_manager_raises_when_fallback_disabled(
    monkeypatch,
    reset_embedding_manager,
):
    monkeypatch.setenv("EMBEDDING__USE_LOCAL", "true")
    monkeypatch.setenv("EMBEDDING__LOCAL_FILES_ONLY", "true")
    monkeypatch.setenv("EMBEDDING__FALLBACK_MODE", "none")

    import src.backend.llm.embedding as embedding_module
    from src.backend.config_loader import reload_settings

    reload_settings()

    class FailingSentenceTransformer:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("local model unavailable")

    monkeypatch.setattr(
        embedding_module,
        "SentenceTransformer",
        FailingSentenceTransformer,
        raising=False,
    )

    manager = EmbeddingManager()

    with pytest.raises(Exception, match="加载本地嵌入模型失败"):
        await manager.get_embedding("test question")
