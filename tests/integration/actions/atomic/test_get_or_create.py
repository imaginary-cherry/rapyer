import rapyer
from rapyer import GetOrCreateStatus
from rapyer.base import AtomicRedisModel
from tests.integration.actions.create import CreateActionTestBase
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.special_types.adapters import SPECIAL_FIELD_ADAPTERS
from tests.models.collection_types import ComprehensiveTestModel

# ``aget_or_create`` has a dual nature: it CREATEs the model when the key is
# absent and otherwise READs the persisted one. Each branch is exercised by its
# own action-test class — the *Creates* classes never pre-insert (so the create
# branch fires), while the *Finds* classes rely on the default ``setup_data``
# insert (so the found branch fires). Both branches run eagerly off
# ``cls.Meta.redis`` and return a value, so pipeline-deferral coverage is
# skipped exactly like the read actions do.

_SKIP_PIPELINE_ATOMICITY = (
    "aget_or_create returns a value and runs eagerly; can't be deferred "
    "in a pipeline"
)
_SKIP_STALE_MIRROR = "atomic aget_or_create; no field-level local mirror to corrupt"
_SKIP_TTL_NO_REFRESH = "create branch is initial, so TTL is always set"


def assert_special_fields_loaded(loaded, expected):
    """Compare every special field on ``loaded`` against ``expected``.

    Iterates the model's full set of SF fields (asserting there is at least
    one) so the check covers all special fields the model declares.
    """
    sf_fields = type(loaded)._special_field_names
    assert sf_fields, "model under test should declare special fields"
    for fname in sf_fields:
        assert getattr(loaded, fname) == getattr(expected, fname), (
            f"special field {fname!r} did not load as expected: "
            f"{getattr(loaded, fname)!r} != {getattr(expected, fname)!r}"
        )


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
        return [ComprehensiveTestModel(name="fresh", counter=7)]

    async def setup_data(self):
        # Don't insert: the create branch is the subject, so the key must be
        # absent when ``perform_action`` runs. Populate the SF fields BEFORE the
        # call so each one flows through ``aget_or_create``'s atomic save path.
        models = self.create_models()
        for adapter in SPECIAL_FIELD_ADAPTERS:
            await adapter.populate(models[0])
        return models

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await type(piped).aget_or_create(piped)

    async def load_data(self):
        return await rapyer.afind_one(self.created_models[0].key)

    def expected_before(self):
        return None

    def expected_after(self):
        return self.created_models[0]

    def assert_action_effect(self, loaded, action_result):
        assert action_result.status == GetOrCreateStatus.CREATED
        assert action_result.value is self.created_models[0]
        assert loaded == self.expected_after()
        assert_special_fields_loaded(loaded, action_result.value)


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

    async def setup_data(self):
        # Insert the key and populate its SF fields so the found model carries
        # special-field data when ``perform_action`` reads it back.
        models = self.create_models()
        async with rapyer.apipeline():
            await rapyer.ainsert(*models)
            for adapter in SPECIAL_FIELD_ADAPTERS:
                await adapter.populate(models[0])
        return models

    async def perform_action(self, piped: ComprehensiveTestModel):
        # ``setup_data`` already inserted the key, so this hits the found branch.
        return await type(piped).aget_or_create(piped)

    async def load_data(self):
        # A plain get reloads the found model, including its SF fields.
        return await rapyer.afind_one(self.created_models[0].key)

    def expected_before(self):
        return self.created_models[0]

    def assert_action_effect(self, loaded, action_result):
        assert action_result.status == GetOrCreateStatus.FOUND
        assert action_result.value.name == self.created_models[0].name
        assert action_result.value.counter == self.created_models[0].counter
        assert_special_fields_loaded(loaded, action_result.value)


class TestRapyerAgetOrCreateCreates(CreateActionTestBase):
    """Module-level ``rapyer.aget_or_create`` create branch."""

    covered_method = rapyer.aget_or_create
    model_exists_before_action = False
    skip_pipeline_atomicity = _SKIP_PIPELINE_ATOMICITY
    skip_stale_mirror_in_pipeline = _SKIP_STALE_MIRROR
    skip_ttl_no_refresh = _SKIP_TTL_NO_REFRESH

    def create_models(self):
        return [ComprehensiveTestModel(name="mod-fresh", counter=11)]

    async def setup_data(self):
        models = self.create_models()
        for adapter in SPECIAL_FIELD_ADAPTERS:
            await adapter.populate(models[0])
        return models

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await rapyer.aget_or_create(piped)

    async def load_data(self):
        return await rapyer.afind_one(self.created_models[0].key)

    def expected_before(self):
        return None

    def expected_after(self):
        return self.created_models[0]

    def assert_action_effect(self, loaded, action_result):
        assert action_result.status == GetOrCreateStatus.CREATED
        assert action_result.value is self.created_models[0]
        assert loaded == self.expected_after()
        assert_special_fields_loaded(loaded, action_result.value)


class TestRapyerAgetOrCreateFinds(ReadActionTestBase):
    """Module-level ``rapyer.aget_or_create`` found branch."""

    covered_method = rapyer.aget_or_create
    skip_pipeline_atomicity = _SKIP_PIPELINE_ATOMICITY
    skip_stale_mirror_in_pipeline = _SKIP_STALE_MIRROR

    def create_models(self):
        return [ComprehensiveTestModel(name="mod-kept", counter=42)]

    async def setup_data(self):
        # Insert the key and populate its SF fields so the found model carries
        # special-field data when ``perform_action`` reads it back.
        models = self.create_models()
        async with rapyer.apipeline():
            await rapyer.ainsert(*models)
            for adapter in SPECIAL_FIELD_ADAPTERS:
                await adapter.populate(models[0])
        return models

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await rapyer.aget_or_create(piped)

    async def load_data(self):
        # A plain get reloads the found model, including its SF fields.
        return await rapyer.afind_one(self.created_models[0].key)

    def expected_before(self):
        return self.created_models[0]

    def assert_action_effect(self, loaded, action_result):
        assert action_result.status == GetOrCreateStatus.FOUND
        assert action_result.value.name == self.created_models[0].name
        assert action_result.value.counter == self.created_models[0].counter
        assert_special_fields_loaded(loaded, action_result.value)
