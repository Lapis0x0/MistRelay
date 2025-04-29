import yaml

with open('./db/config.yml', 'r', encoding='utf-8') as f:
    result = yaml.load(f.read(), Loader=yaml.FullLoader)

API_ID = result['API_ID']
API_HASH = result['API_HASH']
BOT_TOKEN = result['BOT_TOKEN']
PROXY_IP = result['PROXY_IP']
PROXY_PORT = result['PROXY_PORT']
ADMIN_ID = result['ADMIN_ID']
FORWARD_ID = result['FORWARD_ID']
UP_TELEGRAM = result['UP_TELEGRAM']
# rclone相关配置
UP_ONEDRIVE = result.get('UP_ONEDRIVE', False)
RCLONE_REMOTE = result.get('RCLONE_REMOTE', 'onedrive')
RCLONE_PATH = result.get('RCLONE_PATH', '/Downloads')
RPC_SECRET = result['RPC_SECRET']
RPC_URL = result['RPC_URL']
