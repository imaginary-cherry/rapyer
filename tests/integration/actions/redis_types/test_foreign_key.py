from rapyer.types.foreign_key import ForeignKey
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.models.foreign_key_types import FkAfetchOwner, FkAfetchTarget

# ForeignKey.afetch is a READ|FETCH action (target=RESULT): it resolves the
# referenced model and refreshes that *target's* TTL — including on the cached
# path, where it never calls the inner aget, so afetch's own action is the only
# refresher. It returns a value, so pipeline deferral doesn't apply.
#
# The target carries TTL with refresh_ttl=False so the inner aget won't refresh
# it; that isolates afetch's own action wrapper for the TTL assertions, and the
# checked key is the target's.

FK_TARGET_KEY = "FkAfetchTarget:fk-afetch-target"


class TestForeignKeyAfetch(ReadActionTestBase, TTLActionTestBase):
    covered_method = ForeignKey.afetch
    skip_pipeline_atomicity = (
        "afetch returns the resolved target; can't be deferred in a pipeline"
    )
    skip_stale_mirror_in_pipeline = (
        "afetch reads the target via aget; no local mirror to corrupt"
    )

    def create_models(self):
        ref = FkAfetchTarget(name="resolved", age=7)
        return [ref, FkAfetchOwner(ref=ref)]

    def ttl_keys(self, model):
        # afetch refreshes the fetched target, not the owner.
        return [model.key]

    async def populate_special_fields(self, *models):
        return

    async def perform_action(self, piped: FkAfetchOwner):
        return await self.created_models[1].ref.afetch()

    def expected_before(self):
        # afetch returns the hydrated target; equality is by field content.
        return FkAfetchTarget(name="resolved", age=7)

    def models_to_check_ttl(self):
        return [self.created_models[0]]