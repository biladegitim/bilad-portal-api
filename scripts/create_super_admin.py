import argparse

from app.core.security import hash_password
from app.database.connection import SessionLocal
from app.models.user import User


def create_super_admin(email: str, password: str, full_name: str):
    db = SessionLocal()

    try:
        existing_user = db.query(User).filter(User.email == email).first()

        if existing_user:
            existing_user.full_name = full_name
            existing_user.hashed_password = hash_password(password)
            existing_user.role = "super_admin"
            existing_user.is_active = True
            db.commit()
            print(f"Updated super_admin: {email}")
            return

        user = User(
            full_name=full_name,
            email=email,
            hashed_password=hash_password(password),
            role="super_admin",
            position="Yönetici",
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Created super_admin: {email}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create or update a Bilad Portal super admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", default="Bilad Yönetici")
    args = parser.parse_args()

    create_super_admin(args.email, args.password, args.full_name)


if __name__ == "__main__":
    main()