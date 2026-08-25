import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.getenv("MONGODB_URI")

print("MONGODB_URI found:", bool(uri))

if not uri:
    print("❌ MONGODB_URI is missing")
    exit()

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)

    # Actually test the connection
    client.admin.command("ping")

    print("✅ MongoDB connection successful!")

    db = client["agrisetu"]
    print("✅ Database selected:", db.name)

    print("Collections:", db.list_collection_names())

except Exception as e:
    print("❌ MongoDB connection failed!")
    print(type(e).__name__)
    print(e)