from app.rag import init_db

def seed():
    print("Initializing Database...")
    init_db()

if __name__ == "__main__":
    seed()