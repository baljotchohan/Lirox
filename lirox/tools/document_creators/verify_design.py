# Verification: run this to confirm DesignEngine works
from lirox.tools.file_generation.design_engine import DesignEngine

tests = [
    "create pdf on github",
    "create pdf on github for new learners",
    "create pptx on history of artificial intelligence",
    "create pdf on marketing strategy for startup",
]

for q in tests:
    plan = DesignEngine.plan_document(q, q[:80])
    print(f"\n{'='*60}")
    print(f"Query: {q}")
    print(f"  Palette:  {plan.palette}")
    print(f"  Audience: {plan.audience.value}")
    print(f"  Theme:    {plan.theme.value}")
    print(f"  Sections: {len(plan.structure)}")
    print(f"  Pages:    {plan.page_count}")
