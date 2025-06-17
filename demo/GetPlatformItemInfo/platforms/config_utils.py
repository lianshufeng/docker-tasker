import os


def merge_config_env(config: dict[str, dict]):
    tokenManager: dict = config.get("TokenManager", None)
    if tokenManager is None:
        return

    proxy: str = os.getenv("SCRIPT_PROXY",None)
    cookie: str = os.getenv("SCRIPT_COOKIE",None)

    for c in ['bilibili', 'douyin', 'tiktok']:
        it = tokenManager.get(c,None)
        if it is None:
            continue
        if proxy is not None:
            it['proxies']['http'] = proxy
            it['proxies']['https'] = proxy
        if cookie is not None:
            it['headers']['cookie'] = cookie


# 合并dict的配置文件
# def merge_config_env(config: dict, prefix=""):
#     """
#     用环境变量覆盖 config 里的值，支持嵌套，环境变量名用大写+下划线展开
#     :param config: dict类型的配置
#     :param prefix: 前缀, 用于递归时传递父级 key
#     """
#     for key, value in config.items():
#         env_key = f"{prefix}{key}".upper()
#         if isinstance(value, dict):
#             merge_config_env(value, prefix=env_key + "_")
#         else:
#             if env_key in os.environ:
#                 # 自动类型转换: 支持 int、float、bool等（按需扩展）
#                 env_value = os.environ[env_key]
#                 if isinstance(value, bool):
#                     env_value = env_value.lower() in ("1", "true", "yes", "on")
#                 elif isinstance(value, int):
#                     env_value = int(env_value)
#                 elif isinstance(value, float):
#                     env_value = float(env_value)
#                 config[key] = env_value
