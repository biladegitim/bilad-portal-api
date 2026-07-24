import unittest
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models.attendance import AttendanceRecord
from app.models.event import Event
from app.models.leave import LeaveRequest
from app.models.notification import Notification
from app.models.permission import Permission, UserPermission
from app.models.qr import QRToken
from app.models.room import Room, RoomReservation
from app.models.user import User
from app.core.rbac import normalize_role, scoped_user_ids
from app.routers.leave import approve_leave_request, create_leave_request, delete_leave_request
from app.routers.permission import assign_permission_to_user, remove_permission_from_user
from app.routers.user import delete_user, purge_inactive_users
from app.schemas.leave import LeaveCreate
from app.schemas.permission import UserPermissionCreate
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
        self.assertEqual(normalize_role("superadmin"), "super_admin")

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

    def test_leave_request_notifies_actual_approvers(self):
        super_admin = self.add_user("Super", "super@example.com", "super_admin")
        admin = self.add_user("Admin", "admin@example.com", "admin")
        unrelated_admin = self.add_user(
            "Other Admin",
            "other-admin@example.com",
            "admin",
        )
        permission_user = self.add_user(
            "Permission User",
            "permission@example.com",
            "employee",
        )
        employee = self.add_user(
            "Employee",
            "employee@example.com",
            "employee",
            admin.id,
        )
        permission = Permission(
            code="leave.approve",
            description="Leave approval",
        )
        self.db.add(permission)
        self.db.commit()
        self.db.add(UserPermission(
            user_id=permission_user.id,
            permission_id=permission.id,
        ))
        self.db.commit()

        create_leave_request(
            LeaveCreate(
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow() + timedelta(hours=8),
                reason="Test",
            ),
            {"sub": employee.email, "role": employee.role},
            self.db,
        )

        notified_user_ids = {
            notification.user_id
            for notification in self.db.query(Notification).filter(
                Notification.link == "/leaves"
            ).all()
        }

        self.assertIn(super_admin.id, notified_user_ids)
        self.assertIn(admin.id, notified_user_ids)
        self.assertIn(permission_user.id, notified_user_ids)
        self.assertNotIn(unrelated_admin.id, notified_user_ids)

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

    def test_user_can_delete_own_approved_leave(self):
        employee = self.add_user("Employee", "employee@example.com", "employee")
        leave = LeaveRequest(
            user_id=employee.id,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=8),
            reason="Test",
            status="approved",
        )
        self.db.add(leave)
        self.db.commit()
        self.db.refresh(leave)

        response = delete_leave_request(
            leave.id,
            {"sub": employee.email, "role": employee.role},
            self.db,
        )

        self.assertEqual(response["leave_id"], leave.id)
        self.assertIsNone(
            self.db.query(LeaveRequest).filter(LeaveRequest.id == leave.id).first()
        )

    def test_delete_user_removes_admin_and_related_records(self):
        super_admin = self.add_user("Super", "super@example.com", "super_admin")
        admin = self.add_user("Admin", "admin@example.com", "admin")
        employee = self.add_user(
            "Employee",
            "employee@example.com",
            "employee",
            admin.id,
        )
        leave = LeaveRequest(
            user_id=admin.id,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=8),
            reason="Test",
            status="pending",
        )
        approved_leave = LeaveRequest(
            user_id=employee.id,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=8),
            reason="Approved",
            status="approved",
            approved_by=admin.id,
        )
        attendance = AttendanceRecord(user_id=admin.id, record_type="check_in")
        notification = Notification(
            user_id=admin.id,
            title="Test",
            message="Test",
        )
        permission = Permission(code="attendance.view", description="Attendance")
        event = Event(
            title="Event",
            start_time=datetime.utcnow(),
            created_by=admin.id,
        )
        room = Room(name="Room")

        self.db.add_all([
            leave,
            approved_leave,
            attendance,
            notification,
            permission,
            event,
            room,
        ])
        self.db.commit()
        self.db.refresh(permission)
        self.db.refresh(room)

        user_permission = UserPermission(
            user_id=admin.id,
            permission_id=permission.id,
        )
        room_reservation = RoomReservation(
            room_id=room.id,
            title="Reservation",
            start_date=datetime.utcnow().date(),
            end_date=datetime.utcnow().date(),
            weekday=0,
            start_time=datetime.utcnow().time(),
            end_time=(datetime.utcnow() + timedelta(hours=1)).time(),
            created_by=admin.id,
        )
        self.db.add_all([user_permission, room_reservation])
        self.db.commit()

        response = delete_user(
            admin.id,
            {"sub": super_admin.email, "role": super_admin.role},
            self.db,
        )

        self.db.refresh(employee)
        self.db.refresh(approved_leave)

        self.assertEqual(response["user_id"], admin.id)
        self.assertIsNone(self.db.query(User).filter(User.id == admin.id).first())
        self.assertIsNone(employee.supervisor_id)
        self.assertIsNone(approved_leave.approved_by)
        self.assertEqual(
            self.db.query(AttendanceRecord).filter(
                AttendanceRecord.user_id == admin.id
            ).count(),
            0,
        )
        self.assertEqual(
            self.db.query(LeaveRequest).filter(LeaveRequest.user_id == admin.id).count(),
            0,
        )
        self.assertEqual(
            self.db.query(UserPermission).filter(
                UserPermission.user_id == admin.id
            ).count(),
            0,
        )
        self.assertEqual(
            self.db.query(Notification).filter(Notification.user_id == admin.id).count(),
            0,
        )
        self.assertEqual(
            self.db.query(Event).filter(Event.created_by == admin.id).count(),
            0,
        )
        self.assertEqual(
            self.db.query(RoomReservation).filter(
                RoomReservation.created_by == admin.id
            ).count(),
            0,
        )
        self.assertNotIn(admin.id, scoped_user_ids(self.db, super_admin))

    def test_purge_inactive_users_removes_existing_passive_accounts(self):
        inactive = self.add_user("Inactive", "inactive@example.com", "employee")
        inactive.is_active = False
        self.db.commit()

        deleted_count = purge_inactive_users(self.db)
        self.db.commit()

        self.assertEqual(deleted_count, 1)
        self.assertIsNone(self.db.query(User).filter(User.id == inactive.id).first())

    def test_user_permission_updates_are_idempotent(self):
        super_admin = self.add_user("Super", "super@example.com", "super_admin")
        employee = self.add_user("Employee", "employee@example.com", "employee")
        permission = Permission(
            code="menu.manage",
            description="Menu management",
        )
        self.db.add(permission)
        self.db.commit()

        payload = UserPermissionCreate(permission_code=permission.code)

        first_assign = assign_permission_to_user(
            employee.id,
            payload,
            {"sub": super_admin.email, "role": super_admin.role},
            self.db,
        )
        second_assign = assign_permission_to_user(
            employee.id,
            payload,
            {"sub": super_admin.email, "role": super_admin.role},
            self.db,
        )
        first_remove = remove_permission_from_user(
            employee.id,
            permission.code,
            {"sub": super_admin.email, "role": super_admin.role},
            self.db,
        )
        second_remove = remove_permission_from_user(
            employee.id,
            permission.code,
            {"sub": super_admin.email, "role": super_admin.role},
            self.db,
        )

        self.assertEqual(first_assign["permission"], permission.code)
        self.assertEqual(second_assign["permission"], permission.code)
        self.assertEqual(first_remove["permission"], permission.code)
        self.assertEqual(second_remove["permission"], permission.code)

    def test_user_permission_update_creates_missing_permission_definition(self):
        super_admin = self.add_user("Super", "super@example.com", "super_admin")
        employee = self.add_user("Employee", "employee@example.com", "employee")
        payload = UserPermissionCreate(permission_code="leave.approve")

        response = assign_permission_to_user(
            employee.id,
            payload,
            {"sub": super_admin.email, "role": super_admin.role},
            self.db,
        )
        permission = self.db.query(Permission).filter(
            Permission.code == payload.permission_code
        ).first()

        self.assertEqual(response["permission"], payload.permission_code)
        self.assertIsNotNone(permission)

    def test_remove_missing_permission_definition_is_successful(self):
        super_admin = self.add_user("Super", "super@example.com", "super_admin")
        employee = self.add_user("Employee", "employee@example.com", "employee")

        response = remove_permission_from_user(
            employee.id,
            "attendance.view",
            {"sub": super_admin.email, "role": super_admin.role},
            self.db,
        )

        self.assertEqual(response["permission"], "attendance.view")


if __name__ == "__main__":
    unittest.main()
