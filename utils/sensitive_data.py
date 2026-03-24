from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import os
# 新增：导入兼容低版本Python的类型标注
from typing import Tuple, Dict


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
# 修复：添加兼容低版本的类型标注 Dict[str, str]
def encrypt_sensitive_data(data: str, password: str) -> Dict[str, str]:
    """
    快捷加密函数（返回可序列化的结果）
    :param data: 敏感数据
    :param password: 加密密码
    :return: {"encrypted_data": 加密字符串, "salt": 盐值字符串}
    """
    encryptor = SensitiveDataEncryptor(password)
    encrypted_data, salt = encryptor.encrypt(data)
    return {
        "encrypted_data": base64.b64encode(encrypted_data).decode("utf-8"),
        "salt": base64.b64encode(salt).decode("utf-8")
    }


def decrypt_sensitive_data(encrypted_dict: Dict[str, str], password: str) -> str:
    """
    快捷解密函数
    :param encrypted_dict: 加密返回的字典
    :param password: 加密密码
    :return: 解密后的原始数据
    """
    encrypted_data = base64.b64decode(encrypted_dict["encrypted_data"])
    salt = base64.b64decode(encrypted_dict["salt"])
    encryptor = SensitiveDataEncryptor(password, salt)
    return encryptor.decrypt(encrypted_data, salt)


# ---------------------- 测试示例 ----------------------
def get_api_key(model_type='dsllm', password="MySecurePassword123!"):
    if model_type == 'dsllm':
        dsllm_encrypted_api = {
            'encrypted_data': 'Z0FBQUFBQnB1WE5DY1E3aDM1LVFmV25jRUxVZjJVOE5HaGEwRml6ZXR3NzYxRFVNMjFadU8xakY1eXFITVBWdlBuNXdwZWFFSDVsekJ0a1ZibkVWOHF4amlETm51OUc2UV9BU1c2VUFTZ3Fvdm1KT0VNTWM2RTlISHpmYTFMLTIwQUVDdTk2aXBQN2E=',
            'salt': 'ihuF3qRKQKP6LGJdpc223g=='}

        # 解密
        return decrypt_sensitive_data(dsllm_encrypted_api, password)
        # 输出：sk-d0b3bf178759483e8e40020f5d00ee02
    else:
        raise ValueError(f"无效的model_type值：{model_type}，仅支持 'dsllm'")


if __name__ == "__main__":
    # # 待加密的敏感数据（如API密钥、数据库密码等）
    sensitive_data = "sk-d0b3bf178759483e8e40020f5d00ee02"
    # # 自定义加密密码（建议复杂且保密）
    # password = "MySecurePassword123!"
    api_key = get_api_key()
    # 验证解密正确性
    assert api_key == sensitive_data, "加密失败！"
    print("✅ 解密验证通过")
