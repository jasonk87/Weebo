import shelve

DB_FILE = 'knowledge.db'

def save_fact(fact_name: str, fact_content: str):
    """Saves a fact to the knowledge base."""
    with shelve.open(DB_FILE) as db:
        db[fact_name] = fact_content
    print(f"Fact '{fact_name}' saved.")

def get_fact(fact_name: str) -> str | None:
    """Retrieves a fact from the knowledge base."""
    with shelve.open(DB_FILE) as db:
        return db.get(fact_name)

def get_all_facts() -> dict:
    """Retrieves all facts from the knowledge base."""
    with shelve.open(DB_FILE) as db:
        return dict(db)
