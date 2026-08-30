from typing import ClassVar

from app.config import Settings
from app.domain.ports import OutboundMessagePort
from app.models import Owner
from app.repositories.opportunities import OpportunityRepository
from app.repositories.people import PeopleRepository
from app.services.presentation import private_citation, public_citation


class DraftService:
    """Builds editable text from cited evidence and never invokes outbound ports."""

    allowed_actions: ClassVar[list[str]] = [
        "edit",
        "copy",
        "open_external_client",
        "create_reminder",
        "save_opportunity",
    ]

    def __init__(
        self,
        session,
        owner: Owner,
        settings: Settings,
        outbound_ports: list[OutboundMessagePort] | None = None,
    ) -> None:
        self._opportunities = OpportunityRepository(
            session,
            owner.id,
            settings.demo_mode,
        )
        self._people = PeopleRepository(session, owner.id, settings.demo_mode)
        self._outbound_ports = outbound_ports or []

    def create(
        self,
        person_id: str,
        opportunity_id: str,
        goal: str,
        action: str,
        channel: str,
    ) -> dict:
        del channel
        if action.casefold() in {"send", "deliver", "apply", "contact"}:
            raise ValueError("Sending and applying are not supported")
        person = self._people.get(person_id)
        opportunity = self._opportunities.get(opportunity_id)
        if person is None or opportunity is None:
            raise LookupError("Person or opportunity not found")
        matching_path = next(
            (row for row in self._opportunities.paths(opportunity.id) if row[1].id == person.id),
            None,
        )
        evidence = self._opportunities.evidence(opportunity.id)
        if matching_path is None or not evidence:
            raise ValueError("A cited relationship path and public opportunity are required")
        interaction = matching_path[3]
        organization = self._opportunities.organization(opportunity.organization_id)
        text = self._compose(
            person.display_name, interaction, opportunity, organization, goal, action
        )
        return {
            "text": text,
            "person_id": person.id,
            "opportunity_id": opportunity.id,
            "send_supported": False,
            "apply_supported": False,
            "allowed_actions": self.allowed_actions,
            "private_citations": [private_citation(interaction)],
            "public_citations": [public_citation(item) for item in evidence],
            "outbound_calls": 0,
        }

    @staticmethod
    def _compose(name, interaction, opportunity, organization, goal, action) -> str:
        subject = interaction.subject or "our earlier conversation"
        org_name = organization.name if organization else "the company"
        action_text = (
            "Would you be open to a quick catch-up and sharing your perspective on the team?"
            if action == "reconnect"
            else "Would you be comfortable pointing me toward the right person to learn more?"
        )
        return (
            f"Hi {name},\n\nIt has been a while since {subject}. "
            f"I appreciated our conversation. I noticed the {opportunity.role_title} "
            f"opportunity at {org_name} in {opportunity.location}. "
            f"I am currently exploring this goal: {goal}. {action_text}\n\nBest,\nAlex"
        )
