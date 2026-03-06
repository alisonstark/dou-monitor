# Authentication module for DOU Monitor
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import os

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Por favor, faça login para acessar o dashboard."

class User(UserMixin):
    """Simple user model for authentication"""
    def __init__(self, id: str):
        self.id = id

@login_manager.user_loader
def load_user(user_id: str):
    """Load user by ID for Flask-Login"""
    if user_id == "admin":
        return User("admin")
    return None

def verify_credentials(username: str, password: str) -> bool:
    """
    Verify username and password against environment variables.
    
    To generate password hash:
    python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('YOUR_PASSWORD'))"
    
    Then set in .env:
    ADMIN_USER=admin
    ADMIN_PASS_HASH=pbkdf2:sha256:...
    """
    admin_user = os.environ.get("ADMIN_USER", "admin")
    admin_pass_hash = os.environ.get("ADMIN_PASS_HASH")
    
    if not admin_pass_hash:
        # Fallback temporário para desenvolvimento (remover em produção)
        if os.environ.get("FLASK_ENV") == "development":
            return username == "admin" and password == "admin"
        return False
    
    if username == admin_user:
        return check_password_hash(admin_pass_hash, password)
    
    return False
