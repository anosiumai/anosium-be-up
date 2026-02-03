from typing import Optional, Dict, Any, Set
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.ai_lead import AILead, AIInteraction, LeadStatus, LeadSource
from models.patient import Patient
from models.user import User
from schemas.ai_lead import (
    AILeadCreate,
    AILeadUpdate,
    AIInteractionCreate,
    LeadConversion,
)
from repositories.ai_lead import AILeadRepository, AIInteractionRepository


# ---------------------------------------------------------------------------
# Allowed status transitions  (source → set of valid targets)
# ---------------------------------------------------------------------------
_VALID_TRANSITIONS: Dict[LeadStatus, Set[LeadStatus]] = {
    LeadStatus.NEW: {
        LeadStatus.CONTACTED,
        LeadStatus.QUALIFIED,
        LeadStatus.APPOINTMENT_SCHEDULED,
        LeadStatus.CONVERTED,
        LeadStatus.LOST,
    },
    LeadStatus.CONTACTED: {
        LeadStatus.QUALIFIED,
        LeadStatus.APPOINTMENT_SCHEDULED,
        LeadStatus.CONVERTED,
        LeadStatus.LOST,
    },
    LeadStatus.QUALIFIED: {
        LeadStatus.APPOINTMENT_SCHEDULED,
        LeadStatus.CONVERTED,
        LeadStatus.LOST,
    },
    LeadStatus.APPOINTMENT_SCHEDULED: {
        LeadStatus.CONVERTED,
        LeadStatus.LOST,
    },
    # terminal states – no outgoing edges
    LeadStatus.CONVERTED: set(),
    LeadStatus.LOST: set(),
}

# Statuses from which a lead may legally be converted to a patient.
_CONVERTIBLE_STATUSES: Set[LeadStatus] = {
    LeadStatus.NEW,
    LeadStatus.CONTACTED,
    LeadStatus.QUALIFIED,
    LeadStatus.APPOINTMENT_SCHEDULED,
}

# Default hours until the next follow-up is due after an outbound (bot) message.
_DEFAULT_FOLLOW_UP_HOURS: int = 24


class AILeadService:
    """Service layer for AI-lead lifecycle and conversion logic."""

    def __init__(
        self,
        db: Session,
        tenant_id: int,
        current_user_id: Optional[int] = None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.current_user_id = current_user_id

        self.lead_repo = AILeadRepository(db, tenant_id, current_user_id)
        self.interaction_repo = AIInteractionRepository(db, tenant_id, current_user_id)

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _get_lead(self, lead_id: int) -> Optional[AILead]:
        """Fetch lead with interactions; tenant-scoped via the repository."""
        return self.lead_repo.get_with_interactions(lead_id)

    def _validate_status_transition(self, current: LeadStatus, target: LeadStatus) -> None:
        """Raise ValueError when *current → target* is not in the transition graph."""
        if current == target:
            return  # no-op is always fine

        allowed = _VALID_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise ValueError(
                f"Cannot transition lead from '{current.value}' to '{target.value}'. "
                f"Allowed transitions: {[s.value for s in allowed] or 'none (terminal state)'}"
            )

    def _validate_user_in_tenant(self, user_id: int) -> User:
        """Ensure the target user exists and belongs to this tenant."""
        user = (
            self.db.query(User)
            .filter(User.id == user_id, User.tenant_id == self.tenant_id)
            .first()
        )
        if not user:
            raise ValueError(f"User with id {user_id} not found in this tenant")
        return user

    # ------------------------------------------------------------------
    # create  (with phone-based deduplication)
    # ------------------------------------------------------------------

    def create_lead(self, lead_in: AILeadCreate) -> AILead:
        """
        Create a new lead **or** surface an existing one when the same phone
        number is already known within the tenant.

        Deduplication rules
        -------------------
        * If an existing lead with the same phone is in a non-terminal state
          (anything other than CONVERTED / LOST) we return that lead directly
          and append the incoming message as a new interaction.  This keeps the
          funnel clean without silently dropping chatbot callbacks.
        * If the existing lead is terminal (CONVERTED / LOST) we create a
          brand-new lead row so the pipeline can be re-entered independently.
        """
        # --- dedup check --------------------------------------------------
        existing = self.lead_repo.get_by_phone(lead_in.phone)
        if existing and existing.status not in (LeadStatus.CONVERTED, LeadStatus.LOST):
            # Append the new message as an interaction on the existing lead
            if lead_in.message:
                interaction = AIInteraction(
                    lead_id=existing.id,
                    message_type="user",
                    message_content=lead_in.message,
                    platform=lead_in.source.value,
                    intent_detected=lead_in.ai_intent,
                    entities_extracted={},
                )
                self.db.add(interaction)
                self.db.commit()
                self.db.refresh(existing)
            return existing

        # --- new lead -----------------------------------------------------
        lead = AILead(
            tenant_id=self.tenant_id,
            name=lead_in.name,
            phone=lead_in.phone,
            email=lead_in.email,
            source=lead_in.source,
            source_details=lead_in.source_details or {},
            message=lead_in.message,
            tags=lead_in.tags,
            interested_in=lead_in.interested_in,
            status=LeadStatus.NEW,
            ai_sentiment=lead_in.ai_sentiment,
            ai_intent=lead_in.ai_intent,
            ai_suggested_action=lead_in.ai_suggested_action,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    # ------------------------------------------------------------------
    # read
    # ------------------------------------------------------------------

    def get_lead_with_interactions(self, lead_id: int) -> Optional[AILead]:
        """Single lead with full interaction history eager-loaded."""
        return self._get_lead(lead_id)

    def get_leads(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Paginated lead listing.

        ``filters`` may contain any of: ``status``, ``source``, ``assigned_to``.
        Returns ``{"items": [...], "total": int}``.
        """
        filters = filters or {}

        query = self.db.query(AILead).filter(AILead.tenant_id == self.tenant_id)

        if "status" in filters:
            query = query.filter(AILead.status == filters["status"])

        if "source" in filters:
            query = query.filter(AILead.source == filters["source"])

        if "assigned_to" in filters:
            query = query.filter(AILead.assigned_to == filters["assigned_to"])

        total = query.count()

        items = (
            query.order_by(desc(AILead.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {"items": items, "total": total}

    # ------------------------------------------------------------------
    # update
    # ------------------------------------------------------------------

    def update_lead(self, lead_id: int, lead_in: AILeadUpdate) -> Optional[AILead]:
        """
        Partial update with validated status transitions.

        If ``assigned_to`` is being changed the target user is validated
        against the tenant.  If ``status`` is being changed the transition
        graph is enforced.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            return None

        update_data = lead_in.model_dump(exclude_unset=True)

        # --- status transition validation ---------------------------------
        new_status = update_data.get("status")
        if new_status and new_status != lead.status:
            self._validate_status_transition(lead.status, new_status)

        # --- assigned_to validation ---------------------------------------
        new_assignee = update_data.get("assigned_to")
        if new_assignee is not None:
            self._validate_user_in_tenant(new_assignee)

        # --- apply ------------------------------------------------------------
        for key, value in update_data.items():
            setattr(lead, key, value)

        # If status just moved to CONTACTED, stamp last_contacted_at
        if new_status == LeadStatus.CONTACTED and lead.last_contacted_at is None:
            lead.last_contacted_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(lead)
        return lead

    # ------------------------------------------------------------------
    # interactions
    # ------------------------------------------------------------------

    def add_interaction(self, lead_id: int, interaction_in: AIInteractionCreate) -> AIInteraction:
        """
        Append a chatbot interaction to a lead's history.

        Side-effects
        ------------
        * If ``message_type == "bot"`` (outbound) we stamp ``last_contacted_at``
          and schedule the next follow-up ``_DEFAULT_FOLLOW_UP_HOURS`` from now.
        * ``follow_up_count`` is incremented on every outbound message.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead with id {lead_id} not found")

        interaction = AIInteraction(
            lead_id=lead_id,
            message_type=interaction_in.message_type,
            message_content=interaction_in.message_content,
            platform=interaction_in.platform,
            intent_detected=interaction_in.intent_detected,
            entities_extracted=interaction_in.entities_extracted or {},
        )
        self.db.add(interaction)

        # --- outbound-message side-effects --------------------------------
        if interaction_in.message_type == "bot":
            now = datetime.utcnow()
            lead.last_contacted_at = now
            lead.next_follow_up_at = now + timedelta(hours=_DEFAULT_FOLLOW_UP_HOURS)
            lead.follow_up_count = (lead.follow_up_count or 0) + 1

            # Auto-advance NEW → CONTACTED on first outbound touch
            if lead.status == LeadStatus.NEW:
                lead.status = LeadStatus.CONTACTED

        self.db.commit()
        self.db.refresh(interaction)
        return interaction

    # ------------------------------------------------------------------
    # assignment
    # ------------------------------------------------------------------

    def assign_lead(self, lead_id: int, user_id: int) -> bool:
        """
        Assign (or re-assign) a lead to a staff member.

        * Validates the target user exists within the tenant.
        * Auto-advances ``NEW → CONTACTED`` and stamps ``last_contacted_at``
          so the lead doesn't sit invisible in the NEW bucket after a human
          picks it up.

        Returns ``False`` when the lead itself is not found (router maps this
        to 404); raises ``ValueError`` for user-validation failures (400).
        """
        lead = self._get_lead(lead_id)
        if not lead:
            return False

        self._validate_user_in_tenant(user_id)

        lead.assigned_to = user_id

        if lead.status == LeadStatus.NEW:
            lead.status = LeadStatus.CONTACTED
            lead.last_contacted_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(lead)
        return True

    # ------------------------------------------------------------------
    # conversion  (lead → patient)
    # ------------------------------------------------------------------

    def convert_to_patient(self, lead_id: int, conversion_data: LeadConversion) -> Patient:
        """
        Convert a qualified lead into a ``Patient`` row.

        Validation
        ----------
        * Lead must exist and be in a convertible status (not CONVERTED/LOST).
        * When ``create_patient=True`` and ``patient_data`` is supplied the
          service creates the Patient from that payload.  When ``patient_data``
          is ``None`` it builds a minimal Patient from the lead's own name /
          phone / email so the conversion can still succeed without a full
          intake form.
        * When ``create_patient=False`` the caller is expected to have already
          created the patient — but we still need a patient_id.  In that case
          we look up an existing patient by phone within the tenant; raise if
          none is found.

        Side-effects
        ------------
        * ``status`` → CONVERTED, ``converted_at`` stamped, ``patient_id``
          linked on the lead row.
        """
        lead = self._get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead with id {lead_id} not found")

        if lead.status not in _CONVERTIBLE_STATUSES:
            raise ValueError(
                f"Lead is in status '{lead.status.value}' and cannot be converted. "
                f"Only leads in {[s.value for s in _CONVERTIBLE_STATUSES]} can be converted."
            )

        # --- resolve or create the Patient ---------------------------------
        if conversion_data.create_patient:
            patient = self._create_patient_from_lead(lead, conversion_data)
        else:
            # Caller says patient already exists — look up by phone
            patient = (
                self.db.query(Patient)
                .filter(
                    Patient.phone == lead.phone,
                    Patient.tenant_id == self.tenant_id,
                )
                .first()
            )
            if not patient:
                raise ValueError(
                    "create_patient is False but no existing patient was found "
                    f"matching phone '{lead.phone}' in this tenant"
                )

        # --- mark lead as converted ---------------------------------------
        lead.status = LeadStatus.CONVERTED
        lead.patient_id = patient.id
        lead.converted_at = datetime.utcnow()
        lead.conversion_notes = conversion_data.conversion_notes

        self.db.commit()
        self.db.refresh(lead)
        return patient

    # ------------------------------------------------------------------
    # private: patient creation helper
    # ------------------------------------------------------------------

    def _create_patient_from_lead(
        self, lead: AILead, conversion_data: LeadConversion
    ) -> Patient:
        """
        Build and persist a Patient row.

        If ``conversion_data.patient_data`` (a full ``PatientCreate``) is
        provided we honour every field in it.  Otherwise we fall back to the
        minimal set of fields available on the lead itself.
        """
        if conversion_data.patient_data:
            # Full PatientCreate supplied — use it directly.
            # PatientCreate is a Pydantic model; dump to dict and unpack into
            # the ORM constructor so we stay decoupled from the exact field set.
            patient_kwargs = conversion_data.patient_data.model_dump()
        else:
            # Minimal fallback from lead data
            patient_kwargs = {
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
            }

        # Ensure tenant is stamped regardless of the source
        patient_kwargs["tenant_id"] = self.tenant_id

        patient = Patient(**patient_kwargs)
        self.db.add(patient)
        self.db.flush()  # get patient.id without committing the whole conversion yet
        return patient