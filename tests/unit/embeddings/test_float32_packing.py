import numpy as np
import pytest
from rapyer.embeddings.adapter import pack_float32_blob

from rapyer.errors import RapyerSerializationError


def test_pack_float32_blob_round_trips_sanity():
    # Arrange
    vector = [0.1, 0.2, 0.3, 0.4]

    # Act
    blob = pack_float32_blob(vector, dim=4)

    # Assert
    assert isinstance(blob, bytes)
    assert len(blob) == 16
    round_tripped = np.frombuffer(blob, dtype="<f4")
    assert round_tripped == pytest.approx(vector, abs=1e-6)


@pytest.mark.parametrize(["vector", "dim"], [[[0.1, 0.2], 4], [[0.1, 0.2, 0.3], 2]])
def test_pack_float32_blob_dim_mismatch_raises_sanity(vector, dim):
    # Act / Assert
    with pytest.raises(RapyerSerializationError):
        pack_float32_blob(vector, dim=dim)
