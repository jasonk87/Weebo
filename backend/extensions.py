from flask_sqlalchemy import SQLAlchemy

# Create the SQLAlchemy extension instance, but don't attach it to an app yet.
# This allows models and other modules to import it without creating circular dependencies.
db_sql_alchemy = SQLAlchemy()
