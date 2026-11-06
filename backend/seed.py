from app.database import migrate
from app.seed import seed

if __name__ == "__main__":
    migrate()
    seed()
    print("Reproducible retail dataset ready.")
