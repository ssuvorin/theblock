from app.services.opportunity_verifier import OpportunityVerifier, VerificationInput


def test_all_five_checks_and_full_document_are_required_for_verified() -> None:
    verifier = OpportunityVerifier()
    verified = verifier.verify(
        VerificationInput(True, True, True, True, True, True, evidence_type="vacancy")
    )
    assert verified.status == "verified_open_role"
    snippet_only = verifier.verify(
        VerificationInput(True, True, True, True, True, False, evidence_type="vacancy")
    )
    assert snippet_only.status == "unverified"


def test_hiring_signal_and_stale_states() -> None:
    verifier = OpportunityVerifier()
    signal = verifier.verify(
        VerificationInput(False, True, True, False, True, True, evidence_type="expansion")
    )
    assert signal.status == "hiring_signal"
    stale = verifier.verify(
        VerificationInput(True, True, True, False, True, True, was_verified=True)
    )
    assert stale.status == "stale"
