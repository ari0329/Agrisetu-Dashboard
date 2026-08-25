"""Ping Atlas using MONGODB_URI from .env. Does not print secrets."""

from config import Config
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError


def main() -> int:
    uri = (Config.MONGODB_URI or "").strip()
    if not uri:
        print("FAIL: MONGODB_URI is missing. Put it in a .env file next to app.py.")
        return 1
    if "<" in uri or ">" in uri:
        print("FAIL: Remove < and > from the URI. Atlas placeholders are not part of the string.")
        return 1
    if "@gmail.com" in uri.split("@", 1)[0]:
        print("FAIL: Do not use your Google/Atlas login email as the URI username.")
        print("Create a Database User in Atlas, then use that username.")
        return 1

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        db = client[Config.MONGODB_DATABASE]
        users = db[Config.MONGODB_USERS_COLLECTION].count_documents({})
        print("OK: MongoDB connected.")
        print(f"Database: {Config.MONGODB_DATABASE}")
        print(f"Users collection: {Config.MONGODB_USERS_COLLECTION} ({users} documents)")
        return 0
    except ServerSelectionTimeoutError:
        print("FAIL: Could not reach the cluster (timeout).")
        print("Fix Atlas Network Access: add your current IP, or 0.0.0.0/0 for testing.")
        return 1
    except OperationFailure as exc:
        print("FAIL: Authentication rejected.")
        print("Use a Database User password, URL-encode special characters, and check the username.")
        print(f"Atlas message: {exc.details.get('errmsg', exc) if getattr(exc, 'details', None) else exc}")
        return 1
    except ConfigurationError as exc:
        print("FAIL: URI format is invalid.")
        print(str(exc))
        return 1
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
