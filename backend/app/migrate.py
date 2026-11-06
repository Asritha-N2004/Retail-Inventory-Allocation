from .database import migrate

if __name__ == "__main__":
    migrate()
    print("Schema version 1 applied.")
