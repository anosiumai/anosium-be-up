from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta, date

from models.patient import Patient, Gender, BloodGroup
from repositories.base import BaseRepository

class PatientRepository(BaseRepository[Patient]):
    """Repository for Patient operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(Patient, db, tenant_id, current_user_id)
    
    def get_by_patient_code(self, patient_code: str) -> Optional[Patient]:
        """Get patient by patient code"""
        query = self.db.query(Patient).filter(Patient.patient_code == patient_code)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_phone(self, phone: str) -> Optional[Patient]:
        """Get patient by phone number"""
        query = self.db.query(Patient).filter(Patient.phone == phone)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def search_patients(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Patient]:
        """Search patients by name, phone, or patient code"""
        query = self.db.query(Patient).filter(
            or_(
                Patient.first_name.ilike(f"%{search_term}%"),
                Patient.last_name.ilike(f"%{search_term}%"),
                Patient.phone.ilike(f"%{search_term}%"),
                Patient.patient_code.ilike(f"%{search_term}%"),
                Patient.email.ilike(f"%{search_term}%")
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def get_by_gender(
        self,
        gender: Gender,
        skip: int = 0,
        limit: int = 100
    ) -> List[Patient]:
        """Get patients by gender"""
        query = self.db.query(Patient).filter(Patient.gender == gender)
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def get_by_age_range(
        self,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Patient]:
        """Get patients by age range"""
        today = date.today()
        
        conditions = []
        if min_age is not None:
            max_birth_date = today.replace(year=today.year - min_age)
            conditions.append(Patient.date_of_birth <= max_birth_date)
        
        if max_age is not None:
            min_birth_date = today.replace(year=today.year - max_age - 1)
            conditions.append(Patient.date_of_birth >= min_birth_date)
        
        query = self.db.query(Patient)
        query = self._apply_tenant_filter(query)
        
        if conditions:
            query = query.filter(and_(*conditions))
        
        return query.offset(skip).limit(limit).all()
    
    def get_recently_registered(
        self,
        days: int = 7,
        limit: int = 10
    ) -> List[Patient]:
        """Get recently registered patients"""
        since_date = date.today() - timedelta(days=days)
        
        query = self.db.query(Patient).filter(Patient.registration_date >= since_date)
        query = self._apply_tenant_filter(query)
        
        return query.order_by(Patient.registration_date.desc()).limit(limit).all()
    
    def count_by_gender(self) -> Dict[str, int]:
        """Count patients by gender"""
        query = self.db.query(
            Patient.gender,
            func.count(Patient.id).label('count')
        )
        query = self._apply_tenant_filter(query)
        
        results = query.group_by(Patient.gender).all()
        
        return {gender.value: count for gender, count in results}
    
    def count_by_age_group(self) -> Dict[str, int]:
        """Count patients by age group"""
        today = date.today()
        
        age_groups = {
            '0-18': (0, 18),
            '19-35': (19, 35),
            '36-50': (36, 50),
            '51-65': (51, 65),
            '66+': (66, 150)
        }
        
        results = {}
        for group_name, (min_age, max_age) in age_groups.items():
            max_birth_date = today.replace(year=today.year - min_age)
            min_birth_date = today.replace(year=today.year - max_age - 1)
            
            query = self.db.query(func.count(Patient.id))
            query = self._apply_tenant_filter(query)
            query = query.filter(
                and_(
                    Patient.date_of_birth <= max_birth_date,
                    Patient.date_of_birth >= min_birth_date
                )
            )
            
            results[group_name] = query.scalar()
        
        return results
    
    def generate_patient_code(self) -> str:
        """Generate unique patient code"""
        # Get count of patients in tenant
        query = self.db.query(func.count(Patient.id))
        query = self._apply_tenant_filter(query)
        count = query.scalar() or 0
        
        # Generate code: PAT-XXXXX
        return f"PAT-{count + 1:05d}"
    
    def check_duplicate(
        self,
        phone: str,
        email: Optional[str] = None,
        exclude_id: Optional[int] = None
    ) -> Optional[Patient]:
        """Check for duplicate patient by phone/email"""
        conditions = [Patient.phone == phone]
        
        if email:
            conditions.append(Patient.email == email)
        
        query = self.db.query(Patient).filter(or_(*conditions))
        query = self._apply_tenant_filter(query)
        
        if exclude_id:
            query = query.filter(Patient.id != exclude_id)
        
        return query.first()