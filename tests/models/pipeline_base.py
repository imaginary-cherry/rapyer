from rapyer.base import AtomicRedisModel

INIT_CLOBBER_SENTINEL: str = "INIT_CLOBBER_SENTINEL"


class PipelineActionModel(AtomicRedisModel):
    """Base model for all models used in pipeline action tests.

    Adds a sentinel field used by UpdateActionTestBase.test_no_clobber
    to verify that pipeline actions don't overwrite unrelated fields.
    """

    pipeline_no_clobber_sentinel: str = INIT_CLOBBER_SENTINEL
