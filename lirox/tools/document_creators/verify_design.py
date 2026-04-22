from lirox.tools.document_creators.design_system import DesignSystem
decision = DesignSystem.decide_design("history of artificial intelligence")
print(f"Palette: {decision.palette.value}")
print(f"Structure: {decision.structure}")
print(f"Confidence: {decision.confidence}")
