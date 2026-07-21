from rapyer.embeddings.adapter import build_cache_model_label


def test_build_cache_model_label_format_sanity():
    # Act
    label = build_cache_model_label("all-mpnet-base-v2", "1", 768)

    # Assert
    assert label == "all-mpnet-base-v2@1:768"


def test_build_cache_model_label_different_version_differs_sanity():
    # Act
    label_v1 = build_cache_model_label("all-mpnet-base-v2", "1", 768)
    label_v2 = build_cache_model_label("all-mpnet-base-v2", "2", 768)

    # Assert
    assert label_v1 != label_v2


def test_build_cache_model_label_different_dim_differs_sanity():
    # Act
    label_768 = build_cache_model_label("all-mpnet-base-v2", "1", 768)
    label_1536 = build_cache_model_label("all-mpnet-base-v2", "1", 1536)

    # Assert
    assert label_768 != label_1536
