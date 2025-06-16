from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_key: str
    openai_base: str
    search_endpoint: str
    search_index: str = "claims-idx"
    blob_conn: str
    cosmos_conn: str
    docai_endpoint: str
    docai_key: str

    class Config:
        env_file = ".env"

settings = Settings()   # import everywhere