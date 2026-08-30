"""Cast and copy for the synthetic Dubai crypto-PM export.

Kept apart from the writer so the generator stays readable and the narrative can change
without touching CSV mechanics.
"""

from __future__ import annotations

from dataclasses import dataclass

OWNER_FIRST_NAME = "Maya"
OWNER_LAST_NAME = "Haddad"
OWNER_SLUG = "maya-haddad-product"
OWNER_HEADLINE = "Product Manager | Crypto & Digital Assets | Building trusted products in Dubai"
OWNER_SUMMARY = (
    "Product manager focused on crypto, wallets, and digital assets. Recently relocated to "
    "Dubai to build simple, trustworthy financial products for a global audience."
)
OWNER_EMAIL = "maya.haddad@example.test"
OWNER_PHONE = "+971 50 555 0101"
OWNER_LOCATION = "Dubai, United Arab Emirates"


@dataclass(frozen=True, slots=True)
class Contact:
    """A connection who exchanged messages with the owner."""

    first_name: str
    last_name: str
    slug: str
    company: str
    position: str
    threads: int

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def linkedin_url(self) -> str:
        return f"https://www.linkedin.com/in/{self.slug}"


# Contacts carrying the demo narrative appear first; the rest give the graph realistic bulk.
CONTACTS: tuple[Contact, ...] = (
    Contact("Marta", "Oliveira", "marta-oliveira-product", "Rain", "VP Product", 3),
    Contact("Sergey", "Lapin", "sergey-lapin-ai", "NeuralPay Labs", "Chief Technology Officer", 3),
    Contact(
        "John", "Whitfield", "john-whitfield-capital", "Crescent Digital Ventures", "Partner", 2
    ),
    Contact("Daniel", "Ruiz", "daniel-ruiz-ops", "Palm Logistics", "Head of Operations", 2),
    Contact("Nadia", "Karim", "nadia-karim-growth", "OrbitPay", "Growth Lead", 2),
    Contact("Omar", "Faris", "omar-faris-design", "Saffron Wallet", "Product Designer", 2),
    Contact("Lena", "Brandt", "lena-brandt-founder", "DesertBlock", "Co-founder", 1),
    Contact("Tom", "Nkemdirim", "tom-nkemdirim-eng", "HarborX", "Engineering Manager", 1),
    Contact("Ruth", "Alvarez", "ruth-alvarez-talent", "Atlas Custody", "Technical Recruiter", 2),
    Contact(
        "Priya", "Raghavan", "priya-raghavan-risk", "Nebula Markets", "Risk Product Manager", 1
    ),
    Contact("Yusuf", "Demir", "yusuf-demir-compliance", "Lattice Labs", "Compliance Lead", 1),
    Contact("Hana", "Sato", "hana-sato-research", "NodeSpring", "User Researcher", 1),
)

# Connections the owner never messaged, so the importer must not invent interactions for them.
SILENT_CONNECTION_NAMES: tuple[tuple[str, str], ...] = (
    ("Aisha", "Reed"),
    ("Nora", "Moretti"),
    ("Layla", "Santos"),
    ("Mariam", "Nasser"),
    ("Elena", "Singh"),
    ("Zara", "Malik"),
    ("Karim", "Haddadi"),
    ("Faisal", "Al Mansoori"),
    ("Beatriz", "Costa"),
    ("Ivan", "Petrov"),
    ("Chen", "Wei"),
    ("Sofia", "Lindqvist"),
    ("Ahmed", "Belhaj"),
    ("Grace", "Otieno"),
    ("Tariq", "Shah"),
    ("Emilia", "Novak"),
    ("Rami", "Khoury"),
    ("Dina", "Farouk"),
    ("Victor", "Alonso"),
    ("Mei", "Tanaka"),
)
SILENT_COMPANIES: tuple[str, ...] = (
    "NovaLedger Labs",
    "Crescent Protocol",
    "Mirage Finance",
    "PalmChain",
    "OrbitPay",
    "",
)
SILENT_POSITIONS: tuple[str, ...] = (
    "Product Manager",
    "Blockchain Engineer",
    "Community Lead",
    "Investment Associate",
    "Data Analyst",
    "",
)

SHORT_MESSAGES: tuple[str, ...] = (
    "Quick follow-up on the Dubai product conversation. Are you free next week?",
    "Thanks, this is useful context. I will review it and send a concise update.",
    "The crypto infrastructure angle makes sense. Let us compare notes on Thursday.",
    "Good point about the UAE market. The product team should validate that assumption.",
    "I can make an introduction after the roadmap review. Does Tuesday afternoon work?",
    "That hiring signal sounds relevant. Please send the role scope when it is ready.",
    "Agreed. A short call is enough, then we can decide whether to involve the team.",
    "The launch plan is moving. I have one question about positioning and distribution.",
    "Let us keep this practical: market, role, location, and the right warm introduction.",
    "Appreciate the update. Dubai remains the priority and product leadership is the fit.",
    "Makes sense. I will share the notes after I speak with the digital assets team.",
    "Yes, please send it over. I can review the product brief before the weekend.",
)

# Narrative openers keyed by slug; these are the lines the demo cites as warm-path evidence.
CONTEXT_MESSAGES: dict[str, tuple[str, ...]] = {
    "marta-oliveira-product": (
        "It was great meeting at TOKEN2049. We were introduced after the product panel.",
        "The Dubai crypto infrastructure team is shaping a VP Product hiring plan.",
        "Eight months since our last contact already. I would value a quick reconnection.",
    ),
    "sergey-lapin-ai": (
        "Great meeting at the AI meetup in Dubai. The technical discussion was useful.",
        "The mutual NDA is signed for three years, so we can continue product scoping.",
        "We are discussing UAE expansion and hiring for the AI product team.",
    ),
    "john-whitfield-capital": (
        "Several digital assets portfolio companies are hiring product talent in Dubai.",
        "Happy to make a warm introduction. We have a strong relationship to work from.",
    ),
    "daniel-ruiz-ops": (
        "Following up from our WhatsApp chat about operations at Palm Logistics.",
        "I sent the Palm Logistics role details to your Gmail so the context stays handy.",
        "Palm Logistics posted the Dubai marketing lead role six days ago.",
    ),
}

SKILLS: tuple[str, ...] = (
    "Product Management",
    "Crypto",
    "Digital Assets",
    "Product Discovery",
    "Tokenization",
    "Go-to-Market",
)
FOLLOWED_COMPANIES: tuple[str, ...] = (
    "Binance",
    "Rain",
    "OKX",
    "Crypto.com",
    "Dubai Future Foundation",
)
POSITIONS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "NovaLedger Labs",
        "Product Manager",
        "Owns discovery and roadmap for a regulated digital-asset wallet.",
        "Aug 2025",
        "",
    ),
    (
        "OrbitPay",
        "Associate Product Manager",
        "Improved onboarding, payments reliability, and product analytics.",
        "Jan 2024",
        "Jul 2025",
    ),
    (
        "OrbitPay",
        "Product Analyst",
        "Built dashboards, ran customer research, and supported experimentation.",
        "Sep 2022",
        "Dec 2023",
    ),
)
JOB_PREFERENCE_HEADERS: tuple[str, ...] = (
    "Locations",
    "Industries",
    "Preferred Job Types",
    "Job Titles",
    "Open To Recruiters",
    "Introduction Statement",
    "Job Seeking Urgency Level",
)
JOB_PREFERENCE_ROW: tuple[str, ...] = (
    f"{OWNER_LOCATION} | Remote",
    "Financial Services | Blockchain Services | Software Development",
    "Full-time | Hybrid",
    "Product Manager | Senior Product Manager | Crypto Product Manager",
    "Yes",
    "Product manager with four years across fintech and crypto, now based in Dubai.",
    "CASUALLY_LOOKING",
)

# LinkedIn prepends this privacy notice to Connections.csv, before the real header row.
CONNECTIONS_PREAMBLE: tuple[tuple[str, ...], ...] = (
    ("Notes:",),
    (
        "When exporting your connection data, you may notice that some of the email addresses "
        "are missing. You will only see email addresses for connections who have allowed their "
        "connections to see or download their email address using this setting "
        "https://www.linkedin.com/psettings/privacy/email.",
    ),
    (),
)
