"""
User Management CLI
====================
Manage the accounts behind the app's login gate.

Examples
--------
    python manage_users.py init                  # ensure default demo accounts
    python manage_users.py list                  # show all accounts
    python manage_users.py add alice             # prompt for a new password
    python manage_users.py setup-security alice  # set the 3 forgot-password questions
    python manage_users.py reset-password bob    # change an existing password
    python manage_users.py remove carol          # delete an account

Passwords are prompted for in hidden mode (never shown on screen or logs).
"""
import sys
import getpass
import auth


def cmd_init():
    users = auth._load_users()
    auth._save_users(auth._ensure_default_users(users))
    print("Default demo accounts ensured.")
    cmd_list()


def cmd_list():
    users = auth._load_users()
    if not users:
        print("No users configured yet. Run: python manage_users.py init")
        return
    print(f"{'username':<12} {'name':<22} {'role'}")
    print("-" * 48)
    for row in auth.list_users():
        print(f"{row['username']:<12} {row['name']:<22} {row['role']}")


def cmd_add(username):
    pwd = getpass.getpass(f"Password for '{username}' (min 6 chars): ")
    pwd2 = getpass.getpass("Confirm password: ")
    if pwd != pwd2:
        print("Passwords do not match. Aborting.")
        sys.exit(1)
    role = input("Role [analyst]: ").strip() or "analyst"
    name = input("Display name (Enter to skip): ").strip() or None
    if auth.add_user(username, pwd, role=role, name=name):
        print(f"User '{username}' created.")
    else:
        print("Could not create user (exists already, or password < 6 chars).")
        sys.exit(1)


def cmd_reset_password(username):
    pwd = getpass.getpass(f"New password for '{username}' (min 6 chars): ")
    pwd2 = getpass.getpass("Confirm password: ")
    if pwd != pwd2:
        print("Passwords do not match. Aborting.")
        sys.exit(1)
    if auth.reset_password(username, pwd):
        print(f"Password updated for '{username}'.")
    else:
        print(f"Unknown user '{username}'.")
        sys.exit(1)


def cmd_remove(username):
    if auth.remove_user(username):
        print(f"User '{username}' removed.")
    else:
        print(f"Unknown user '{username}'.")
        sys.exit(1)


def cmd_setup_security(username):
    """Set the 3 security questions used by the 'Forgot Password' flow."""
    existing = auth.get_security_questions(username)
    if existing is None:
        print(f"Unknown user '{username}'.")
        sys.exit(1)
    if existing:
        print("This user already has security questions configured:")
        for i, q in enumerate(existing, 1):
            print(f"  {i}. {q}")
    else:
        print("This user has no security questions yet.")

    print("\nPick 3 questions. Answers are case-insensitive and hashed.")
    qa = []
    chosen = []
    for slot in range(1, auth.SECURITY_QUESTION_COUNT + 1):
        print(f"\n{'='*60}\nQuestion {slot} of {auth.SECURITY_QUESTION_COUNT}:")
        for i, q in enumerate(auth.SECURITY_QUESTION_POOL, 1):
            print(f"  {i}. {q}")
        choice = input("Enter number: ").strip()
        try:
            num = int(choice)
            question = auth.SECURITY_QUESTION_POOL[num - 1]
        except (ValueError, IndexError):
            print("Invalid choice.")
            sys.exit(1)
        if num in chosen:
            print("Question already picked — choose a different one.")
            sys.exit(1)
        chosen.append(num)
        answer = getpass.getpass("Answer: ")
        qa.append((question, answer))

    if auth.set_security_questions(username, qa):
        print(f"\nSecurity questions saved for '{username}'.")
    else:
        print("\nFailed to save security questions.")
        sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    command = args[0]
    if command == "init":
        cmd_init()
    elif command == "list":
        cmd_list()
    elif command == "add" and len(args) == 2:
        cmd_add(args[1])
    elif command == "reset-password" and len(args) == 2:
        cmd_reset_password(args[1])
    elif command in ("setup-security", "set-security") and len(args) == 2:
        cmd_setup_security(args[1])
    elif command == "remove" and len(args) == 2:
        cmd_remove(args[1])
    else:
        print("Unknown command or missing argument.\n")
        print(__doc__)
        sys.exit(1)