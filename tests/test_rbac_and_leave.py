import unittest
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveRequest
from app.models.notification import Notification
from app.models.permission import Permission, UserPermission
from app.models.qr import QRToken
from app.models.room import Room, RoomReservation
from app.models.user import User
from app.core.rbac import normalize_role, scoped_user_ids
from app.routers.leave import approve_leave_request
from app.core.security import hash_password


class RbacAndLeaveTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        testing_session = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = testing_session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def add_user(self, full_name, email, role="employee", supervisor_id=None):
        user = User(
            full_name=full_name,
            email=email,
            hashed_password=hash_password("secret"),
            role=role,
            supervisor_id=supervisor_id,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def test_normalize_role_accepts_legacy_employee_alias(self):
        self.assertEqual(normalize_role("çalışan"), "employee")
        self.assertEqual(normalize_role("calisan"), "employee")
        self.assertEqual(normalize_role("employee"), "employee")

    def test_scoped_user_ids_match_role_hierarchy(self):
        super_admin = self.add_user("Super", "super@example.com", "super_admin")
        admin = self.add_user("Admin", "admin@example.com", "admin")
        employee = self.add_user(
            "Employee",
            "employee@example.com",
            "employee",
            admin.id,
        )
        other = self.add_user("Other", "other@example.com", "employee")

        self.assertEqual(
            set(scoped_user_ids(self.db, super_admin)),
            {super_admin.id, admin.id, employee.id, other.id},
        )
        self.assertEqual(scoped_user_ids(self.db, admin), [employee.id])
        self.assertEqual(scoped_user_ids(self.db, employee), [employee.id])

    def test_admin_can_approve_subordinate_leave_and_notify_employee(self):
        admin = self.add_user("Admin", "admin@example.com", "admin")
        employee = self.add_user(
            "Employee",
            "employee@example.com",
            "employee",
            admin.id,
        )
        leave = LeaveRequest(
            user_id=employee.id,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=8),
            reason="Test",
            status="pending",
        )
        self.db.add(leave)
        self.db.commit()
        self.db.refresh(leave)

        response = approve_leave_request(
            leave.id,
            {"sub": admin.email, "role": admin.role},
            self.db,
        )

        notification = self.db.query(Notification).filter(
            Notification.user_id == employee.id
        ).first()

        self.assertEqual(response["status"], "approved")
        self.assertIsNotNone(notification)
        self.assertEqual(notification.link, "/my-leaves")

    def test_admin_cannot_approve_non_subordinate_leave(self):
        admin = self.add_user("Admin", "admin@example.com", "admin")
        employee = self.add_user("Employee", "employee@example.com", "employee")
        leave = LeaveRequest(
            user_id=employee.id,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=8),
            reason="Test",
            status="pending",
        )
        self.db.add(leave)
        self.db.commit()
        self.db.refresh(leave)

        with self.assertRaises(HTTPException) as context:
            approve_leave_request(
                leave.id,
                {"sub": admin.email, "role": admin.role},
                self.db,
            )

        self.assertEqual(context.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
