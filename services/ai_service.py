"""
AI Automation Service Layer
Handles chatbot interactions, lead management, and intelligent automation
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import json
import re

from models.lead import Lead
from models.ai_lead import AIInteraction
from models.automation_rule import AutomationRule
from models.appointment import Appointment
from models.patient import Patient
from models.user import User
from models.clinic import Clinic
from models.base import LeadStatus, LeadSource, UserRole

from schemas.doctor import LeadCreate, ChatbotMessage, ChatbotResponse
from schemas.doctor import AIInteractionCreate


class AIAutomationService:
    """Service for AI-powered automation and lead management"""
    
    # Intent patterns for simple NLP
    INTENT_PATTERNS = {
        "appointment": [
            r"book.*appointment", r"schedule.*appointment", r"need.*appointment",
            r"want.*appointment", r"appointment.*booking", r"make.*appointment",
            r"set.*appointment", r"get.*appointment"
        ],
        "inquiry": [
            r"information", r"details", r"tell.*about", r"know.*about",
            r"what.*is", r"how.*does", r"can.*you", r"services",
            r"pricing", r"cost", r"price"
        ],
        "emergency": [
            r"emergency", r"urgent", r"asap", r"immediately", r"right.*now",
            r"critical", r"severe.*pain", r"accident"
        ],
        "complaint": [
            r"complaint", r"issue", r"problem", r"not.*happy", r"dissatisfied",
            r"disappointed", r"bad.*experience"
        ],
        "greeting": [
            r"^hi$", r"^hello$", r"^hey$", r"^good.*morning", r"^good.*afternoon",
            r"^good.*evening", r"greetings"
        ]
    }
    
    @staticmethod
    def detect_intent(message: str) -> Tuple[str, float]:
        """
        Simple intent detection using pattern matching
        Returns (intent, confidence_score)
        """
        message_lower = message.lower().strip()
        
        for intent, patterns in AIAutomationService.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    # Simple confidence based on pattern match
                    confidence = 0.85 if len(message_lower.split()) <= 5 else 0.75
                    return intent, confidence
        
        # Default to inquiry if no match
        return "inquiry", 0.5
    
    @staticmethod
    def extract_entities(message: str) -> Dict[str, Any]:
        """
        Extract entities like phone, email, name, date from message
        """
        entities = {}
        
        # Extract phone number
        phone_pattern = r'\b\d{10,}\b|\b\+?\d[\d\s-]{9,}\b'
        phone_match = re.search(phone_pattern, message)
        if phone_match:
            entities["phone"] = phone_match.group()
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, message)
        if email_match:
            entities["email"] = email_match.group()
        
        # Extract date mentions
        date_patterns = [
            r'\btomorrow\b', r'\btoday\b', r'\bnext\s+week\b',
            r'\bmonday\b', r'\btuesday\b', r'\bwednesday\b',
            r'\bthursday\b', r'\bfriday\b', r'\bsaturday\b', r'\bsunday\b'
        ]
        for pattern in date_patterns:
            if re.search(pattern, message.lower()):
                entities["date_mention"] = re.search(pattern, message.lower()).group()
                break
        
        return entities
    
    @staticmethod
    def generate_response(
        intent: str,
        entities: Dict[str, Any],
        clinic: Clinic
    ) -> str:
        """
        Generate appropriate response based on intent
        """
        clinic_name = clinic.name
        
        responses = {
            "greeting": f"Hello! Welcome to {clinic_name}. How can I assist you today?",
            
            "appointment": (
                f"I'd be happy to help you schedule an appointment at {clinic_name}. "
                f"Could you please provide your preferred date and time? "
                f"Our working hours are typically 9 AM to 6 PM, Monday through Friday."
            ),
            
            "inquiry": (
                f"Thank you for your interest in {clinic_name}. "
                f"We offer a wide range of medical services. "
                f"What specific information would you like to know about?"
            ),
            
            "emergency": (
                f"I understand this is urgent. For immediate medical emergencies, "
                f"please call our emergency line or visit the nearest emergency room. "
                f"If this is not a life-threatening emergency, I can help you schedule "
                f"an urgent appointment. How can I help?"
            ),
            
            "complaint": (
                f"I apologize for any inconvenience you've experienced at {clinic_name}. "
                f"Your feedback is important to us. Could you please share more details "
                f"so we can address your concerns properly?"
            )
        }
        
        return responses.get(intent, f"Thank you for contacting {clinic_name}. How may I assist you?")
    
    @staticmethod
    def process_chatbot_message(
        db: Session,
        clinic_id: int,
        message_data: ChatbotMessage
    ) -> ChatbotResponse:
        """
        Main chatbot processing function
        Handles intent detection, entity extraction, and response generation
        """
        start_time = datetime.utcnow()
        
        # Get clinic
        clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
        if not clinic:
            return ChatbotResponse(
                response="Sorry, clinic not found.",
                confidence=0.0,
                next_steps=[]
            )
        
        # Check if AI is enabled for clinic
        if not clinic.ai_config.get("enabled", False):
            return ChatbotResponse(
                response=f"Thank you for contacting {clinic.name}. Our team will get back to you soon.",
                confidence=1.0,
                next_steps=["Manual follow-up required"]
            )
        
        # Detect intent
        intent, confidence = AIAutomationService.detect_intent(message_data.message)
        
        # Extract entities
        entities = AIAutomationService.extract_entities(message_data.message)
        
        # Find or create lead
        lead = None
        if message_data.phone:
            lead = db.query(Lead).filter(
                and_(
                    Lead.clinic_id == clinic_id,
                    Lead.phone == message_data.phone
                )
            ).first()
        
        if not lead and message_data.phone:
            # Create new lead
            lead = Lead(
                clinic_id=clinic_id,
                name=message_data.name or "Unknown",
                phone=message_data.phone,
                email=entities.get("email"),
                source=message_data.platform,
                status=LeadStatus.NEW,
                initial_message=message_data.message,
                conversation_history=[{
                    "role": "user",
                    "message": message_data.message,
                    "timestamp": datetime.utcnow().isoformat()
                }],
                intent=intent,
                custom_metadata=message_data.metadata or {}
            )
            db.add(lead)
            db.flush()
        
        # Generate response
        response_text = AIAutomationService.generate_response(intent, entities, clinic)
        
        # Update lead conversation
        if lead:
            lead.conversation_history.append({
                "role": "assistant",
                "message": response_text,
                "timestamp": datetime.utcnow().isoformat()
            })
            lead.ai_responses += 1
            lead.intent = intent
            lead.last_contacted = datetime.utcnow()
            
            # Update status
            if lead.status == LeadStatus.NEW:
                lead.status = LeadStatus.CONTACTED
            
            lead.updated_at = datetime.utcnow()
        
        # Record AI interaction
        response_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        interaction = AIInteraction(
            clinic_id=clinic_id,
            lead_id=lead.id if lead else None,
            platform=message_data.platform.value,
            message_type="text",
            user_message=message_data.message,
            ai_response=response_text,
            intent_detected=intent,
            entities_extracted=entities,
            confidence_score=confidence,
            action_taken="response_generated",
            response_time_ms=response_time
        )
        db.add(interaction)
        
        db.commit()
        
        # Determine next steps
        next_steps = []
        if intent == "appointment":
            next_steps.append("Collect appointment details")
            next_steps.append("Check doctor availability")
        elif intent == "emergency":
            next_steps.append("Escalate to staff immediately")
        elif intent == "inquiry":
            next_steps.append("Provide service details")
        
        return ChatbotResponse(
            response=response_text,
            lead_id=lead.id if lead else None,
            action_taken="response_generated",
            confidence=confidence,
            next_steps=next_steps
        )
    
    @staticmethod
    def create_lead_manually(db: Session, clinic_id: int, lead_data: LeadCreate) -> Lead:
        """Create a lead manually"""
        lead = Lead(
            clinic_id=clinic_id,
            name=lead_data.name,
            phone=lead_data.phone,
            email=lead_data.email,
            source=lead_data.source,
            status=LeadStatus.NEW,
            initial_message=lead_data.initial_message,
            conversation_history=[],
            intent=lead_data.intent,
            preferred_doctor=lead_data.preferred_doctor,
            preferred_date=lead_data.preferred_date,
            service_interest=lead_data.service_interest,
            custom_metadata=lead_data.metadata or {}
        )
        
        db.add(lead)
        db.commit()
        db.refresh(lead)
        
        return lead
    
    @staticmethod
    def convert_lead_to_patient(
        db: Session,
        clinic_id: int,
        lead_id: int
    ) -> Optional[Patient]:
        """Convert a qualified lead to patient"""
        lead = db.query(Lead).filter(
            and_(Lead.id == lead_id, Lead.clinic_id == clinic_id)
        ).first()
        
        if not lead or lead.converted_to_patient:
            return None
        
        # Check if patient already exists with this phone
        existing_patient = db.query(Patient).filter(
            and_(
                Patient.clinic_id == clinic_id,
                Patient.phone == lead.phone
            )
        ).first()
        
        if existing_patient:
            lead.converted_to_patient = True
            lead.patient_id = existing_patient.id
            lead.converted_at = datetime.utcnow()
            lead.status = LeadStatus.CONVERTED
            db.commit()
            return existing_patient
        
        # Create new patient
        from services.multi_clinic import MultiClinicService  # Updated import
        
        name_parts = lead.name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Generate patient code
        patient_code = f"P{clinic_id}{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        patient = Patient(
            clinic_id=clinic_id,
            patient_code=patient_code,
            first_name=first_name,
            last_name=last_name,
            email=lead.email,
            phone=lead.phone,
            medical_history=[{
                "note": "Converted from lead",
                "date": datetime.utcnow().isoformat(),
                "source": lead.source.value
            }]
        )
        
        db.add(patient)
        db.flush()
        
        # Update lead
        lead.converted_to_patient = True
        lead.patient_id = patient.id
        lead.converted_at = datetime.utcnow()
        lead.status = LeadStatus.CONVERTED
        
        db.commit()
        db.refresh(patient)
        
        return patient
    
    @staticmethod
    def list_leads(
        db: Session,
        clinic_id: int,
        status: Optional[LeadStatus] = None,
        source: Optional[LeadSource] = None,
        from_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Lead]:
        """List leads with filters"""
        query = db.query(Lead).filter(Lead.clinic_id == clinic_id)
        
        if status:
            query = query.filter(Lead.status == status)
        
        if source:
            query = query.filter(Lead.source == source)
        
        if from_date:
            query = query.filter(Lead.created_at >= from_date)
        
        return query.order_by(Lead.created_at.desc()).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_leads_for_follow_up(db: Session, clinic_id: int) -> List[Lead]:
        """Get leads that need follow-up"""
        return db.query(Lead).filter(
            and_(
                Lead.clinic_id == clinic_id,
                Lead.status.in_([LeadStatus.NEW, LeadStatus.CONTACTED, LeadStatus.QUALIFIED]),
                Lead.next_follow_up <= datetime.utcnow()
            )
        ).order_by(Lead.next_follow_up).all()
    
    @staticmethod
    def update_lead_status(
        db: Session,
        clinic_id: int,
        lead_id: int,
        new_status: LeadStatus,
        notes: Optional[str] = None
    ) -> Optional[Lead]:
        """Update lead status"""
        lead = db.query(Lead).filter(
            and_(Lead.id == lead_id, Lead.clinic_id == clinic_id)
        ).first()
        
        if not lead:
            return None
        
        lead.status = new_status
        lead.last_contacted = datetime.utcnow()
        
        if notes:
            lead.conversation_history.append({
                "role": "staff",
                "message": f"Status update: {notes}",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        lead.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(lead)
        
        return lead
    
    @staticmethod
    def get_ai_stats(db: Session, clinic_id: int, days: int = 30) -> Dict[str, Any]:
        """Get AI automation statistics"""
        from_date = datetime.utcnow() - timedelta(days=days)
        
        # Total interactions
        total_interactions = db.query(func.count(AIInteraction.id)).filter(
            and_(
                AIInteraction.clinic_id == clinic_id,
                AIInteraction.created_at >= from_date
            )
        ).scalar()
        
        # Average response time
        avg_response_time = db.query(func.avg(AIInteraction.response_time_ms)).filter(
            and_(
                AIInteraction.clinic_id == clinic_id,
                AIInteraction.created_at >= from_date
            )
        ).scalar() or 0
        
        # Leads created
        leads_created = db.query(func.count(Lead.id)).filter(
            and_(
                Lead.clinic_id == clinic_id,
                Lead.created_at >= from_date
            )
        ).scalar()
        
        # Conversion rate
        converted_leads = db.query(func.count(Lead.id)).filter(
            and_(
                Lead.clinic_id == clinic_id,
                Lead.created_at >= from_date,
                Lead.converted_to_patient == True
            )
        ).scalar()
        
        conversion_rate = (converted_leads / leads_created * 100) if leads_created > 0 else 0
        
        # Intent distribution
        intent_stats = db.query(
            AIInteraction.intent_detected,
            func.count(AIInteraction.id)
        ).filter(
            and_(
                AIInteraction.clinic_id == clinic_id,
                AIInteraction.created_at >= from_date
            )
        ).group_by(AIInteraction.intent_detected).all()
        
        intent_distribution = {intent: count for intent, count in intent_stats}
        
        return {
            "total_interactions": total_interactions,
            "average_response_time_ms": round(avg_response_time, 2),
            "leads_created": leads_created,
            "leads_converted": converted_leads,
            "conversion_rate": round(conversion_rate, 2),
            "intent_distribution": intent_distribution,
            "period_days": days
        }
    
    @staticmethod
    def schedule_follow_up(
        db: Session,
        clinic_id: int,
        lead_id: int,
        follow_up_date: datetime
    ) -> Optional[Lead]:
        """Schedule follow-up for a lead"""
        lead = db.query(Lead).filter(
            and_(Lead.id == lead_id, Lead.clinic_id == clinic_id)
        ).first()
        
        if not lead:
            return None
        
        lead.next_follow = follow_up_date  # Updated field name
        lead.follow_up_count += 1
        lead.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(lead)
        
        return lead