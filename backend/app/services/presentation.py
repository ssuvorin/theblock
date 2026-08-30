from datetime import UTC, datetime

from app.models import (
    FollowUp,
    InteractionEvent,
    Opportunity,
    OpportunityEvidence,
    OpportunityPersonPath,
    Organization,
    Person,
    PersonIdentity,
    Relationship,
)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


def public_citation(evidence: OpportunityEvidence) -> dict:
    return {
        "url": evidence.url,
        "title": evidence.title,
        "source_domain": evidence.source_domain,
        "checked_at": iso(evidence.checked_at),
        "excerpt": evidence.excerpt,
        "evidence_type": evidence.evidence_type,
        "verification_details": evidence.verification_details,
    }


def private_citation(interaction: InteractionEvent) -> dict:
    return {
        "interaction_id": interaction.id,
        "source": interaction.source,
        "subject": interaction.subject,
        "occurred_at": iso(interaction.occurred_at),
        "snippet": (interaction.body_text or "")[:240],
        "locator": interaction.metadata_json.get("citation_locator", "body"),
    }


def opportunity_base(
    opportunity: Opportunity,
    organization: Organization | None,
    evidence: list[OpportunityEvidence],
) -> dict:
    return {
        "id": opportunity.id,
        "opportunity_id": opportunity.id,
        "verification_status": opportunity.verification_status,
        "role_title": opportunity.role_title,
        "organization": organization_json(organization),
        "location": opportunity.location,
        "summary": opportunity.summary,
        "canonical_url": opportunity.canonical_url,
        "source_domain": opportunity.source_domain,
        "checked_at": iso(opportunity.checked_at),
        "saved": opportunity.saved_at is not None,
        "dismissed": opportunity.dismissed_at is not None,
        "provider": opportunity.provider,
        "provider_disclosure": opportunity.provider_disclosure,
        "public_citations": [public_citation(item) for item in evidence],
    }


def organization_json(organization: Organization | None) -> dict | None:
    if organization is None:
        return None
    return {
        "id": organization.id,
        "name": organization.name,
        "domain": organization.domain,
        "industry": organization.industry,
        "enrichment_provider": organization.enrichment_provider,
    }


def warm_path_json(
    path: OpportunityPersonPath,
    person: Person,
    relationship: Relationship,
    interaction: InteractionEvent,
    organization: Organization | None,
    factors: dict,
) -> dict:
    organization_name = organization.name if organization else "unresolved organization"
    confidence = (
        "high" if path.path_score >= 0.8 else "medium" if path.path_score >= 0.55 else "low"
    )
    return {
        "person_id": person.id,
        "display_name": person.display_name,
        "current_role": person.current_title,
        "path": ["You", person.display_name, organization_name],
        "path_type": path.path_type,
        "relevance_reason": path.rationale,
        "suggested_action": path.suggested_action,
        "confidence_band": confidence,
        "relationship_status": relationship.status,
        "ranking_factors": factors,
        "private_citations": [private_citation(interaction)],
    }


def interaction_json(interaction: InteractionEvent) -> dict:
    return {
        "id": interaction.id,
        "type": interaction.type,
        "source": interaction.source,
        "subject": interaction.subject,
        "occurred_at": iso(interaction.occurred_at),
        "direction": interaction.direction,
        "snippet": (interaction.body_text or "")[:240],
        "locator": interaction.metadata_json.get("citation_locator", "body"),
    }


def identity_json(identity: PersonIdentity) -> dict:
    value = identity.raw_value
    if identity.kind == "email" and "@" in value:
        local, domain = value.split("@", 1)
        value = f"{local[:1]}***@{domain}"
    return {
        "kind": identity.kind,
        "value": value,
        "source": identity.source,
        "verified": identity.is_verified,
        "primary": identity.is_primary,
    }


def relationship_json(relationship: Relationship | None) -> dict:
    if relationship is None:
        return {
            "status": "unknown",
            "strength_score": 0.0,
            "strength_components": {},
            "last_interaction_at": None,
            "total_interactions": 0,
        }
    return {
        "status": relationship.status,
        "strength_score": relationship.strength_score,
        "strength_components": relationship.strength_components,
        "last_interaction_at": iso(relationship.last_interaction_at),
        "total_interactions": relationship.total_interactions,
        "score_is_advisory": True,
    }


def follow_up_json(follow_up: FollowUp, person: Person | None = None) -> dict:
    result = {
        "id": follow_up.id,
        "person_id": follow_up.person_id,
        "reason": follow_up.reason,
        "due_date": follow_up.due_date.isoformat() if follow_up.due_date else None,
        "due_timezone": follow_up.due_timezone,
        "source": follow_up.source,
        "source_key": follow_up.source_key,
        "priority": follow_up.priority,
        "status": follow_up.status,
        "created_at": iso(follow_up.created_at),
        "updated_at": iso(follow_up.updated_at),
    }
    if person:
        result["person"] = {"id": person.id, "display_name": person.display_name}
    return result
