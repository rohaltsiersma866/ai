import mysql.connector
from mysql.connector import Error
from datetime import datetime
import hashlib
import secrets
from typing import Optional, Dict, List


class Database:

    def __init__(self):
        self.config = {
            'host': '20.24.64.208',
            'database': 'agoiembeuk_ODIwN2E0MGEyNjc0Yj_database_name',
            'user': 'agoiembeuk_ODIwN2E0MGEyNjc0Yj_username_database',
            'password': 'ODIwN2E0MGEyNjc0YjRhYmEwMmRmNjI2ODVh',
            'port': 3306,
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci'
        }
        self.init_db()

    def get_connection(self):
        """Create database connection"""
        try:
            conn = mysql.connector.connect(**self.config)
            return conn
        except Error as e:
            print(f"❌ Error connecting to MariaDB: {e}")
            return None

    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        if not conn:
            return

        cursor = conn.cursor()

        try:
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(64) NOT NULL,
                    role VARCHAR(20) DEFAULT 'user',
                    credits INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP NULL,
                    is_active TINYINT(1) DEFAULT 1,
                    INDEX idx_email (email),
                    INDEX idx_role (role)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # API Keys table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    key_value TEXT NOT NULL,
                    name VARCHAR(255),
                    remaining_credits INT DEFAULT 2500,
                    total_used INT DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'active',
                    last_credit_check TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active TINYINT(1) DEFAULT 1,
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Contact messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contact_messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    subject VARCHAR(255) NOT NULL,
                    message TEXT NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    admin_reply TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    replied_at TIMESTAMP NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_id (user_id),
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Credit transactions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS credit_transactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    amount INT NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    description TEXT,
                    admin_id INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE SET NULL,
                    INDEX idx_user_id (user_id),
                    INDEX idx_type (type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    session_token VARCHAR(255) UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_session_token (session_token),
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            conn.commit()
            print("✅ Database tables initialized successfully")

        except Error as e:
            print(f"❌ Error creating tables: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

        # Create default admin
        self.create_default_admin()

    def create_default_admin(self):
        """Create default admin account"""
        try:
            # Check if admin already exists
            existing_admin = self.get_user_by_email("admin@indexchecker.com")
            if existing_admin:
                print("ℹ️  Default admin already exists")
                return

            user_id = self.create_user(email="admin@indexchecker.com",
                                       password="Admin@123456",
                                       role="admin",
                                       credits=10000)

            if user_id:
                print(
                    "✅ Default admin created: admin@indexchecker.com / Admin@123456"
                )
            else:
                print("⚠️  Could not create default admin")

        except Exception as e:
            print(f"⚠️  Error creating default admin: {e}")

    # ============= USER MANAGEMENT =============

    def hash_password(self, password: str) -> str:
        """Hash password with salt"""
        return hashlib.sha256(password.encode()).hexdigest()

    def create_user(self,
                    email: str,
                    password: str,
                    role: str = 'user',
                    credits: int = 0) -> Optional[int]:
        """Create new user"""
        conn = self.get_connection()
        if not conn:
            return None

        cursor = conn.cursor()

        try:
            password_hash = self.hash_password(password)
            cursor.execute(
                """
                INSERT INTO users (email, password_hash, role, credits)
                VALUES (%s, %s, %s, %s)
            """, (email, password_hash, role, credits))

            conn.commit()
            user_id = cursor.lastrowid
            return user_id
        except Error as e:
            print(f"❌ Error creating user: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def verify_user(self, email: str, password: str) -> Optional[Dict]:
        """Verify user credentials"""
        conn = self.get_connection()
        if not conn:
            return None

        cursor = conn.cursor(dictionary=True)

        try:
            password_hash = self.hash_password(password)
            cursor.execute(
                """
                SELECT * FROM users 
                WHERE email = %s AND password_hash = %s AND is_active = 1
            """, (email, password_hash))

            user = cursor.fetchone()

            # Convert datetime objects to strings
            if user:
                if user.get('created_at'):
                    user['created_at'] = user['created_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')
                if user.get('last_login'):
                    user['last_login'] = user['last_login'].strftime(
                        '%Y-%m-%d %H:%M:%S')

            return user
        except Error as e:
            print(f"❌ Error verifying user: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        conn = self.get_connection()
        if not conn:
            return None

        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id, ))
            user = cursor.fetchone()

            # Convert datetime objects to strings
            if user:
                if user.get('created_at'):
                    user['created_at'] = user['created_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')
                if user.get('last_login'):
                    user['last_login'] = user['last_login'].strftime(
                        '%Y-%m-%d %H:%M:%S')

            return user
        except Error as e:
            print(f"❌ Error getting user: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        conn = self.get_connection()
        if not conn:
            return None

        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email, ))
            user = cursor.fetchone()

            # Convert datetime objects to strings
            if user:
                if user.get('created_at'):
                    user['created_at'] = user['created_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')
                if user.get('last_login'):
                    user['last_login'] = user['last_login'].strftime(
                        '%Y-%m-%d %H:%M:%S')

            return user
        except Error as e:
            print(f"❌ Error getting user by email: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def update_user_credits(self,
                            user_id: int,
                            amount: int,
                            admin_id: int,
                            description: str = "") -> bool:
        """Update user credits"""
        conn = self.get_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        try:
            # Update credits
            cursor.execute(
                """
                UPDATE users SET credits = credits + %s
                WHERE id = %s
            """, (amount, user_id))

            # Log transaction
            cursor.execute(
                """
                INSERT INTO credit_transactions (user_id, amount, type, description, admin_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, amount, 'admin_adjust', description, admin_id))

            conn.commit()
            return True
        except Error as e:
            print(f"❌ Error updating credits: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def deduct_user_credits(self, user_id: int, amount: int) -> bool:
        """Deduct credits from user (for index checking)"""
        conn = self.get_connection()
        if not conn:
            return False

        cursor = conn.cursor(dictionary=True)

        try:
            # Check if user has enough credits
            cursor.execute("SELECT credits FROM users WHERE id = %s",
                           (user_id, ))
            result = cursor.fetchone()

            if not result or result['credits'] < amount:
                return False

            # Deduct credits
            cursor.execute(
                """
                UPDATE users SET credits = credits - %s
                WHERE id = %s
            """, (amount, user_id))

            # Log transaction
            cursor.execute(
                """
                INSERT INTO credit_transactions (user_id, amount, type, description)
                VALUES (%s, %s, %s, %s)
            """, (user_id, -amount, 'usage',
                  f'Used {amount} credits for index checking'))

            conn.commit()
            return True
        except Error as e:
            print(f"❌ Error deducting credits: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def get_all_users(self) -> List[Dict]:
        """Get all users (admin only)"""
        conn = self.get_connection()
        if not conn:
            return []

        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute("""
                SELECT id, email, role, credits, created_at, last_login, is_active
                FROM users
                ORDER BY created_at DESC
            """)

            users = cursor.fetchall()

            # Convert datetime objects to strings
            for user in users:
                if user.get('created_at'):
                    user['created_at'] = user['created_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')
                if user.get('last_login'):
                    user['last_login'] = user['last_login'].strftime(
                        '%Y-%m-%d %H:%M:%S')

            return users
        except Error as e:
            print(f"❌ Error getting users: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    # ============= SESSION MANAGEMENT =============

    def create_session(self, user_id: int) -> str:
        """Create session for user"""
        conn = self.get_connection()
        if not conn:
            return ""

        cursor = conn.cursor()

        try:
            session_token = secrets.token_urlsafe(32)
            expires_at = datetime.now().timestamp() + (7 * 24 * 3600)  # 7 days

            cursor.execute(
                """
                INSERT INTO sessions (user_id, session_token, expires_at)
                VALUES (%s, %s, FROM_UNIXTIME(%s))
            """, (user_id, session_token, expires_at))

            # Update last login
            cursor.execute(
                """
                UPDATE users SET last_login = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (user_id, ))

            conn.commit()
            return session_token
        except Error as e:
            print(f"❌ Error creating session: {e}")
            return ""
        finally:
            cursor.close()
            conn.close()

    def get_session(self, session_token: str) -> Optional[Dict]:
        """Get session and user data"""
        conn = self.get_connection()
        if not conn:
            return None

        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT s.*, u.* FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.session_token = %s 
                AND s.expires_at > CURRENT_TIMESTAMP
                AND u.is_active = 1
            """, (session_token, ))

            result = cursor.fetchone()

            # Convert datetime objects to strings
            if result:
                if result.get('created_at'):
                    result['created_at'] = result['created_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')
                if result.get('last_login'):
                    result['last_login'] = result['last_login'].strftime(
                        '%Y-%m-%d %H:%M:%S')
                if result.get('expires_at'):
                    result['expires_at'] = result['expires_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')

            return result
        except Error as e:
            print(f"❌ Error getting session: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def delete_session(self, session_token: str):
        """Delete session (logout)"""
        conn = self.get_connection()
        if not conn:
            return

        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM sessions WHERE session_token = %s",
                           (session_token, ))
            conn.commit()
        except Error as e:
            print(f"❌ Error deleting session: {e}")
        finally:
            cursor.close()
            conn.close()

    # ============= API KEYS MANAGEMENT =============

    def add_api_key(self, key_value: str, name: str = "") -> Optional[int]:
        """Add new API key"""
        conn = self.get_connection()
        if not conn:
            return None

        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO api_keys (key_value, name)
                VALUES (%s, %s)
            """, (key_value, name))

            conn.commit()
            key_id = cursor.lastrowid
            return key_id
        except Error as e:
            print(f"❌ Error adding API key: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def get_all_api_keys(self) -> List[Dict]:
        """Get all API keys"""
        conn = self.get_connection()
        if not conn:
            return []

        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute("""
                SELECT * FROM api_keys
                WHERE is_active = 1
                ORDER BY id
            """)

            keys = cursor.fetchall()

            # Convert datetime objects to strings
            for key in keys:
                if key.get('created_at'):
                    key['created_at'] = key['created_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')
                if key.get('last_credit_check'):
                    key['last_credit_check'] = key[
                        'last_credit_check'].strftime('%Y-%m-%d %H:%M:%S')

            return keys
        except Error as e:
            print(f"❌ Error getting API keys: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def update_api_key_credits(self, key_id: int, remaining: int,
                               total_used: int, status: str):
        """Update API key credits"""
        conn = self.get_connection()
        if not conn:
            return

        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE api_keys 
                SET remaining_credits = %s, total_used = %s, status = %s,
                    last_credit_check = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (remaining, total_used, status, key_id))

            conn.commit()
        except Error as e:
            print(f"❌ Error updating API key credits: {e}")
        finally:
            cursor.close()
            conn.close()

    def delete_api_key(self, key_id: int) -> bool:
        """Delete API key"""
        conn = self.get_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE api_keys SET is_active = 0
                WHERE id = %s
            """, (key_id, ))

            conn.commit()
            return True
        except Error as e:
            print(f"❌ Error deleting API key: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

    # ============= CONTACT MESSAGES =============

    def create_contact_message(self, user_id: int, subject: str,
                               message: str) -> Optional[int]:
        """Create contact message"""
        conn = self.get_connection()
        if not conn:
            return None

        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO contact_messages (user_id, subject, message)
                VALUES (%s, %s, %s)
            """, (user_id, subject, message))

            conn.commit()
            message_id = cursor.lastrowid
            return message_id
        except Error as e:
            print(f"❌ Error creating message: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def get_contact_messages(self, status: str = None) -> List[Dict]:
        """Get contact messages"""
        conn = self.get_connection()
        if not conn:
            return []

        cursor = conn.cursor(dictionary=True)

        try:
            if status:
                cursor.execute(
                    """
                    SELECT cm.*, u.email as user_email
                    FROM contact_messages cm
                    JOIN users u ON cm.user_id = u.id
                    WHERE cm.status = %s
                    ORDER BY cm.created_at DESC
                """, (status, ))
            else:
                cursor.execute("""
                    SELECT cm.*, u.email as user_email
                    FROM contact_messages cm
                    JOIN users u ON cm.user_id = u.id
                    ORDER BY cm.created_at DESC
                """)

            messages = cursor.fetchall()

            # Convert datetime objects to strings
            for msg in messages:
                if msg.get('created_at'):
                    msg['created_at'] = msg['created_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')
                if msg.get('replied_at'):
                    msg['replied_at'] = msg['replied_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')

            return messages
        except Error as e:
            print(f"❌ Error getting messages: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def reply_contact_message(self, message_id: int, admin_reply: str) -> bool:
        """Reply to contact message"""
        conn = self.get_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE contact_messages 
                SET admin_reply = %s, status = 'replied', replied_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (admin_reply, message_id))

            conn.commit()
            return True
        except Error as e:
            print(f"❌ Error replying to message: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

    def get_user_messages(self, user_id: int) -> List[Dict]:
        """Get messages for specific user"""
        conn = self.get_connection()
        if not conn:
            return []

        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT * FROM contact_messages
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id, ))

            messages = cursor.fetchall()

            # Convert datetime objects to strings
            for msg in messages:
                if msg.get('created_at'):
                    msg['created_at'] = msg['created_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')
                if msg.get('replied_at'):
                    msg['replied_at'] = msg['replied_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')

            return messages
        except Error as e:
            print(f"❌ Error getting user messages: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    # ============= CREDIT TRANSACTIONS =============

    def get_user_transactions(self,
                              user_id: int,
                              limit: int = 50) -> List[Dict]:
        """Get user credit transactions"""
        conn = self.get_connection()
        if not conn:
            return []

        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT ct.*, u.email as admin_email
                FROM credit_transactions ct
                LEFT JOIN users u ON ct.admin_id = u.id
                WHERE ct.user_id = %s
                ORDER BY ct.created_at DESC
                LIMIT %s
            """, (user_id, limit))

            transactions = cursor.fetchall()

            # Convert datetime objects to strings
            for trans in transactions:
                if trans.get('created_at'):
                    trans['created_at'] = trans['created_at'].strftime(
                        '%Y-%m-%d %H:%M:%S')

            return transactions
        except Error as e:
            print(f"❌ Error getting transactions: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
