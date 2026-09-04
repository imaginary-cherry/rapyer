import rapyer
from rapyer import GetOrCreateStatus
from rapyer.base import AtomicRedisModel
from tests.integration.actions.create import CreateActionTestBase
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.functioninality.assertions import assert_atomic_models_equal
from tests.models.collection_types import ComprehensiveTestModel

# aget_or_create CREATEs on a missing key and READs otherwise, so each branch gets its own class:
# the *Creates* ones never pre-insert, the *Finds* ones rely on the default setup_data insert.

_SKIP_PIPELINE_ATOMICITY = (
    "aget_or_create returns a value and runs eagerly; can't be deferred "
    "in a pipeline"
)
_SKIP_STALE_MIRROR = "atomic aget_or_create; no field-level local mirror to corrupt"
_SKIP_TTL_NO_REFRESH = "create branch is initial, so TTL is always set"


class TestModelAgetOrCreateCreates(CreateActionTestBase):
    """
    ``AtomicRedisModel.aget_or_create`` when the key is absent: it persists
    the draft and reports ``CREATED``.
    """

    covered_method = AtomicRedisModel.aget_or_create
    model_exists_before_action = False
    skip_pipeline_atomicity = _SKIP_PIPELINE_ATOMICITY
    skip_stale_mirror_in_pipeline = _SKIP_STALE_MIRROR
    skip_ttl_no_refresh = _SKIP_TTL_NO_REFRESH

    def create_models(self):
        return [self.build_model(name="fresh", counter=7)]

    async def setup_data(self):
        # No insert (the create branch is the subject) and SF fields are populated before the call.
        models = self.create_models()
        return models

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await type(piped).aget_or_create(piped)

    async def load_data(self):
        return await rapyer.afind_one(self.created_models[0].key)

    def expected_before(self):
        return None

    def expected_after(self):
        return self.created_models[0]

    async def assert_action_effect(self, loaded, action_result):
        assert action_result.status == GetOrCreateStatus.CREATED
        assert action_result.value is self.created_models[0]
        assert loaded == self.expected_after()
        await assert_atomic_models_equal(loaded, action_result.value)


class TestModelAgetOrCreateFinds(ReadActionTestBase):
    """
    ``AtomicRedisModel.aget_or_create`` when the key already exists: it
    returns the persisted model and reports ``FOUND`` without mutating it.
    """

    covered_method = AtomicRedisModel.aget_or_create
    skip_pipeline_atomicity = _SKIP_PIPELINE_ATOMICITY
    skip_stale_mirror_in_pipeline = _SKIP_STALE_MIRROR

    def create_models(self):
        return [ComprehensiveTestModel(name="kept", counter=99)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        # ``setup_data`` already inserted the key, so this hits the found branch.
        return await type(piped).aget_or_create(piped)

    async def load_data(self):
        # A plain get reloads the found model, including its SF fields.
        return await rapyer.afind_one(self.created_models[0].key)

    def expected_before(self):
        return self.created_models[0]

    async def assert_action_effect(self, loaded, action_result):
        assert action_result.status == GetOrCreateStatus.FOUND
        assert action_result.value.name == self.created_models[0].name
        assert action_result.value.counter == self.created_models[0].counter
        await assert_atomic_models_equal(loaded, action_result.value)


class TestRapyerAgetOrCreateCreates(CreateActionTestBase):
    """Module-level ``rapyer.aget_or_create`` create branch."""

    covered_method = rapyer.aget_or_create
    model_exists_before_action = False
    skip_pipeline_atomicity = _SKIP_PIPELINE_ATOMICITY
    skip_stale_mirror_in_pipeline = _SKIP_STALE_MIRROR
    skip_ttl_no_refresh = _SKIP_TTL_NO_REFRESH

    def create_models(self):
        return [self.build_model(name="mod-fresh", counter=11)]

    async def setup_data(self):
        models = self.create_models()
        return models

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await rapyer.aget_or_create(piped)

    async def load_data(self):
        return await rapyer.afind_one(self.created_models[0].key)

    def expected_before(self):
        return None

    def expected_after(self):
        return self.created_models[0]

    async def assert_action_effect(self, loaded, action_result):
        assert action_result.status == GetOrCreateStatus.CREATED
        assert action_result.value is self.created_models[0]
        assert loaded == self.expected_after()
        await assert_atomic_models_equal(loaded, action_result.value)


class TestRapyerAgetOrCreateFinds(ReadActionTestBase):
    """Module-level ``rapyer.aget_or_create`` found branch."""

    covered_method = rapyer.aget_or_create
    skip_pipeline_atomicity = _SKIP_PIPELINE_ATOMICITY
    skip_stale_mirror_in_pipeline = _SKIP_STALE_MIRROR

    def create_models(self):
        return [ComprehensiveTestModel(name="mod-kept", counter=42)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await rapyer.aget_or_create(piped)

    async def load_data(self):
        # A plain get reloads the found model, including its SF fields.
        return await rapyer.afind_one(self.created_models[0].key)

    def expected_before(self):
        return self.created_models[0]

    async def assert_action_effect(self, loaded, action_result):
        assert action_result.status == GetOrCreateStatus.FOUND
        assert action_result.value.name == self.created_models[0].name
        assert action_result.value.counter == self.created_models[0].counter
        await assert_atomic_models_equal(loaded, action_result.value)
