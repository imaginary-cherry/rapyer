from rapyer.base import AtomicRedisModel

INIT_CLOBBER_SENTINEL: str = "INIT_CLOBBER_SENTINEL"


class PipelineActionModel(AtomicRedisModel):
    """Base model for all models used in pipeline action tests."""

    pipeline_no_clobber_sentinel: str = INIT_CLOBBER_SENTINEL
