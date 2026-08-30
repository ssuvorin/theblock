from app.services.query.goal_parser import DeterministicGoalParser


def test_dubai_crypto_product_goal_is_deterministic() -> None:
    question = (
        "I'm looking for a Product Manager role at a crypto company in Dubai. "
        "Who could help and which companies are hiring?"
    )
    goal = DeterministicGoalParser().parse(question)
    assert goal.role == "Product Manager"
    assert goal.related_roles == [
        "Senior Product Manager",
        "Product Lead",
        "Product Owner",
        "Head of Product",
    ]
    assert goal.industry == ["crypto", "web3", "digital assets"]
    assert goal.location == ["Dubai", "UAE"]
    assert "warm paths" in goal.action


def test_unknown_goal_does_not_invent_fields() -> None:
    goal = DeterministicGoalParser().parse("Tell me about my week")
    assert goal.role is None
    assert goal.industry == []
    assert goal.location == []
