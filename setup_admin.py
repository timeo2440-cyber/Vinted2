#!/usr/bin/env python3
"""
Script de création du compte admin.
Usage: python3 setup_admin.py <email> <password>
"""
import asyncio, sys, os

# Ensure we're in the backend directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(SCRIPT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)


async def main(email: str, password: str):
    import bcrypt
    from database import init_db, AsyncSessionLocal, User
    from sqlalchemy import select, delete

    print(f"Base de données : {os.environ.get('DATABASE_URL', 'défaut')}")

    await init_db()

    async with AsyncSessionLocal() as db:
        # Supprimer l'ancien compte si existe
        await db.execute(delete(User).where(User.email == email.lower()))
        await db.commit()

        # Créer le hash
        pw_hash = bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()

        # Vérifier que le hash fonctionne
        ok = bcrypt.checkpw(password.encode()[:72], pw_hash.encode())
        if not ok:
            print("ERREUR: Le hash bcrypt ne fonctionne pas !")
            return

        # Créer l'admin
        admin = User(
            email=email.lower(),
            password_hash=pw_hash,
            role="admin",
            plan="unlimited",
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        print(f"")
        print(f"✓ Compte admin créé avec succès !")
        print(f"  Email    : {admin.email}")
        print(f"  Plan     : {admin.plan}")
        print(f"  Role     : {admin.role}")
        print(f"  Hash OK  : {ok}")
        print(f"")
        print(f"→ Connectez-vous sur http://localhost:8000")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 setup_admin.py <email> <password>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
