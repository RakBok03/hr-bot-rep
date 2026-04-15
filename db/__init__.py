import sys
from db.db import models, repository, session

sys.modules["db.models"] = models
sys.modules["db.repository"] = repository
sys.modules["db.session"] = session

__all__ = ["models", "repository", "session"]
