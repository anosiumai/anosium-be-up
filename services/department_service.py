"""
Department Service
Handles all department-related operations including CRUD, head doctor assignment, and statistics
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import case, func, and_, or_

from models.department import Department
from models.doctor import Doctor
from models.user import User
from repositories.department import DepartmentRepository
from schemas.department import (
    DepartmentCreate, DepartmentUpdate, Department as DepartmentSchema,
    DepartmentWithDoctors
)


class DepartmentService:
    """Service for department operations"""
    
    def __init__(self, db: Session, tenant_id: int, current_user_id: int):
        self.db = db
        self.tenant_id = tenant_id
        self.current_user_id = current_user_id
        self.dept_repo = DepartmentRepository(db, tenant_id, current_user_id)
    
    # ============================================================================
    # CRUD OPERATIONS
    # ============================================================================
    
    def create_department(self, dept_in: DepartmentCreate) -> DepartmentSchema:
        """
        Create new department
        
        Args:
            dept_in: Department creation data
            
        Returns:
            Created department
            
        Raises:
            ValueError: If department code already exists or head doctor not found
        """
        # Check if code already exists
        if self.dept_repo.check_code_exists(dept_in.code.upper()):
            raise ValueError(f"Department code '{dept_in.code}' already exists")
        
        # Validate head doctor if provided
        if dept_in.head_doctor_id:
            head_doctor = (
                self.db.query(Doctor)
                .filter(
                    and_(
                        Doctor.id == dept_in.head_doctor_id,
                        Doctor.tenant_id == self.tenant_id,
                        Doctor.is_active == True
                    )
                )
                .first()
            )
            
            if not head_doctor:
                raise ValueError("Head doctor not found or inactive")
        
        # Create department
        department = Department(
            tenant_id=self.tenant_id,
            name=dept_in.name,
            code=dept_in.code.upper(),
            description=dept_in.description,
            head_doctor_id=dept_in.head_doctor_id,
            is_active=True
        )
        
        self.db.add(department)
        self.db.commit()
        self.db.refresh(department)
        
        return DepartmentSchema.from_orm(department)
    
    def get_department(self, department_id: int) -> Optional[DepartmentSchema]:
        """
        Get department by ID
        
        Args:
            department_id: Department ID
            
        Returns:
            Department or None if not found
        """
        department = self.dept_repo.get_with_head_doctor(department_id)
        
        if department:
            return DepartmentSchema.from_orm(department)
        
        return None
    
    def get_departments(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get list of departments with filtering
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Filter criteria
            
        Returns:
            Dictionary with items and total count
        """
        query = self.db.query(Department)
        
        # Apply tenant filter
        query = query.filter(Department.tenant_id == self.tenant_id)
        
        # Apply filters
        if filters:
            if 'is_active' in filters:
                query = query.filter(Department.is_active == filters['is_active'])
            
            if 'search' in filters:
                search_term = filters['search']
                query = query.filter(
                    or_(
                        Department.name.ilike(f"%{search_term}%"),
                        Department.code.ilike(f"%{search_term}%")
                    )
                )
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        departments = query.order_by(Department.name).offset(skip).limit(limit).all()
        
        return {
            'items': [DepartmentSchema.from_orm(dept) for dept in departments],
            'total': total
        }
    
    def update_department(
        self,
        department_id: int,
        dept_in: DepartmentUpdate
    ) -> Optional[DepartmentSchema]:
        """
        Update department
        
        Args:
            department_id: Department ID
            dept_in: Update data
            
        Returns:
            Updated department or None if not found
            
        Raises:
            ValueError: If code already exists or head doctor not found
        """
        department = self.dept_repo.get(department_id)
        
        if not department:
            return None
        
        # Check if code is being changed and already exists
        if dept_in.code and dept_in.code != department.code:
            if self.dept_repo.check_code_exists(dept_in.code.upper(), exclude_id=department_id):
                raise ValueError(f"Department code '{dept_in.code}' already exists")
        
        # Validate head doctor if being changed
        if dept_in.head_doctor_id is not None:
            if dept_in.head_doctor_id:  # Not setting to None
                head_doctor = (
                    self.db.query(Doctor)
                    .filter(
                        and_(
                            Doctor.id == dept_in.head_doctor_id,
                            Doctor.tenant_id == self.tenant_id,
                            Doctor.is_active == True
                        )
                    )
                    .first()
                )
                
                if not head_doctor:
                    raise ValueError("Head doctor not found or inactive")
        
        # Update fields
        update_data = dept_in.dict(exclude_unset=True)
        
        # Uppercase code if present
        if 'code' in update_data:
            update_data['code'] = update_data['code'].upper()
        
        for field, value in update_data.items():
            setattr(department, field, value)
        
        self.db.commit()
        self.db.refresh(department)
        
        return DepartmentSchema.from_orm(department)
    
    def delete_department(self, department_id: int, soft: bool = True) -> bool:
        """
        Delete department
        
        Args:
            department_id: Department ID
            soft: If True, perform soft delete (set is_active=False)
            
        Returns:
            True if deleted successfully, False if not found
            
        Raises:
            ValueError: If department has doctors and attempting hard delete
        """
        department = self.dept_repo.get(department_id)
        
        if not department:
            return False
        
        if soft:
            # Soft delete - mark as inactive
            department.is_active = False
            self.db.commit()
        else:
            # Hard delete - check for dependencies
            doctor_count = (
                self.db.query(func.count(Doctor.id))
                .filter(Doctor.department_id == department_id)
                .scalar() or 0
            )
            
            if doctor_count > 0:
                raise ValueError(
                    f"Cannot delete department with {doctor_count} doctors. "
                    "Use soft delete or reassign doctors first."
                )
            
            self.db.delete(department)
            self.db.commit()
        
        return True
    
    # ============================================================================
    # DEPARTMENT MANAGEMENT
    # ============================================================================
    
    def assign_head_doctor(
        self,
        department_id: int,
        doctor_id: int
    ) -> Optional[DepartmentSchema]:
        """
        Assign head doctor to department
        
        Args:
            department_id: Department ID
            doctor_id: Doctor ID to assign as head
            
        Returns:
            Updated department or None if not found
            
        Raises:
            ValueError: If doctor not found or doesn't belong to department
        """
        department = self.dept_repo.get(department_id)
        
        if not department:
            return None
        
        # Validate doctor
        doctor = (
            self.db.query(Doctor)
            .filter(
                and_(
                    Doctor.id == doctor_id,
                    Doctor.tenant_id == self.tenant_id,
                    Doctor.is_active == True
                )
            )
            .first()
        )
        
        if not doctor:
            raise ValueError("Doctor not found or inactive")
        
        # Check if doctor belongs to this department
        if doctor.department_id != department_id:
            raise ValueError(
                f"Doctor must belong to department '{department.name}' "
                f"to be assigned as head"
            )
        
        # Assign head doctor
        department.head_doctor_id = doctor_id
        
        self.db.commit()
        self.db.refresh(department)
        
        return DepartmentSchema.from_orm(department)
    
    def remove_head_doctor(self, department_id: int) -> Optional[DepartmentSchema]:
        """
        Remove head doctor from department
        
        Args:
            department_id: Department ID
            
        Returns:
            Updated department or None if not found
        """
        department = self.dept_repo.get(department_id)
        
        if not department:
            return None
        
        department.head_doctor_id = None
        
        self.db.commit()
        self.db.refresh(department)
        
        return DepartmentSchema.from_orm(department)
    
    def get_department_with_doctors(
        self,
        department_id: int
    ) -> Optional[DepartmentWithDoctors]:
        """
        Get department with list of doctors
        
        Args:
            department_id: Department ID
            
        Returns:
            Department with doctors or None if not found
        """
        department = self.dept_repo.get_with_doctors(department_id)
        
        if not department:
            return None
        
        # Count active doctors
        active_doctors = sum(1 for d in department.doctors if d.is_active)
        
        # Create response
        dept_dict = DepartmentSchema.from_orm(department).dict()
        dept_dict['doctors'] = department.doctors
        dept_dict['total_doctors'] = len(department.doctors)
        dept_dict['active_doctors'] = active_doctors
        
        return DepartmentWithDoctors(**dept_dict)
    
    def reassign_doctors(
        self,
        from_department_id: int,
        to_department_id: int,
        doctor_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Reassign doctors from one department to another
        
        Args:
            from_department_id: Source department ID
            to_department_id: Target department ID
            doctor_ids: Optional list of specific doctor IDs to reassign
                       If None, reassigns all doctors
            
        Returns:
            Dictionary with reassignment results
            
        Raises:
            ValueError: If departments not found or same
        """
        # Validate departments
        from_dept = self.dept_repo.get(from_department_id)
        to_dept = self.dept_repo.get(to_department_id)
        
        if not from_dept or not to_dept:
            raise ValueError("Department not found")
        
        if from_department_id == to_department_id:
            raise ValueError("Cannot reassign to the same department")
        
        # Build query for doctors to reassign
        query = self.db.query(Doctor).filter(
            and_(
                Doctor.department_id == from_department_id,
                Doctor.tenant_id == self.tenant_id
            )
        )
        
        if doctor_ids:
            query = query.filter(Doctor.id.in_(doctor_ids))
        
        doctors = query.all()
        
        if not doctors:
            return {
                'reassigned_count': 0,
                'doctor_ids': [],
                'message': 'No doctors found to reassign'
            }
        
        # Reassign doctors
        reassigned_ids = []
        for doctor in doctors:
            doctor.department_id = to_department_id
            reassigned_ids.append(doctor.id)
        
        self.db.commit()
        
        return {
            'reassigned_count': len(reassigned_ids),
            'doctor_ids': reassigned_ids,
            'from_department': from_dept.name,
            'to_department': to_dept.name,
            'message': f'Successfully reassigned {len(reassigned_ids)} doctors'
        }
    
    # ============================================================================
    # STATISTICS AND REPORTING
    # ============================================================================
    
    def get_department_statistics(
        self,
        department_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get department statistics
        
        Args:
            department_id: Department ID
            
        Returns:
            Statistics dictionary or None if department not found
        """
        department = self.dept_repo.get(department_id)
        
        if not department:
            return None
        
        # Count doctors
        doctor_stats = (
            self.db.query(
                func.count(Doctor.id).label('total'),
                func.sum(case((Doctor.is_active == True, 1), else_=0)).label('active'),
                func.sum(case((Doctor.is_available == True, 1), else_=0)).label('available')
            )
            .filter(Doctor.department_id == department_id)
            .first()
        )
        
        # Count specializations
        specializations = (
            self.db.query(
                Doctor.specialization,
                func.count(Doctor.id).label('count')
            )
            .filter(
                and_(
                    Doctor.department_id == department_id,
                    Doctor.is_active == True
                )
            )
            .group_by(Doctor.specialization)
            .all()
        )
        
        # Get head doctor info
        head_doctor_info = None
        if department.head_doctor_id:
            head_doctor = (
                self.db.query(Doctor)
                .join(User)
                .filter(Doctor.id == department.head_doctor_id)
                .first()
            )
            
            if head_doctor:
                head_doctor_info = {
                    'id': head_doctor.id,
                    'name': f"{head_doctor.user.first_name} {head_doctor.user.last_name}",
                    'specialization': head_doctor.specialization
                }
        
        return {
            'department_id': department_id,
            'department_name': department.name,
            'department_code': department.code,
            'total_doctors': doctor_stats.total or 0,
            'active_doctors': doctor_stats.active or 0,
            'available_doctors': doctor_stats.available or 0,
            'head_doctor': head_doctor_info,
            'specializations': [
                {'specialization': spec, 'count': count}
                for spec, count in specializations
            ],
            'is_active': department.is_active
        }
    
    def get_all_departments_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary statistics for all departments
        
        Returns:
            List of department summaries
        """
        # Replaced the nonexistent get_all() with get_multi()
        departments = self.dept_repo.get_multi(skip=0, limit=1000)
        
        summaries = []
        for dept in departments:
            # Count doctors in this department
            doctor_count = (
                self.db.query(func.count(Doctor.id))
                .filter(
                    and_(
                        Doctor.department_id == dept.id,
                        Doctor.is_active == True
                    )
                )
                .scalar() or 0
            )
            
            summaries.append({
                'id': dept.id,
                'name': dept.name,
                'code': dept.code,
                'doctor_count': doctor_count,
                'has_head': dept.head_doctor_id is not None,
                'is_active': dept.is_active
            })
        
        # Sort by doctor count descending
        summaries.sort(key=lambda x: x['doctor_count'], reverse=True)
        
        return summaries
        
        """
        Get summary statistics for all departments
        
        Returns:
            List of department summaries
        """
        departments = self.dept_repo.get_all()
        
        summaries = []
        for dept in departments:
            # Count doctors in this department
            doctor_count = (
                self.db.query(func.count(Doctor.id))
                .filter(
                    and_(
                        Doctor.department_id == dept.id,
                        Doctor.is_active == True
                    )
                )
                .scalar() or 0
            )
            
            summaries.append({
                'id': dept.id,
                'name': dept.name,
                'code': dept.code,
                'doctor_count': doctor_count,
                'has_head': dept.head_doctor_id is not None,
                'is_active': dept.is_active
            })
        
        # Sort by doctor count descending
        summaries.sort(key=lambda x: x['doctor_count'], reverse=True)
        
        return summaries
    
    def search_departments(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Search departments by name or code
        
        Args:
            search_term: Search query
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Dictionary with items and total count
        """
        query = self.db.query(Department).filter(
            and_(
                Department.tenant_id == self.tenant_id,
                or_(
                    Department.name.ilike(f"%{search_term}%"),
                    Department.code.ilike(f"%{search_term}%")
                )
            )
        )
        
        total = query.count()
        departments = query.offset(skip).limit(limit).all()
        
        return {
            'items': [DepartmentSchema.from_orm(dept) for dept in departments],
            'total': total
        }
    
    def get_department_by_code(self, code: str) -> Optional[DepartmentSchema]:
        """
        Get department by code
        
        Args:
            code: Department code
            
        Returns:
            Department or None if not found
        """
        department = self.dept_repo.get_by_code(code.upper())
        
        if department:
            return DepartmentSchema.from_orm(department)
        
        return None
    
    def activate_department(self, department_id: int) -> Optional[DepartmentSchema]:
        """
        Activate department
        
        Args:
            department_id: Department ID
            
        Returns:
            Updated department or None if not found
        """
        department = self.dept_repo.get(department_id)
        
        if not department:
            return None
        
        department.is_active = True
        
        self.db.commit()
        self.db.refresh(department)
        
        return DepartmentSchema.from_orm(department)
    
    def deactivate_department(self, department_id: int) -> Optional[DepartmentSchema]:
        """
        Deactivate department
        
        Args:
            department_id: Department ID
            
        Returns:
            Updated department or None if not found
        """
        department = self.dept_repo.get(department_id)
        
        if not department:
            return None
        
        department.is_active = False
        
        self.db.commit()
        self.db.refresh(department)
        
        return DepartmentSchema.from_orm(department)
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _validate_department_access(self, department_id: int) -> bool:
        """
        Validate that department belongs to current tenant
        
        Args:
            department_id: Department ID
            
        Returns:
            True if department belongs to tenant, False otherwise
        """
        department = self.db.query(Department).filter(
            and_(
                Department.id == department_id,
                Department.tenant_id == self.tenant_id
            )
        ).first()
        
        return department is not None