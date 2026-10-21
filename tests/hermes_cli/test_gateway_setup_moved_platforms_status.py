"""Setup-menu status for the messaging platforms that moved from core into bundled plugins.

The old static wizard rows read credentials through ``get_env_value`` (``.env``-backed), so a profile whose
credentials live only in ``.env`` showed "configured". A plain CLI process never loads ``.env`` into
``os.environ``, so a plugin ``is_connected`` that reads only the scoped environment reports "not configured"
for the same profile.
"""

import pytest

# platform -> the credential env vars the old static rows (or config_env enablement) required.
_CREDENTIALS = {
    "signal": {"SIGNAL_HTTP_URL": "http://127.0.0.1:8080", "SIGNAL_ACCOUNT": "+15550001111"},
    "weixin": {"WEIXIN_ACCOUNT_ID": "acct@im.bot", "WEIXIN_TOKEN": "tok"},
    "bluebubbles": {"BLUEBUBBLES_SERVER_URL": "http://127.0.0.1:1234", "BLUEBUBBLES_PASSWORD": "pw"},
    "qqbot": {"QQ_APP_ID": "1", "QQ_CLIENT_SECRET": "s"},
    "yuanbao": {"YUANBAO_APP_ID": "a", "YUANBAO_APP_SECRET": "s"},
    "whatsapp_cloud": {"WHATSAPP_CLOUD_PHONE_NUMBER_ID": "1", "WHATSAPP_CLOUD_ACCESS_TOKEN": "t"},
}


