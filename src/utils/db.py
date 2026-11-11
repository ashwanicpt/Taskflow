from sqlalchemy import create_engine
from  sqlalchemy.orm import sessionmaker , declarative_base
from src.utils.settings import settings

# declarative_base are used to create the table in the database and also interact with the database 
Base =declarative_base()

# create_engine() is a function from SQLAlchemy used to connect you python application to a database
# create_engine() create a database connection that sqlAlchmey uses to talk to database 
engine=create_engine(url=settings.DB_CONNECTION)
# Here we can create the session from the database 
# we create this session to the database so we can perform curd operation in the database
LocalSession=sessionmaker(bind=engine)

def get_db():
    session=LocalSession()
    try:
        yield session
    finally:
        session.close()