"""
Source registry model — defines monitored government websites.

Person 1 (Aditya) — Ingestion & Source Verification
"""

from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from lib.dates import utcnow


class CrawlPolicy(BaseModel):
    """Crawl behaviour settings, nested inside Source."""
    max_pages_per_run: int = 10
    request_delay_seconds: int = 5
    max_documents_per_run: int = 50
    respect_robots: bool = True
    stop_on_403: bool = True
    stop_on_429: bool = True


class Source(BaseModel):
    """
    A government website source configuration.

    `source_id` is the canonical identifier used throughout the pipeline
    (e.g. "pib", "karnataka_egazette").
    """
    source_id: str = Field(..., description="Unique source identifier, e.g. 'pib'")
    name: str = Field(..., description="Human-readable name")
    base_domains: list[str] = Field(default_factory=list)
    seed_urls: list[str] = Field(default_factory=list)
    adapter: str = Field(..., description="Crawler adapter key, e.g. 'pib'")
    government_level: str = Field(..., description="'central' or 'state'")
    state: str | None = None
    allowed_document_types: list[str] = Field(
        default_factory=list,
        description="e.g. ['press_release', 'circular', 'notification']",
    )
    allowed_path_patterns: list[str] = Field(
        default_factory=list,
        description="URL path prefixes/patterns this adapter may follow",
    )
    crawl_policy: CrawlPolicy = Field(default_factory=CrawlPolicy)
    status: str = Field(default="active", description="'active' | 'paused' | 'disabled'")

    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def to_crawler_config(self) -> dict:
        """
        Flatten the Source into the dict shape that BaseCrawlerAdapter expects.
        Keeps backward-compatibility with adapter code that reads source_config keys directly.
        """
        return {
            "source_id": self.source_id,
            "name": self.name,
            "base_domains": self.base_domains,
            "seed_urls": self.seed_urls,
            "adapter": self.adapter,
            "government_level": self.government_level,
            "state": self.state,
            "allowed_document_types": self.allowed_document_types,
            "allowed_path_patterns": self.allowed_path_patterns,
            # Flatten crawl_policy so adapters can read stop_on_403 etc. directly
            "enabled": self.status == "active",
            "max_pages_per_run": self.crawl_policy.max_pages_per_run,
            "request_delay_seconds": self.crawl_policy.request_delay_seconds,
            "max_documents_per_run": self.crawl_policy.max_documents_per_run,
            "respect_robots": self.crawl_policy.respect_robots,
            "stop_on_403": self.crawl_policy.stop_on_403,
            "stop_on_429": self.crawl_policy.stop_on_429,
        }


# ─── PIB seed entry ───────────────────────────────────────────────────────────
# Canonical seed for the Press Information Bureau (Day-1 target).
# Insert this into the `sources` collection on first startup.

PIB_SOURCE = Source(
    source_id="pib",
    name="Press Information Bureau",
    base_domains=["pib.gov.in", "www.pib.gov.in", "static.pib.gov.in"],
    seed_urls=[
        "https://www.pib.gov.in/Allrel.aspx?reg=48&lang=1",
    ],
    adapter="pib",
    government_level="central",
    state=None,
    allowed_document_types=["press_release", "fact_sheet", "press_note"],
    allowed_path_patterns=[
        "/PressReleaseDetail.aspx",
        "/FactsheetDetails.aspx",
        "/PressNoteDetails.aspx",
        "/Allrel.aspx",
    ],
    crawl_policy=CrawlPolicy(
        max_pages_per_run=5,
        request_delay_seconds=5,
        max_documents_per_run=50,
        respect_robots=True,
        stop_on_403=True,
        stop_on_429=True,
    ),
    status="active",
)


# ─── New Karnataka / education source seeds ──────────────────────────────────

_KA_POLICY = CrawlPolicy(
    max_pages_per_run=3,
    request_delay_seconds=3,
    max_documents_per_run=30,
    respect_robots=True,
    stop_on_403=True,
    stop_on_429=True,
)

# ── Drupal-CMS sources ────────────────────────────────────────────────────────

BESCOM_SOURCE = Source(
    source_id="bescom", name="BESCOM", adapter="drupal_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["bescom.karnataka.gov.in", "www.bescom.karnataka.gov.in"],
    seed_urls=["https://bescom.karnataka.gov.in/43/circulars/en"],
    allowed_document_types=["circular", "order", "notification"],
    crawl_policy=_KA_POLICY, status="active",
)

KPTCL_SOURCE = Source(
    source_id="kptcl", name="KPTCL", adapter="drupal_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["kptcl.karnataka.gov.in", "www.kptcl.karnataka.gov.in"],
    seed_urls=["https://kptcl.karnataka.gov.in/5/tender-and-procurement/en"],
    allowed_document_types=["order", "circular", "notification"],
    crawl_policy=_KA_POLICY, status="active",
)

KERC_SOURCE = Source(
    source_id="kerc", name="KERC", adapter="drupal_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["kerc.karnataka.gov.in", "www.kerc.karnataka.gov.in"],
    seed_urls=["https://kerc.karnataka.gov.in/42/miscellaneous-orders/en"],
    allowed_document_types=["order", "circular"],
    crawl_policy=_KA_POLICY, status="active",
)

MESCOM_SOURCE = Source(
    source_id="mescom", name="MESCOM", adapter="drupal_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["mescom.karnataka.gov.in", "www.mescom.karnataka.gov.in"],
    seed_urls=["https://mescom.karnataka.gov.in/16/news-and-press-release/en"],
    allowed_document_types=["press_release", "circular", "notification"],
    crawl_policy=_KA_POLICY, status="active",
)

BWSSB_SOURCE = Source(
    source_id="bwssb", name="BWSSB", adapter="drupal_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["bwssb.karnataka.gov.in", "www.bwssb.karnataka.gov.in"],
    seed_urls=["https://bwssb.karnataka.gov.in/1/news-and-events/en"],
    allowed_document_types=["notification", "circular", "order"],
    crawl_policy=_KA_POLICY, status="active",
)

KUWSDB_SOURCE = Source(
    source_id="kuwsdb", name="KUWSDB", adapter="drupal_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["kuwsdb.karnataka.gov.in", "www.kuwsdb.karnataka.gov.in"],
    seed_urls=["https://kuwsdb.karnataka.gov.in/42/circulars-&-proceedings/en"],
    allowed_document_types=["circular", "order"],
    crawl_policy=_KA_POLICY, status="active",
)

KSPCB_SOURCE = Source(
    source_id="kspcb", name="KSPCB", adapter="drupal_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["kspcb.karnataka.gov.in", "www.kspcb.karnataka.gov.in"],
    seed_urls=["https://kspcb.karnataka.gov.in/index.php/consent-management/mines-and-stone-crusher-notifications-circulars"],
    allowed_document_types=["circular", "notification", "order"],
    crawl_policy=_KA_POLICY, status="active",
)

KSEAB_SOURCE = Source(
    source_id="kseab", name="KSEAB", adapter="drupal_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["kseab.karnataka.gov.in", "www.kseab.karnataka.gov.in"],
    seed_urls=["https://kseab.karnataka.gov.in/"],
    allowed_document_types=["circular", "notification", "order"],
    crawl_policy=_KA_POLICY, status="active",
)

# ── WordPress sources ─────────────────────────────────────────────────────────

VTU_SOURCE = Source(
    source_id="vtu", name="Visvesvaraya Technological University (VTU)",
    adapter="wordpress_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["vtu.ac.in", "www.vtu.ac.in"],
    seed_urls=["https://vtu.ac.in/ict-circular-notification/"],
    allowed_document_types=["circular", "notification"],
    crawl_policy=_KA_POLICY, status="active",
)

KARNATAKA_GOV_SOURCE = Source(
    source_id="karnataka_gov", name="Karnataka Government Portal",
    adapter="wordpress_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["karnataka.gov.in", "www.karnataka.gov.in"],
    seed_urls=["https://karnataka.gov.in/"],
    allowed_document_types=["circular", "notification", "order", "gazette_notification"],
    crawl_policy=_KA_POLICY, status="active",
)

# ── Individual sources ────────────────────────────────────────────────────────

SSP_KARNATAKA_SOURCE = Source(
    source_id="ssp_karnataka", name="SSP Karnataka",
    adapter="ssp_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["ssp.karnataka.gov.in", "www.ssp.karnataka.gov.in"],
    seed_urls=["https://ssp.karnataka.gov.in/"],
    allowed_document_types=["circular", "notification"],
    crawl_policy=_KA_POLICY, status="active",
)

SEVASINDHU_SOURCE = Source(
    source_id="sevasindhu", name="Seva Sindhu Karnataka",
    adapter="sevasindhu",
    government_level="state", state="Karnataka",
    base_domains=["sevasindhu.karnataka.gov.in", "www.sevasindhu.karnataka.gov.in"],
    seed_urls=["https://sevasindhu.karnataka.gov.in/"],
    allowed_document_types=["circular", "notification", "order"],
    crawl_policy=_KA_POLICY, status="active",
)

# Minimal/unknown structure — active but may find 0 docs until seed URLs improve
GBA_SOURCE = Source(
    source_id="gba", name="Greater Bengaluru Authority (GBA)",
    adapter="drupal_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["gba.karnataka.gov.in", "www.gba.karnataka.gov.in"],
    seed_urls=["https://gba.karnataka.gov.in/"],
    allowed_document_types=["circular", "notification", "order"],
    crawl_policy=_KA_POLICY, status="active",
)

KSRTC_SOURCE = Source(
    source_id="ksrtc", name="KSRTC",
    adapter="drupal_karnataka",
    government_level="state", state="Karnataka",
    base_domains=["ksrtc.in", "www.ksrtc.in"],
    seed_urls=["https://www.ksrtc.in/"],
    allowed_document_types=["circular", "notification", "order"],
    crawl_policy=_KA_POLICY, status="active",
)

# ── All sources list — used by server startup seed ────────────────────────────
ALL_NEW_SOURCES = [
    BESCOM_SOURCE, KPTCL_SOURCE, KERC_SOURCE, MESCOM_SOURCE,
    BWSSB_SOURCE, KUWSDB_SOURCE, KSPCB_SOURCE, KSEAB_SOURCE,
    VTU_SOURCE, KARNATAKA_GOV_SOURCE,
    SSP_KARNATAKA_SOURCE, SEVASINDHU_SOURCE,
    GBA_SOURCE, KSRTC_SOURCE,
]

# ─── Request / response models ────────────────────────────────────────────────

class CrawlRunRequest(BaseModel):
    """Body for POST /api/admin/sources/{source_id}/crawl."""
    max_pages: int = 5
    max_documents: int = 50


class CrawlRun(BaseModel):
    """Result / status record for a single crawler run."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    status: str = "pending"   # pending | running | completed | failed
    pages_fetched: int = 0
    documents_discovered: int = 0
    documents_new: int = 0
    documents_duplicate: int = 0
    blocked_requests: int = 0
    errors: list[dict] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
