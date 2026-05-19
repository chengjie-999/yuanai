from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import os
import logging
from typing import Tuple, Dict

logger = logging.getLogger(__name__)


# ---------------------- 核心加密解密类 ----------------------
class SensitiveDataEncryptor:
    """敏感数据加密解密工具类"""

    def __init__(self, password: str, salt: bytes = None):
        """
        初始化加密器
        :param password: 加密密码（自定义，用于生成密钥）
        :param salt: 盐值（可选，不传则自动生成）
        """
        self.password = password.encode("utf-8")
        # 盐值：随机生成16字节（增强密钥唯一性），可保存用于解密
        self.salt = salt if salt else os.urandom(16)
        # 生成加密密钥
        self.key = self._generate_key()

    def _generate_key(self) -> bytes:
        """从密码和盐值生成AES密钥（PBKDF2算法）"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # AES-256需要32字节密钥
            salt=self.salt,
            iterations=100000,  # 迭代次数，越高越安全（耗时也增加）
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.password))
        return key

    # 修复：将 tuple[bytes, bytes] 改为 Tuple[bytes, bytes]
    def encrypt(self, sensitive_data: str) -> Tuple[bytes, bytes]:
        """
        加密敏感数据
        :param sensitive_data: 待加密的敏感字符串（如API密钥、密码）
        :return: (加密后的数据, 盐值) —— 盐值需保存用于解密
        """
        f = Fernet(self.key)
        encrypted_data = f.encrypt(sensitive_data.encode("utf-8"))
        return encrypted_data, self.salt

    def decrypt(self, encrypted_data: bytes, salt: bytes) -> str:
        """
        解密数据
        :param encrypted_data: 加密后的数据
        :param salt: 加密时的盐值
        :return: 解密后的原始字符串
        """
        # 重新生成对应密钥（必须用加密时的盐值和密码）
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.password))
        f = Fernet(key)
        decrypted_data = f.decrypt(encrypted_data).decode("utf-8")
        return decrypted_data


# ---------------------- 快捷函数（简化调用） ----------------------
def _get_encryption_password():
    """从环境变量获取加密密码，未设置则报错"""
    pwd = os.getenv("ENCRYPTION_PASSWORD")
    if not pwd:
        raise RuntimeError("未设置 ENCRYPTION_PASSWORD 环境变量，无法解密敏感数据")
    return pwd


def _get_env_or_decrypt(env_key, encrypted_dict):
    """优先从环境变量读取，其次解密已存储的加密值"""
    env_val = os.getenv(env_key)
    if env_val:
        return env_val
    if encrypted_dict and encrypted_dict.get("encrypted_data"):
        password = _get_encryption_password()
        return decrypt_sensitive_data(encrypted_dict, password)
    raise RuntimeError(f"未设置 {env_key} 环境变量，且无已存储的加密数据")


def get_api_key(model_type='dsllm'):
    """获取 API Key，优先从环境变量读取"""
    env_key_map = {
        'dsllm': 'DEEPSEEK_API_KEY',
        'seed': 'DOUBAO_API_KEY',
    }
    encrypted_map = {
        'dsllm': {
            'encrypted_data': os.getenv("DEEPSEEK_API_KEY_ENCRYPTED", ""),
            'salt': os.getenv("DEEPSEEK_API_KEY_SALT", ""),
        },
        'seed': {
            'encrypted_data': os.getenv("DOUBAO_API_KEY_ENCRYPTED", ""),
            'salt': os.getenv("DOUBAO_API_KEY_SALT", ""),
        },
    }
    if model_type not in env_key_map:
        raise ValueError(f"无效的model_type值：{model_type}，仅支持 {list(env_key_map.keys())}")
    return _get_env_or_decrypt(env_key_map[model_type], encrypted_map[model_type])


def encrypt_sensitive_data(data: str, password: str) -> Dict[str, str]:
    """快捷加密函数（返回可序列化的结果）"""
    encryptor = SensitiveDataEncryptor(password)
    encrypted_data, salt = encryptor.encrypt(data)
    return {
        "encrypted_data": base64.b64encode(encrypted_data).decode("utf-8"),
        "salt": base64.b64encode(salt).decode("utf-8")
    }


def decrypt_sensitive_data(encrypted_dict: Dict[str, str], password: str) -> str:
    """快捷解密函数"""
    encrypted_data = base64.b64decode(encrypted_dict["encrypted_data"])
    salt = base64.b64decode(encrypted_dict["salt"])
    encryptor = SensitiveDataEncryptor(password, salt)
    return encryptor.decrypt(encrypted_data, salt)


def get_mysql_config() -> dict:
    """获取 MySQL 配置，优先从环境变量读取"""
    password = os.getenv("MYSQL_PASSWORD")
    if not password:
        encrypted = {
            'encrypted_data': os.getenv("MYSQL_PASSWORD_ENCRYPTED", ""),
            'salt': os.getenv("MYSQL_PASSWORD_SALT", ""),
        }
        if encrypted['encrypted_data']:
            password = decrypt_sensitive_data(encrypted, _get_encryption_password())
    if not password:
        raise RuntimeError("未设置 MYSQL_PASSWORD 或 MYSQL_PASSWORD_ENCRYPTED 环境变量")
    return {
        "user": os.getenv("MYSQL_USER", "root"),
        "password": password,
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "database": os.getenv("MYSQL_DATABASE", "ai_agent"),
    }


def get_cloud_mysql_config() -> dict:
    """获取云 MySQL 配置，优先从环境变量读取"""
    password = os.getenv("CLOUD_MYSQL_PASSWORD")
    if not password:
        encrypted = {
            'encrypted_data': os.getenv("CLOUD_MYSQL_PASSWORD_ENCRYPTED", ""),
            'salt': os.getenv("CLOUD_MYSQL_PASSWORD_SALT", ""),
        }
        if encrypted['encrypted_data']:
            password = decrypt_sensitive_data(encrypted, _get_encryption_password())
    if not password:
        raise RuntimeError("未设置 CLOUD_MYSQL_PASSWORD 或 CLOUD_MYSQL_PASSWORD_ENCRYPTED 环境变量")
    return {
        "user": os.getenv("CLOUD_MYSQL_USER", "root"),
        "password": password,
        "host": os.getenv("CLOUD_MYSQL_HOST", ""),
        "port": int(os.getenv("CLOUD_MYSQL_PORT", "3306")),
        "database": os.getenv("CLOUD_MYSQL_DATABASE", "ai_agent"),
    }


if __name__ == "__main__":
    print("=== 敏感数据加密工具 ===")
    password = input("请输入加密密码: ")
    data = input("请输入需要加密的数据: ")
    result = encrypt_sensitive_data(data, password)
    print(f"\nencrypted_data: {result['encrypted_data']}")
    print(f"salt: {result['salt']}")
    print("\n将上述两行设置为对应的环境变量 _ENCRYPTED 和 _SALT 即可")
