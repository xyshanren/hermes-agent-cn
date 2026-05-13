"""DeepSeek provider profile."""

from providers import register_provider
from providers.base import ProviderProfile

deepseek = ProviderProfile(
    name="deepseek",
    aliases=("deepseek-chat",),
    env_vars=("DEEPSEEK_API_KEY",),
    display_name="DeepSeek",
    description="DeepSeek — native DeepSeek API",
    signup_url="https://platform.deepseek.com/",
    fallback_models=(
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    ),
    base_url="https://api.deepseek.com",
)

register_provider(deepseek)
