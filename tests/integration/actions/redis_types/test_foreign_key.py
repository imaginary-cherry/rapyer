from rapyer.types.foreign_key import ForeignKey
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.models.foreign_key_types import FkAfetchOwner, FkAfetchTarget

# ForeignKey.afetch is a READ|FETCH action (target=RESULT): it resolves the
# referenced model and refreshes that *target's* TTL. It returns a value, so
# pipeline deferral doesn't apply.
#
# Under V2 the refresh is OWNER-gated: the wrap decision uses the owner's
# TTL-refresh config at install time. So the owner is created_models[0] (the
# model the TTL harness patches), while the checked key is the target's
# (models_to_check_ttl).


class TestForeignKeyAfetch(ReadActionTestBase, TTLActionTestBase):
    covered_method = ForeignKey.afetch
    skip_pipeline_atomicity = (
        "afetch returns the resolved target; can't be deferred in a pipeline"
    )
    skip_stale_mirror_in_pipeline = (
        "afetch reads the target via aget; no local mirror to corrupt"
    )

    def create_models(self):
        target = FkAfetchTarget(name="resolved", age=7)
        return [FkAfetchOwner(ref=target), target]

    def ttl_keys(self, model):
        return [model.key]

    async def populate_special_fields(self, *models):
        return

    async def perform_action(self, piped: FkAfetchOwner):
        return await self.created_models[0].ref.afetch()

    def models_to_check_ttl(self):
        # afetch refreshes the fetched target, so its TTL is what we assert.
        return [self.created_models[1]]

    def expected_before(self):
        # afetch returns the hydrated target; equality is by field content.
        return FkAfetchTarget(name="resolved", age=7)
